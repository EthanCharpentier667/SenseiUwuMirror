"""HTTP client for interacting with the Ollama API."""

import json
import os
import time
from typing import Any, cast

import dotenv
import httpx

from sensai.ui.protocol import AsyncUIHandler

dotenv.load_dotenv()

DEFAULT_URL = "https://ollama.tanouminou.com/api/chat"
DEFAULT_TIMEOUT = 300.0


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

    async def _parse_stream(
        self,
        response: httpx.Response,
        ui_handler: AsyncUIHandler | None,
    ) -> tuple[str, list[dict[str, Any]], str, int, int, int]:
        """Parse line-delimited JSON stream from the Ollama response."""
        full_text = ""
        tool_calls: list[dict[str, Any]] = []
        done_reason = ""
        eval_count = 0
        prompt_eval_count = 0
        total_duration = 0

        async for line in response.aiter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = chunk.get("message", {})
            text = message.get("content", "")
            if text:
                full_text += text
                if ui_handler:
                    await ui_handler.on_stream_chunk(text)

            if message.get("tool_calls"):
                tool_calls.extend(message["tool_calls"])

            if chunk.get("done"):
                done_reason = chunk.get("done_reason", "")
                eval_count = chunk.get("eval_count", 0)
                prompt_eval_count = chunk.get("prompt_eval_count", 0)
                total_duration = chunk.get("total_duration", 0)
                break

        return full_text, tool_calls, done_reason, eval_count, prompt_eval_count, total_duration

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
                return cast("dict[str, Any]", response.json())

            async with http_client.stream(
                "POST", self.base_url, headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                text, tool_calls, reason, eval_cnt, prompt_cnt, duration = await self._parse_stream(
                    response, ui_handler
                )

        return {
            "response": text,
            "respond_time": time.time() - start_time,
            "request_time": start_time,
            "total_duration": duration,
            "model": model,
            "tools": tools or [],
            "messages": messages,
            "prompt_eval_count": prompt_cnt,
            "eval_count": eval_cnt,
            "token_used": eval_cnt + prompt_cnt,
            "status_code": response.status_code,
            "tool_calls": tool_calls,
            "stop_reason": reason,
        }
