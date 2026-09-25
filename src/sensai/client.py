"""HTTP client for interacting with the Ollama API."""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, cast

import dotenv
import httpx

from sensai.data.session.message import Message
from sensai.ui.protocol import AsyncUIHandler

dotenv.load_dotenv()

DEFAULT_URL = "https://ollama.tanouminou.com/api/chat"
DEFAULT_TIMEOUT = 300.0


@dataclass
class ChatResult:
    """Internal container for parsed Ollama responses."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    done_reason: str = ""
    eval_count: int = 0
    prompt_eval_count: int = 0
    total_duration: int = 0
    status_code: int = 200


def _messages_from_payload(
    payload_messages: list[dict[str, Any]], request_time: float, respond_time: float
) -> list[Message]:
    """Build the Message history from a request payload's raw messages.

    A user message was sent at request_time; any other role (assistant, tool)
    only became available once the response came back, at respond_time.
    """
    return [
        Message(
            role=message.get("role", "unknown"),
            content=message.get("content", ""),
            response_time=request_time if message.get("role") == "user" else respond_time,
        )
        for message in payload_messages
    ]


def _messages_with_reply(
    payload_messages: list[dict[str, Any]], reply: str, request_time: float, respond_time: float
) -> list[Message]:
    """Build the full Message history for this exchange, including the assistant's reply.

    ``_messages_from_payload`` only echoes what was sent; the assistant's own reply text
    is only known once the response comes back, so it's appended here as a final message
    (skipped when empty, e.g. a tool-call-only turn with no text yet).
    """
    messages = _messages_from_payload(payload_messages, request_time, respond_time)
    if reply:
        messages.append(Message(role="assistant", content=reply, response_time=respond_time))
    return messages


@dataclass
class Response:
    """A response from the Sensei API.

    Attributes:
        response (str): The response text from the Sensei API.
        respond_time (float): The time taken to respond, in seconds.
        request_time (float): The time taken to make the request, in seconds.
        total_duration (float): The total duration of the request and response, in seconds.
        model (str): The model used for generating the response.
        tools (list[Any]): A list of tools used in the request.
        messages (list[Message]): The conversation history exchanged during the request.
        prompt_eval_count (int): The number of prompt evaluations performed.
        eval_count (int): The number of evaluations performed.
        token_used (int): The number of tokens used in the request and response.
        status_code (int): The HTTP status code of the response.
        tool_calls (list[dict[str, Any]]): A list of tool calls made during the request.
        stop_reason (str): The reason for stopping the request, if applicable.
    """

    response: str
    respond_time: float
    request_time: float
    total_duration: float
    model: str
    tools: list[Any]
    messages: list[Message]
    prompt_eval_count: int
    eval_count: int
    token_used: int
    status_code: int
    tool_calls: list[dict[str, Any]]
    stop_reason: str

    def row(self) -> dict[str, Any]:
        """Return the response data as a dictionary.

        Returns:
            dict[str, Any]: A dictionary containing the response data.
        """
        return {
            "response": self.response,
            "respond_time": self.respond_time,
            "request_time": self.request_time,
            "total_duration": self.total_duration,
            "model": self.model,
            "tools": self.tools,
            "messages": self.messages,
            "prompt_eval_count": self.prompt_eval_count,
            "eval_count": self.eval_count,
            "token_used": self.token_used,
            "status_code": self.status_code,
            "tool_calls": self.tool_calls,
            "stop_reason": self.stop_reason,
        }


class OllamaClient:
    """Client responsible for low-level HTTP communication with Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the Ollama client.

        Args:
            base_url: Optional base endpoint URL for the chat API.
            token: Optional bearer authentication token.
            timeout: HTTP request timeout in seconds.
        """
        self.base_url: str = base_url or os.getenv("OLLAMA_URL") or DEFAULT_URL
        self.token = token or os.getenv("TOKEN")
        self.timeout = timeout

    def _build_headers(self) -> dict[str, str]:
        """Construct authorization and content-type headers."""
        if not self.token:
            msg = "API token not found in environment variables."
            raise ValueError(msg)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    async def _consume_chunk(
        self,
        chunk: dict[str, Any],
        result: ChatResult,
        ui_handler: AsyncUIHandler | None,
    ) -> None:
        """Process an individual streaming chunk and update the accumulated result."""
        message = chunk.get("message", {})
        text = message.get("content", "")
        if text:
            result.text += text
            if ui_handler:
                await ui_handler.on_stream_chunk(text)

        if message.get("tool_calls"):
            result.tool_calls.extend(message["tool_calls"])

        if chunk.get("done"):
            result.done_reason = chunk.get("done_reason", "")
            result.eval_count = chunk.get("eval_count", 0)
            result.prompt_eval_count = chunk.get("prompt_eval_count", 0)
            result.total_duration = chunk.get("total_duration", 0)

    async def _parse_stream(
        self,
        response: httpx.Response,
        ui_handler: AsyncUIHandler | None,
    ) -> ChatResult:
        """Parse line-delimited JSON stream from the Ollama response."""
        result = ChatResult(status_code=response.status_code)
        is_done = False

        async for line in response.aiter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "error" in chunk:
                msg = f"Ollama error: {chunk['error']}"
                raise RuntimeError(msg)

            await self._consume_chunk(chunk, result, ui_handler)
            if chunk.get("done"):
                is_done = True
                break

        if not is_done:
            msg = "Incomplete response: stream ended without done event."
            raise RuntimeError(msg)

        return result

    def _parse_non_stream(self, response: httpx.Response) -> ChatResult:
        """Parse complete JSON payload from a non-streaming Ollama response."""
        data = cast("dict[str, Any]", response.json())
        if "error" in data:
            msg = f"Ollama error: {data['error']}"
            raise RuntimeError(msg)

        msg_obj = data.get("message", {})
        return ChatResult(
            text=msg_obj.get("content", ""),
            tool_calls=msg_obj.get("tool_calls", []),
            done_reason=data.get("done_reason", ""),
            eval_count=data.get("eval_count", 0),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            total_duration=data.get("total_duration", 0),
            status_code=response.status_code,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str = "llama3.2",
        tools: list[dict[str, Any]] | None = None,
        *,
        stream: bool = True,
        ui_handler: AsyncUIHandler | None = None,
    ) -> Response:
        """Send a chat completion request to Ollama.

        Args:
            messages: List of message turns comprising the conversation.
            model: Name of the Ollama model to invoke.
            tools: Formatted tool definitions to pass to the model.
            stream: Whether to stream the response progressively.
            ui_handler: Optional event handler for progressive streaming chunks.

        Returns:
            Response: The parsed response, including metadata and token usage.
        """
        headers = self._build_headers()
        payload = {
            "messages": messages,
            "model": model,
            "tools": tools or [],
            "stream": stream,
        }

        start_time = time.time()
        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
            if not stream:
                response = await http_client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                parsed = self._parse_non_stream(response)
            else:
                async with http_client.stream(
                    "POST", self.base_url, headers=headers, json=payload
                ) as response:
                    response.raise_for_status()
                    parsed = await self._parse_stream(response, ui_handler)

        respond_time = time.time()
        return Response(
            response=parsed.text,
            respond_time=respond_time,
            request_time=start_time,
            total_duration=parsed.total_duration,
            model=model,
            tools=tools or [],
            messages=_messages_with_reply(messages, parsed.text, start_time, respond_time),
            prompt_eval_count=parsed.prompt_eval_count,
            eval_count=parsed.eval_count,
            token_used=parsed.eval_count + parsed.prompt_eval_count,
            status_code=parsed.status_code,
            tool_calls=parsed.tool_calls,
            stop_reason=parsed.done_reason,
        )
