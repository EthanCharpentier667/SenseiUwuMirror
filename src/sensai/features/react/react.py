"""Code-owned controller for the agent's constrained ReAct loop.

Each step follows ReAct's Thought -> Action -> Observation cycle: the model writes a
thought and proposes one action, as JSON whose shape (and allowed actions) is constrained
by a schema built here. The controller validates that proposal and keeps the trajectory,
replayed after the user's message as assistant (thought and action) and tool
(observation) messages, so the latest thing the model reads is the last observation.
The model ends the loop by choosing the final answer; the budgets only bound how long it
can go on.
"""

import json
from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

FINAL_ANSWER = "final_answer"
DEFAULT_MAX_STEPS = 5
DEFAULT_MAX_CALLS_PER_TOOL = 2
DEFAULT_MAX_TOOL_CALLS = 3
DEFAULT_OBSERVATION_LIMIT = 4000

PLAN_PROMPT = (
    "You are the reasoning step of an assistant working in a loop: at each step you think, "
    "pick one action, then see its result (the observation) at the next step. You do not "
    "write the reply to the user here.\n\n"
    "Actions:\n{actions}\n\n"
    "How to choose:\n"
    '- "thought": in English, reason about what the user asks for and what the '
    "observations below really contain. Rely on their content, not on which tools ran.\n"
    "- If the reply needs information you do not have yet and a tool can get it, choose "
    'that tool and fill "args" with its parameters only.\n'
    '- Choose "{final}" once the conversation and the observations hold what the reply '
    "needs, or when no tool can help.\n"
    "- Never repeat a call you already made: use its observation instead.\n\n"
    "Your previous steps for the user's latest message, if any, follow it: each of your "
    "actions, then its observation."
)
JSON_PROMPT = (
    "Reply with only a JSON object, nothing before or after it: "
    '{{"thought": "...", "action": "<one of: {actions}>", "args": {{...}}}}'
)
ANSWER_PROMPT = (
    "Notes prepared for the user's latest message (the user has not seen them):\n"
    "{notes}\n\n"
    "Reply to the user's latest message now, using these notes when they are relevant. "
    "Do not mention the tools."
)
FINDINGS_NOTE = "Information gathered with tools:\n{findings}"
IMAGES_NOTE = "[{count} image(s) from this tool are attached to the user's latest message.]"

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
    """One step proposed by the model: its reasoning and its action."""

    thought: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    """A proposed step and what came of it.

    ``status`` is "done" (the tool ran), "failed" (it raised), "refused" (the user denied
    it) or "rejected" (the controller refused it before running anything). ``images`` are
    the base64 images the tool returned, kept apart from the text observation.
    """

    decision: Decision
    status: str
    observation: str
    images: list[str] = field(default_factory=list)


