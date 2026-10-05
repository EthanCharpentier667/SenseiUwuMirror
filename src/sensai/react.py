"""Code-owned controller for the agent's constrained ReAct loop.

The model never drives the loop: at each step it only proposes one action, as JSON whose
shape (and allowed actions) is constrained by a schema built here. The controller then
validates that proposal, keeps the record of what was done, and the agent's code decides
whether to run a tool, reject the step, or stop and answer.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

FINAL_ANSWER = "final_answer"
DEFAULT_MAX_STEPS = 5
DEFAULT_MAX_CALLS_PER_TOOL = 2
DEFAULT_MAX_TOOL_CALLS = 3
DEFAULT_OBSERVATION_LIMIT = 4000

PLAN_PROMPT = (
    "You are the planning step of an assistant. You do not write the reply to the user "
    "here: you only choose the next action for the user's latest message.\n\n"
    "Actions:\n{actions}\n\n"
    "Rules:\n"
    '- "thought": one or two sentences, in English, on what the conversation and the '
    "results below already give. Never write the reply here.\n"
    '- "missing": the information you still need to reply, that is in neither the '
    'conversation nor the results below. Write "nothing" only if you can already give '
    "the full reply.\n"
    '- If "missing" is "nothing", or no tool can help, choose "{final}".\n'
    '- Otherwise choose one tool and fill "args" with its parameters only.\n'
    "- Never repeat a call already listed in the steps below.\n\n"
    "Steps already taken for this message:\n{steps}"
)
ANSWER_PROMPT = (
    "Notes prepared for the user's latest message (the user has not seen them):\n"
    "{notes}\n\n"
    "Reply to the user's latest message now, using these notes when they are relevant. "
    "Do not mention the tools."
)
FINDINGS_NOTE = "Information gathered with tools:\n{findings}"
DRAFT_NOTE = "Draft written while planning (check it against the information above):\n{draft}"
NOTHING_MISSING = {"", "nothing", "none", "nothing missing", "n/a", "na"}

_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


@dataclass(frozen=True)
class Decision:
    """One step proposed by the model: its reasoning, what it still misses, and its action."""

    thought: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    missing: str = ""


@dataclass
class Step:
    """A proposed step and what came of it.

    ``status`` is "done" (the tool ran), "failed" (it raised), "refused" (the user denied
    it) or "rejected" (the controller refused it before running anything).
    """

    decision: Decision
    status: str
    observation: str


def _canonical(args: dict[str, Any]) -> str:
    """A stable key for a set of arguments, to spot a call made twice."""
    return json.dumps(args, sort_keys=True, ensure_ascii=False)


def _nothing_missing(missing: str) -> bool:
    return missing.strip().strip(".!").lower() in NOTHING_MISSING


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}… [truncated]"


class ReActController:
    """State and rules of one ReAct run, for one user message."""

    def __init__(
        self,
        tool_definitions: list[dict[str, Any]],
        *,
        max_calls_per_tool: int = DEFAULT_MAX_CALLS_PER_TOOL,
        max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
        observation_limit: int = DEFAULT_OBSERVATION_LIMIT,
    ) -> None:
        """Initialize the controller.

        Args:
            tool_definitions: The tools' Ollama definitions (``Tool.define()``).
            max_calls_per_tool: How many times a single tool may run in this run.
            max_tool_calls: How many tool runs, all tools together, this run allows.
            observation_limit: Maximum characters of a tool result kept for the model.
        """
        self.functions: dict[str, dict[str, Any]] = {
            function["name"]: function
            for definition in tool_definitions
            if (function := definition.get("function", {})).get("name")
        }
        self.max_calls_per_tool = max_calls_per_tool
        self.max_tool_calls = max_tool_calls
        self.observation_limit = observation_limit
        self.steps: list[Step] = []
        self.draft: str | None = None

    def allowed_actions(self) -> list[str]:
        """Tools that still have call budget left, then the final answer."""
        calls = Counter(step.decision.action for step in self.steps if step.status == "done")
        if calls.total() >= self.max_tool_calls:
            return [FINAL_ANSWER]
        tools = [name for name in self.functions if calls[name] < self.max_calls_per_tool]
        return [*tools, FINAL_ANSWER]

    def schema(self) -> dict[str, Any]:
        """JSON schema the model's next step must follow (Ollama's ``format``).

        ``thought`` then ``missing`` come first, so the model has to say what it still
        lacks before it commits to an action.
        """
        return {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "missing": {"type": "string"},
                "action": {"type": "string", "enum": self.allowed_actions()},
                "args": {"type": "object"},
            },
            "required": ["thought", "missing", "action", "args"],
        }

    def parse(self, raw: str) -> Decision:
        """Read the model's step. Anything unreadable ends the loop with a final answer.

        Arguments a known tool doesn't declare are dropped (the model tends to copy other
        fields, like its thought, into them).
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return Decision(thought=raw.strip(), action=FINAL_ANSWER)
        if not isinstance(data, dict):
            return Decision(thought=raw.strip(), action=FINAL_ANSWER)
        action = str(data.get("action", FINAL_ANSWER)).strip()
        args = data.get("args")
        args = args if isinstance(args, dict) else {}
        if action in self.functions:
            parameters = self.functions[action].get("parameters") or {}
            declared = parameters.get("properties", {})
            args = {name: value for name, value in args.items() if name in declared}
        return Decision(
            thought=str(data.get("thought", "")).strip(),
            action=action,
            args=args,
            missing=str(data.get("missing", "")).strip(),
        )

    def finishes(self, decision: Decision) -> bool:
        """Whether this step ends the loop, decided by the code rather than the model.

        It does when the model chose the final answer, but also when, with tool results
        already in hand, it says nothing is missing while still picking a tool: that step's
        thought then often holds the answer already, so it's kept as a draft for the reply.
        Before any result, "nothing missing" with a tool is just the model copying the
        prompt's default value, so the tool call wins.
        """
        if decision.action == FINAL_ANSWER:
            return True
        has_results = any(step.status == "done" for step in self.steps)
        if has_results and _nothing_missing(decision.missing):
            self.draft = decision.thought or None
            return True
        return False

    def _arguments_error(self, decision: Decision) -> str | None:
        parameters = self.functions[decision.action].get("parameters") or {}
        properties: dict[str, Any] = parameters.get("properties", {})
        missing = [name for name in parameters.get("required", []) if name not in decision.args]
        if missing:
            return f"missing argument(s): {', '.join(missing)}."
        for name, value in decision.args.items():
            expected = _JSON_TYPES.get(properties.get(name, {}).get("type", ""))
            wrong_bool = isinstance(value, bool) and expected in {int, (int, float)}
            if expected is not None and (not isinstance(value, expected) or wrong_bool):
                return f"argument '{name}' must be of type {properties[name]['type']}."
        return None

    def check(self, decision: Decision) -> str | None:
        """Why a proposed tool step must not run, or None if it may."""
        allowed = self.allowed_actions()
        if decision.action not in allowed:
            return f"'{decision.action}' is not available now. Choose one of: {', '.join(allowed)}."
        if error := self._arguments_error(decision):
            return error
        key = _canonical(decision.args)
        for index, step in enumerate(self.steps, start=1):
            same_call = step.decision.action == decision.action
            if same_call and step.status != "rejected" and _canonical(step.decision.args) == key:
                return f"this exact call was already made at step {index}; use its result."
        return None

    def record(self, decision: Decision, status: str, observation: str) -> None:
        """Keep a step and its (truncated) result for the next decisions and the answer."""
        self.steps.append(Step(decision, status, _truncate(observation, self.observation_limit)))

    def _describe_action(self, name: str) -> str:
        function = self.functions[name]
        parameters = function.get("parameters") or {}
        required = set(parameters.get("required", []))
        params = ", ".join(
            f"{param}: {spec.get('type', 'any')}{'' if param in required else ' (optional)'}"
            for param, spec in parameters.get("properties", {}).items()
        )
        description = " ".join(function.get("description", "").split())
        return f"- {name}({params}): {description}"

    def _describe_steps(self) -> str:
        if not self.steps:
            return "(none yet)"
        lines = []
        for index, step in enumerate(self.steps, start=1):
            call = f"{step.decision.action} {_canonical(step.decision.args)}"
            lines.append(f"{index}. {call} -> {step.status}\n   {step.observation}")
        return "\n".join(lines)

    def plan_instructions(self) -> str:
        """System instructions for the next planning call, with the steps taken so far."""
        tools = [self._describe_action(name) for name in self.allowed_actions()[:-1]]
        final = f"- {FINAL_ANSWER}(): stop using tools and reply to the user."
        return PLAN_PROMPT.format(
            actions="\n".join([*tools, final]), final=FINAL_ANSWER, steps=self._describe_steps()
        )

    def answer_instructions(self) -> str | None:
        """System instructions for the reply: the tool results and the draft, if any."""
        findings = [
            f"- {step.decision.action} {_canonical(step.decision.args)}:\n{step.observation}"
            for step in self.steps
            if step.status == "done"
        ]
        notes = []
        if findings:
            notes.append(FINDINGS_NOTE.format(findings="\n\n".join(findings)))
        if self.draft:
            notes.append(DRAFT_NOTE.format(draft=self.draft))
        if not notes:
            return None
        return ANSWER_PROMPT.format(notes="\n\n".join(notes))
