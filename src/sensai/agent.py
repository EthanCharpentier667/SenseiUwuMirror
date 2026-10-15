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


def _with_images(messages: list[dict[str, Any]], images: list[str]) -> list[dict[str, Any]]:
    """Attach base64 images to (a copy of) the latest user message, as Ollama expects them.

    The copy is sent to the model only: the persisted history never carries the images.
    """
    if not images:
        return messages
    index = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "user"), None
    )
    if index is None:
        return messages
    message = messages[index]
    with_images = {**message, "images": [*message.get("images", []), *images]}
    return [*messages[:index], with_images, *messages[index + 1 :]]


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
        self.read_documents: list[str] = []
        self._unconstrained_models: set[str] = set()

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

    async def _run_tool(self, decision: Decision) -> tuple[str, str, list[str]]:
        """Ask approval for and run the tool of a validated step.

        Returns (status, observation, images). A failing tool doesn't stop the loop: its
        error becomes the observation, so the model can try something else or answer with
        what it has. A dict result's "images" (base64) are taken out of the observation.
        """
        tool = next(
            (t for t in self.available_tools() if getattr(t, "name", None) == decision.action), None
        )
        approved, cancel_msg = await self._check_tool_approval(decision.action, decision.args, tool)
        if not approved:
            return "refused", cancel_msg, []

        if self.ui_handler:
            await self.ui_handler.start_spinner(f"Executing {decision.action}...")

        try:
            found, res = await self._dispatch_single_tool(decision.action, decision.args)
        except Exception as e:  # noqa: BLE001 - any tool failure is reported back to the model
            if self.ui_handler:
                await self.ui_handler.stop_spinner()
                await self.ui_handler.on_error(e, title=f"Tool Error: {decision.action}")
            return "failed", f"Error: {e}", []

        if self.ui_handler:
            await self.ui_handler.stop_spinner()

        if not found:
            if self.ui_handler:
                await self.ui_handler.on_error(
                    RuntimeError(f"Tool '{decision.action}' not found."),
                    title=f"Tool Error: {decision.action}",
                )
            return "failed", f"Tool '{decision.action}' not found.", []

        res, images = self._take_attachments(res)
        if self.ui_handler:
            show_output = bool(getattr(tool, "show_output", False))
            await self.ui_handler.on_tool_call_result(decision.action, res, show_output=show_output)
        observation, images = await self._observe(res, images)
        return "done", observation, images

    def _take_attachments(self, res: Any) -> tuple[Any, list[str]]:
        """Take a tool result's attachments out of it: its images and its document.

        A dict result's "images" (base64) are returned apart, for the model to look at; its
        "document" (a file path) is kept in ``read_documents``, for the app to ingest.
        """
        if not isinstance(res, dict):
            return res, []
        res = dict(res)
        images = list(res.pop("images", None) or [])
        if document := res.pop("document", None):
            self.read_documents.append(document)
        return res, images

    async def _observe(self, res: Any, images: list[str]) -> tuple[str, list[str]]:
        """Turn a tool's result into the observation text and the images the model can see.

        Images are dropped for a model without vision (Ollama rejects such a request); a
        tool returning images should declare ``requires={"vision"}`` so it isn't offered.
        """
        observation = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
        if images and "vision" not in await self.client.capabilities(self.model):
            return observation, []
        return observation, images

    async def _usable_tools(self) -> list[Any]:
        """The available tools the model can use: those whose required capabilities it has."""
        tools = self.available_tools()
        if not any(getattr(tool, "requires", None) for tool in tools):
            return tools
        capabilities = await self.client.capabilities(self.model)
        return [tool for tool in tools if getattr(tool, "requires", frozenset()) <= capabilities]

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

    @staticmethod
    def _format_tools(tools: list[Any]) -> list[dict[str, Any]]:
        """Collect valid tool definitions for the controller."""
        formatted_tools: list[dict[str, Any]] = []
        for tool in tools:
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
        for something the user said. The trajectory comes after the user's message, so
        the model reads the last observation last, and the images tools returned are sent
        along, so it can observe them before choosing its next action.

        A server answering nothing to the schema (e.g. Ollama Cloud) is asked again with
        the JSON shape spelled out in the instructions instead, and so is every later
        step of that model, without trying the schema first.
        """
        if self.ui_handler:
            await self.ui_handler.start_spinner("Thinking...")
        payload = _with_images(messages, controller.images())
        response = None
        if self.model not in self._unconstrained_models:
            response = await self._chat(
                [
                    *_with_instructions(payload, controller.plan_instructions()),
                    *controller.trajectory(),
                ],
                [],
                stream=False,
                response_format=controller.schema(),
                options=PLAN_OPTIONS,
            )
            if not response.response.strip():
                self._unconstrained_models.add(self.model)
                response = None
        if response is None:
            instructions = f"{controller.plan_instructions()}\n\n{controller.json_instructions()}"
            response = await self._chat(
                [*_with_instructions(payload, instructions), *controller.trajectory()],
                [],
                stream=False,
                options=PLAN_OPTIONS,
            )
        decision = controller.parse(response.response)
        if self.ui_handler:
            await self.ui_handler.stop_spinner()
            args = f" {json.dumps(decision.args, ensure_ascii=False)}" if decision.args else ""
            await self.ui_handler.on_thinking_chunk(
                f"{decision.thought}\n→ {decision.action}{args}\n\n"
            )
        return decision

    async def _answer(
        self, messages: list[dict[str, Any]], controller: ReActController
    ) -> Response:
        """Stream the reply to the user, without tools, from what the steps gathered."""
        if self.ui_handler:
            await self.ui_handler.start_spinner("Thinking...")
        instructions = controller.answer_instructions()
        payload = _with_images(messages, controller.images())
        payload = _with_instructions(payload, instructions) if instructions else payload
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

        Each step is a ReAct Thought -> Action -> Observation cycle. The loop ends when the
        model chooses the final answer, or once a budget is spent: ``max_turns`` planned
        steps, or the controller's tool-call budgets. With the ReAct feature disabled, or
        no tool available, the loop is skipped and the model answers right away.

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

        self.read_documents = []
        current_messages = self._prepare_messages(prompt, messages, system_prompt)
        formatted_tools = self._format_tools(await self._usable_tools())
        controller = ReActController(formatted_tools)
        if not self.features.is_enabled(REACT) or not formatted_tools:
            return await self._answer(current_messages, controller)

        for _ in range(self.max_turns):
            if controller.exhausted():
                break
            if self.ui_handler:
                await self.ui_handler.start_spinner("Thinking...")
            decision = await self._plan(current_messages, controller)
            if controller.finishes(decision):
                break
            if reason := controller.check(decision):
                controller.record(decision, "rejected", f"Rejected: {reason}")
                continue
            status, observation, images = await self._run_tool(decision)
            controller.record(decision, status, observation, images)

        return await self._answer(current_messages, controller)