def _canonical(args: dict[str, Any]) -> str:
    """A stable key for a set of arguments, to spot a call made twice."""
    return json.dumps(args, sort_keys=True, ensure_ascii=False)


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
        repeatable: Collection[str] = (),
    ) -> None:
        """Initialize the controller.

        Args:
            tool_definitions: The tools' Ollama definitions (``Tool.define()``).
            max_calls_per_tool: How many times a single tool may run in this run.
            max_tool_calls: How many tool runs, all tools together, this run allows.
            observation_limit: Maximum characters of a tool result kept for the model.
            repeatable: Tools whose same call may run again, its result changing over time
                (e.g. checking a background job).
        """
        self.functions: dict[str, dict[str, Any]] = {
            function["name"]: function
            for definition in tool_definitions
            if (function := definition.get("function", {})).get("name")
        }
        self.max_calls_per_tool = max_calls_per_tool
        self.max_tool_calls = max_tool_calls
        self.observation_limit = observation_limit
        self.repeatable = frozenset(repeatable)
        self.steps: list[Step] = []

    def allowed_actions(self) -> list[str]:
        """Tools that still have call budget left, then the final answer."""
        calls = Counter(step.decision.action for step in self.steps if step.status == "done")
        if calls.total() >= self.max_tool_calls:
            return [FINAL_ANSWER]
        tools = [name for name in self.functions if calls[name] < self.max_calls_per_tool]
        return [*tools, FINAL_ANSWER]

    def exhausted(self) -> bool:
        """Whether no tool can run anymore, so planning another step is pointless."""
        return self.allowed_actions() == [FINAL_ANSWER]

    def schema(self) -> dict[str, Any]:
        """JSON schema the model's next step must follow (Ollama's ``format``).

        ``thought`` comes first, so the model reasons before it commits to an action.
        """
        return {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "action": {"type": "string", "enum": self.allowed_actions()},
                "args": {"type": "object"},
            },
            "required": ["thought", "action", "args"],
        }

    def parse(self, raw: str) -> Decision:
        """Read the model's step. Anything unreadable ends the loop with a final answer.

        The JSON object may be surrounded by other text (e.g. a Markdown code fence, or a
        stray closing brace), as when the schema couldn't be enforced (see
        ``json_instructions``): the first complete object is read, the rest ignored.

        Arguments a known tool doesn't declare are dropped (the model tends to copy other
        fields, like its thought, into them). The final answer takes none: the model tends
        to write its whole reply there, which the answer step writes anyway.
        """
        try:
            start = raw.find("{")
            data = json.JSONDecoder().raw_decode(raw, start)[0] if start >= 0 else json.loads(raw)
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
        elif action == FINAL_ANSWER:
            args = {}
        return Decision(thought=str(data.get("thought", "")).strip(), action=action, args=args)

    def finishes(self, decision: Decision) -> bool:
        """Whether this step ends the loop.

        It does when the model chooses the final answer, or proposes a call that already
        ran: it has nothing new to do, and small models at temperature 0 would otherwise
        propose that same call again until the step budget is spent.
        """
        return decision.action == FINAL_ANSWER or self._already_made(decision) is not None

    def _already_made(self, decision: Decision) -> int | None:
        """The step at which this exact call already ran (not rejected), if it did."""
        if decision.action in self.repeatable:
            return None
        key = _canonical(decision.args)
        for index, step in enumerate(self.steps, start=1):
            same_call = step.decision.action == decision.action
            if same_call and step.status != "rejected" and _canonical(step.decision.args) == key:
                return index
        return None

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
        if (index := self._already_made(decision)) is not None:
            return f"this exact call was already made at step {index}; use its result."
        return None

    def record(
        self, decision: Decision, status: str, observation: str, images: list[str] | None = None
    ) -> None:
        """Keep a step and its (truncated) result for the next decisions and the answer.

        ``images`` (base64) are never truncated; the observation says they are attached.
        """
        observation = _truncate(observation, self.observation_limit)
        if images:
            observation = f"{observation}\n{IMAGES_NOTE.format(count=len(images))}"
        self.steps.append(Step(decision, status, observation, images or []))

    def images(self) -> list[str]:
        """The base64 images the tools that ran returned, for the model to look at."""
        return [image for step in self.steps if step.status == "done" for image in step.images]

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

    def trajectory(self) -> list[dict[str, Any]]:
        """The steps so far as messages to replay after the user's: action, then observation.

        They are ephemeral: only meant for this run's planning, never for the session.
        """
        messages: list[dict[str, Any]] = []
        for step in self.steps:
            decision = step.decision
            action = {"thought": decision.thought, "action": decision.action, "args": decision.args}
            label = "Observation" if step.status == "done" else f"Observation ({step.status})"
            messages += [
                {
                    "role": "assistant",
                    "content": json.dumps(action, ensure_ascii=False),
                    "ephemeral": True,
                },
                {
                    "role": "tool",
                    "tool_name": decision.action,
                    "content": f"{label}: {step.observation}",
                    "ephemeral": True,
                },
            ]
        return messages

    def plan_instructions(self) -> str:
        """System instructions for the next planning call: the actions it may choose."""
        tools = [self._describe_action(name) for name in self.allowed_actions()[:-1]]
        final = f"- {FINAL_ANSWER}(): stop using tools and reply to the user."
        return PLAN_PROMPT.format(actions="\n".join([*tools, final]), final=FINAL_ANSWER)

    def json_instructions(self) -> str:
        """The step's JSON shape, spelled out for a model whose output isn't constrained.

        Some servers (e.g. Ollama Cloud) answer nothing when given the schema as
        ``format``; the step is then asked for in the instructions instead.
        """
        return JSON_PROMPT.format(actions=", ".join(self.allowed_actions()))

    def answer_instructions(self) -> str | None:
        """System instructions for the reply: the tool results, if any."""
        findings = [
            f"- {step.decision.action} {_canonical(step.decision.args)}:\n{step.observation}"
            for step in self.steps
            if step.status == "done"
        ]
        if not findings:
            return None
        return ANSWER_PROMPT.format(notes=FINDINGS_NOTE.format(findings="\n\n".join(findings)))
