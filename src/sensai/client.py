"""HTTP client for interacting with the Ollama API."""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, cast

import dotenv
import httpx

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
    ) -> dict[str, Any]:
        """Send a chat completion request to Ollama.

        Args:
            messages: List of message turns comprising the conversation.
            model: Name of the Ollama model to invoke.
            tools: Formatted tool definitions to pass to the model.
            stream: Whether to stream the response progressively.
            ui_handler: Optional event handler for progressive streaming chunks.

        Returns:
            Dictionary containing response content, metadata, and token usage.
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

        return {
            "response": parsed.text,
            "respond_time": time.time() - start_time,
            "request_time": start_time,
            "total_duration": parsed.total_duration,
            "model": model,
            "tools": tools or [],
            "messages": messages,
            "prompt_eval_count": parsed.prompt_eval_count,
            "eval_count": parsed.eval_count,
            "token_used": parsed.eval_count + parsed.prompt_eval_count,
            "status_code": parsed.status_code,
            "tool_calls": parsed.tool_calls,
            "stop_reason": parsed.done_reason,
        }
