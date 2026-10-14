"""Agent abstraction running a constrained ReAct loop over the available tools."""

import asyncio
import inspect
import json
from typing import Any

from sensai.client import OllamaClient, Response
from sensai.features.features import MCP, REACT, TOOLS, Features
from sensai.features.react.react import DEFAULT_MAX_STEPS, Decision, ReActController
from sensai.features.tools.mcp.mcp_tools import MCPTools
from sensai.ui.protocol import AsyncUIHandler

PLAN_OPTIONS = {"temperature": 0}


def _ephemeral(role: str, content: str) -> dict[str, Any]:
    """A message only meant for the model's current reasoning, never for the session history."""
    return {"role": role, "content": content, "ephemeral": True}


def _with_instructions(messages: list[dict[str, Any]], instructions: str) -> list[dict[str, Any]]:
    """Add an ephemeral system message with instructions, just before the latest message.

    It must not be the last message: chat templates like llama3.2's only open the
    assistant's turn after a user or tool message, so a trailing system message makes the
    model write that turn header itself (an "assistant" line in the reply). Such templates
    move every system message to the top anyway; others read it right before the message.
    """
    if not messages or messages[-1].get("role") == "system":
        return [*messages, _ephemeral("system", instructions)]
    return [*messages[:-1], _ephemeral("system", instructions), messages[-1]]


def _strip_ephemeral(response: Response, payload: list[dict[str, Any]]) -> Response:
    """Drop the messages built from ephemeral payload entries out of ``response.messages``.

    ``response.messages`` mirrors the payload one-to-one (then the reply), so the entries
    to drop are found by index; this keeps reasoning scaffolding out of the persisted session.
    """
    response.messages = [
        message
        for index, message in enumerate(response.messages)
        if index >= len(payload) or not payload[index].get("ephemeral")
    ]
    return response


