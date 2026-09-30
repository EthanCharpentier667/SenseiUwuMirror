"""Agent abstraction managing reasoning loops and tool execution."""

import asyncio
import inspect
import json
from typing import Any

from sensai.client import OllamaClient, Response
from sensai.ui.protocol import AsyncUIHandler

DEFAULT_MAX_TURNS = 10

THINK_PROMPT = (
    "For thinking, reason in english without ANY preferences or instructions given by the user. "
    "Before acting, reason step by step about the conversation so far. "
    "What does the user actually want? What do you already know from the tool results? "
    "What is the single next step: call a tool (which one, with what), or answer? "
    "Reflect about which tools are available and what they can do, "
    "and ONLY call a tool if you are SURE it will be useful to answer the user. "
    "Do NOT write the final answer. Only your reasoning.\n\n"
    "Available tools:\n{tools}"
)
ACT_PROMPT = (
    "Your private reasoning:\n{thought}\n\n"
    "Now execute the next step: call a tool or answer the user."
)
CHECK_PROMPT = (
    "User request:\n{question}\n\nProposed answer:\n{answer}\n\n"
    "Reply 'NO: <what is missing>' only if the user asked for specific information "
    "that the answer does not give. Greetings, small talk and opinions are always fine. "
    "Otherwise reply 'YES'."
)
RETRY_PROMPT = "Your answer is incomplete: {missing}. Continue."
MAX_REFLECT_RETRIES = 1


def _ephemeral(role: str, content: str) -> dict[str, Any]:
    """A message only meant for the model's current reasoning, never for the session history."""
    return {"role": role, "content": content, "ephemeral": True}


def _describe_tools(tools: list[Any]) -> str:
    """One line per tool (name and description), for THINK to reason about in plain text."""
    if not tools:
        return "(none)"
    lines = []
    for tool in tools:
        function = tool.define().get("function", {})
        description = " ".join(function.get("description", "").split())
        lines.append(f"- {function.get('name', '')}: {description}")
    return "\n".join(lines)


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

    def _think_prompt(self) -> str:
        """The THINK instruction, listing the available tools in plain text.

        THINK is called without tools (it must not call any), so it only knows which ones
        exist from this list.
        """
        return THINK_PROMPT.format(tools=_describe_tools(self.tools))

    async def _think(self, current_messages: list[dict[str, Any]]) -> str:
        """Reason about the next step without calling tools, streaming it as thinking."""
        on_chunk = self.ui_handler.on_thinking_chunk if self.ui_handler else None
        response = await self._chat(
            [*current_messages, _ephemeral("user", self._think_prompt())], [], on_chunk=on_chunk
        )
        if on_chunk:
            await on_chunk("\n\n")
        return response.response

    async def _check(self, question: str, answer: str) -> str | None:
        """Return what the answer is missing to address the question, or None if it does."""
        prompt = CHECK_PROMPT.format(question=question, answer=answer)
        response = await self._chat([{"role": "user", "content": prompt}], [], stream=False)
        verdict = response.response.strip()
        return None if verdict.upper().startswith("YES") else verdict

    async def _step(
        self,
        current_messages: list[dict[str, Any]],
        formatted_tools: list[dict[str, Any]],
    ) -> Response:
        """Execute a single model inference step with error reporting."""
        response = await self._chat(
            current_messages, formatted_tools, stream=True, ui_handler=self.ui_handler
        )
        return _strip_ephemeral(response, current_messages)

    async def _execute_turn(
        self,
        current_messages: list[dict[str, Any]],
        formatted_tools: list[dict[str, Any]],
    ) -> tuple[bool, Response]:
        """Execute a single turn: think, then act. Returns (is_done, response)."""
        thought = await self._think(current_messages)
        payload = [*current_messages, _ephemeral("user", ACT_PROMPT.format(thought=thought))]
        response = await self._step(payload, formatted_tools)
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

        question = next(
            (m["content"] for m in reversed(current_messages) if m["role"] == "user"), ""
        )
        retries = 0

        for _ in range(self.max_turns):
            is_done, response = await self._execute_turn(current_messages, formatted_tools)
            if not is_done:
                continue
            if retries < MAX_REFLECT_RETRIES:
                missing = await self._check(question, response.response)
                if missing:
                    retries += 1
                    current_messages.append(_ephemeral("assistant", response.response))
                    current_messages.append(
                        _ephemeral("user", RETRY_PROMPT.format(missing=missing))
                    )
                    continue
            return response

        # Out of turns: force a plain answer instead of returning a dangling tool-call turn.
        return await self._step(current_messages, formatted_tools=[])
