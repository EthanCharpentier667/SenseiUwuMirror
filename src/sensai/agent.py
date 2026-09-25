"""Agent abstraction managing reasoning loops and tool execution."""

import asyncio
import inspect
import json
from typing import Any

from sensai.client import OllamaClient, Response
from sensai.ui.protocol import AsyncUIHandler

DEFAULT_MAX_TURNS = 10


class Agent:
    """Autonomous agent executing a ReAct reasoning and tool-use loop."""

    def __init__(
        self,
        model: str = "llama3.2",
        tools: list[Any] | None = None,
        *,
        human_in_the_loop: bool = False,
        ui_handler: AsyncUIHandler | None = None,
        client: OllamaClient,
    ) -> None:
        """Initialize the agent.

        Args:
            model: The Ollama model name to use.
            tools: List of available Tool instances.
            human_in_the_loop: Whether tool calls require manual user approval.
            ui_handler: Event handler for UI presentation.
            client: Optional preconfigured OllamaClient instance.
        """
        self.model = model
        self.tools = tools or []
        self.human_in_the_loop = human_in_the_loop
        self.ui_handler = ui_handler
        self.client = client
        self.max_turns = DEFAULT_MAX_TURNS
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
            if effective_system and not any(m.get("role") == "system" for m in formatted):
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

    async def _dispatch_single_tool(self, name: str, args: dict[str, Any]) -> tuple[bool, Any]:
        """Find and execute a tool by name, running sync tools in a thread."""
        for tool in self.tools:
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

    async def _execute_single_tool_call(self, tool_call: dict[str, Any]) -> str:
        """Process approval and execution for a single tool call."""
        func = tool_call.get("function", {})
        fn_name = func.get("name", "")
        fn_args = func.get("arguments", {})

        if self.human_in_the_loop and self.ui_handler:
            approved = await self.ui_handler.on_tool_call_request(fn_name, fn_args)
            if not approved:
                return "Action cancelled by user."

        try:
            found, res = await self._dispatch_single_tool(fn_name, fn_args)
        except Exception as e:
            if self.ui_handler:
                await self.ui_handler.on_error(e)
            raise

        if not found:
            return f"Tool '{fn_name}' not found."

        if self.ui_handler:
            await self.ui_handler.on_tool_call_result(fn_name, res)

        return res if isinstance(res, str) else json.dumps(res)

    async def _process_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        current_messages: list[dict[str, Any]],
    ) -> None:
        """Execute all tool calls in the turn and append outputs to history."""
        for tool_call in tool_calls:
            content = await self._execute_single_tool_call(tool_call)
            tool_name = tool_call.get("function", {}).get("name", "")
            current_messages.append({"role": "tool", "content": content, "tool_name": tool_name})

    async def _step(
        self,
        current_messages: list[dict[str, Any]],
        formatted_tools: list[dict[str, Any]],
    ) -> Response:
        """Execute a single model inference step with error reporting."""
        try:
            return await self.client.chat(
                messages=current_messages,
                model=self.model,
                tools=formatted_tools,
                stream=True,
                ui_handler=self.ui_handler,
            )
        except Exception as e:
            if self.ui_handler:
                await self.ui_handler.on_error(e)
            raise

    async def _execute_turn(
        self,
        current_messages: list[dict[str, Any]],
        formatted_tools: list[dict[str, Any]],
    ) -> tuple[bool, Response]:
        """Execute a single turn. Returns (is_done, response)."""
        response = await self._step(current_messages, formatted_tools)
        tool_calls = response.tool_calls
        if not tool_calls:
            return True, response

        current_messages.append(
            {
                "role": "assistant",
                "content": response.response,
                "tool_calls": tool_calls,
            }
        )
        await self._process_tool_calls(tool_calls, current_messages)
        return False, response

    async def run(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> Response:
        """Run the ReAct loop until completion or max iterations reached.

        Args:
            prompt: User message prompt.
            messages: Optional conversation history overriding prompt.
            system_prompt: Optional system prompt to override default.

        Returns:
            Final completion response from the model.
        """
        if self.max_turns < 1:
            msg = "max_turns must be at least 1."
            raise ValueError(msg)

        current_messages = self._prepare_messages(prompt, messages, system_prompt)
        formatted_tools = [tool.define() for tool in self.tools]

        response: Response | None = None
        for _ in range(self.max_turns):
            is_done, response = await self._execute_turn(current_messages, formatted_tools)
            if is_done:
                return response

        if response is None:  # pragma: no cover - unreachable, max_turns >= 1 is enforced above
            msg = "Agent loop exited without producing a response."
            raise RuntimeError(msg)
        return response