class Agent:
    """Autonomous agent running a constrained ReAct loop.

    Each step, the model only proposes a JSON action constrained to the allowed ones
    (see ``ReActController``); the code validates it, runs the tool, and decides when
    to stop. The reply is then written in a separate call, without tools.
    """

    def __init__(  # noqa: PLR0913
        self,
        model: str = "llama3.2",
        tools: list[Any] | None = None,
        *,
        trust_level: str = "none",
        ui_handler: AsyncUIHandler | None = None,
        client: OllamaClient,
        features: Features | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            model: The Ollama model name to use.
            tools: List of available Tool instances.
            trust_level: Tool execution trust level: "none", "partial", or "total".
            ui_handler: Event handler for UI presentation.
            client: Optional preconfigured OllamaClient instance.
            features: Feature flags deciding whether tools, MCP tools and the ReAct loop
                are used. Default is None, which enables every feature.
        """
        self.model = model
        self.tools = tools or []
        self.trust_level = trust_level
        self.ui_handler = ui_handler
        self.client = client
        self.features = features or Features()
        self.max_turns = DEFAULT_MAX_STEPS
        self.system_prompt: str | None = None

    def _prepare_messages(
        self,
        prompt: str | None,
        messages: list[dict[str, Any]] | None,
        system_prompt: str | None,
    ) -> list[dict[str, Any]]:
        """Validate and format initial conversation messages."""
        effective_system = system_prompt or self.system_prompt
        if messages is not None:
            formatted = list(messages)
            if effective_system:
                idx = next((i for i, m in enumerate(formatted) if m.get("role") == "system"), None)
                if idx is not None:
                    formatted[idx] = {
                        **formatted[idx],
                        "content": effective_system + "\n\n" + formatted[idx]["content"],
                    }
                else:
                    formatted.insert(0, {"role": "system", "content": effective_system})
            return formatted

        if prompt is None:
            msg = "Either prompt or messages must be provided."
            raise ValueError(msg)

        result: list[dict[str, Any]] = []
        if effective_system:
            result.append({"role": "system", "content": effective_system})
        result.append({"role": "user", "content": prompt})
        return result

    def available_tools(self) -> list[Any]:
        """The tools the enabled features let the agent use, minus the disabled tools."""
        if not self.features.is_enabled(TOOLS):
            return []
        mcp_enabled = self.features.is_enabled(MCP)
        return [
            tool
            for tool in self.tools
            if self.features.is_tool_enabled(tool.name)
            and (mcp_enabled or not isinstance(tool, MCPTools))
        ]

    async def _dispatch_single_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, Any]:
        """Find and execute a tool by name, running sync tools in a thread."""
        for tool in self.available_tools():
            if getattr(tool, "name", None) == name:
                execute_fn = getattr(tool, "execute_async", None)
                if execute_fn is not None:
                    res = await execute_fn(**args)
                elif inspect.iscoroutinefunction(tool.execute):
                    res = await tool.execute(**args)
                else:
                    res = await asyncio.to_thread(tool.execute, **args)
                return True, res
        return False, None

    async def _check_tool_approval(
        self, fn_name: str, fn_args: dict[str, Any], tool: Any
    ) -> tuple[bool, str]:
        """Check if a tool call is approved by the user."""
        if self.trust_level == "total" or (
            self.trust_level == "partial" and tool and getattr(tool, "safe", False)
        ):
            return True, ""

        if not self.ui_handler:
            return False, "Action cancelled: approval required but no UI handler is available."

        approved = await self.ui_handler.on_tool_call_request(fn_name, fn_args)
        if not approved:
            return False, "Action cancelled by user."

        return True, ""

    async def _run_tool(self, decision: Decision) -> tuple[str, str]:
        """Ask approval for and run the tool of a validated step. Returns (status, observation).

        A failing tool doesn't stop the loop: its error becomes the observation, so the
        model can try something else or answer with what it has.
        """
        tool = next(
            (t for t in self.available_tools() if getattr(t, "name", None) == decision.action), None
        )
        approved, cancel_msg = await self._check_tool_approval(decision.action, decision.args, tool)
        if not approved:
            return "refused", cancel_msg

        if self.ui_handler:
            await self.ui_handler.start_spinner(f"Executing {decision.action}...")

        try:
            found, res = await self._dispatch_single_tool(decision.action, decision.args)
        except Exception as e:  # noqa: BLE001 - any tool failure is reported back to the model
            if self.ui_handler:
                await self.ui_handler.stop_spinner()
                await self.ui_handler.on_error(e, title=f"Tool Error: {decision.action}")
            return "failed", f"Error: {e}"

        if self.ui_handler:
            await self.ui_handler.stop_spinner()

        if not found:
            if self.ui_handler:
                await self.ui_handler.on_error(
                    RuntimeError(f"Tool '{decision.action}' not found."),
                    title=f"Tool Error: {decision.action}",
                )
            return "failed", f"Tool '{decision.action}' not found."

        if self.ui_handler:
            show_output = bool(getattr(tool, "show_output", False))
            await self.ui_handler.on_tool_call_result(decision.action, res, show_output=show_output)
        return "done", res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)

    async def _chat(
        self,
        messages: list[dict[str, Any]],
        formatted_tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Response:
        """Send a chat request, reporting any error to the UI before re-raising it."""
        try:
            return await self.client.chat(
                messages=messages, model=self.model, tools=formatted_tools, **kwargs
            )
        except Exception as e:
            if self.ui_handler:
                await self.ui_handler.on_error(e)
            raise

    def _format_tools(self) -> list[dict[str, Any]]:
        """Collect valid tool definitions for the controller."""
        formatted_tools: list[dict[str, Any]] = []
        for tool in self.available_tools():
            if not hasattr(tool, "define"):
                continue
            tool_def = tool.define()
            if not isinstance(tool_def, dict):
                continue
            formatted_tools.append(tool_def)
        return formatted_tools

    async def _plan(self, messages: list[dict[str, Any]], controller: ReActController) -> Decision:
        """Have the model propose the next step, as JSON constrained to the allowed actions.

        The planning instructions are a system message, so the model never mistakes them
        for something the user said.
        """
        if self.ui_handler:
            await self.ui_handler.start_spinner("Thinking...")
        payload = _with_instructions(messages, controller.plan_instructions())
        response = await self._chat(
            payload,
            [],
            stream=False,
            response_format=controller.schema(),
            options=PLAN_OPTIONS,
        )
        decision = controller.parse(response.response)
        if self.ui_handler:
            await self.ui_handler.stop_spinner()
            await self.ui_handler.on_thinking_chunk(
                f"{decision.thought}\n→ {decision.action} (missing: {decision.missing or '-'})\n\n"
            )
        return decision

    async def _answer(
        self, messages: list[dict[str, Any]], controller: ReActController
    ) -> Response:
        """Stream the reply to the user, without tools, from what the steps gathered."""
        if self.ui_handler:
            await self.ui_handler.start_spinner("Thinking...")
        instructions = controller.answer_instructions()
        payload = _with_instructions(messages, instructions) if instructions else messages
        response = await self._chat(payload, [], stream=True, ui_handler=self.ui_handler)
        return _strip_ephemeral(response, payload)

    async def run(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> Response:
        """Run the ReAct loop, then answer.

        At most ``max_turns`` steps are planned; the code, not the model, decides when the
        loop ends: on a final-answer step, a step missing nothing more, or once that budget
        is spent. With the ReAct feature disabled, or no tool available, the loop is skipped
        and the model answers right away.

        Args:
            prompt: User message prompt.
            messages: Optional conversation history overriding prompt.
            system_prompt: Optional system prompt to override default.

        Returns:
            The response carrying the reply to the user.
        """
        if self.max_turns < 1:
            msg = "max_turns must be at least 1."
            raise ValueError(msg)

        current_messages = self._prepare_messages(prompt, messages, system_prompt)
        formatted_tools = self._format_tools()
        controller = ReActController(formatted_tools)
        if not self.features.is_enabled(REACT) or not formatted_tools:
            return await self._answer(current_messages, controller)

        for _ in range(self.max_turns):
            if self.ui_handler:
                await self.ui_handler.start_spinner("Thinking...")
            decision = await self._plan(current_messages, controller)
            if controller.finishes(decision):
                break
            if reason := controller.check(decision):
                controller.record(decision, "rejected", f"Rejected: {reason}")
                continue
            status, observation = await self._run_tool(decision)
            controller.record(decision, status, observation)

        return await self._answer(current_messages, controller)
