"""A module for making requests to the Ollama Sensei API."""

import json
import os
import time
from typing import Any, cast

import dotenv
import httpx

from sensai.events import AsyncUIHandler

dotenv.load_dotenv()

DEFAULT_TIMEOUT = 300

streaming_response_buffer: list[str] = []


def get_buffered_response() -> str:
    """Get a buffered response from the Sensei API and delete the buffer."""
    value_to_return = "".join(streaming_response_buffer)
    streaming_response_buffer.clear()
    return value_to_return


async def make_request(  # noqa: PLR0913
    url: str,
    payload: dict[str, Any],
    headers: dict[str, Any] | None = None,
    *,
    stream: bool = False,
    timeout: float = DEFAULT_TIMEOUT,  # noqa: ASYNC109
    ui_handler: AsyncUIHandler | None = None,
) -> dict[str, Any]:
    """Make a POST request to the specified URL with the given payload."""
    request_time = time.time()
    request_headers = {"Content-Type": "application/json"}
    if headers is not None:
        request_headers.update(headers)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if not stream:
            response = await client.post(url, headers=request_headers, json=payload)
            response.raise_for_status()
            return cast("dict[str, Any]", response.json())

        full_response = ""
        done_reason = ""
        eval_count = 0
        prompt_eval_count = 0
        total_duration = 0
        tool_calls = []

        async with client.stream("POST", url, headers=request_headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                message = chunk.get("message", {})
                text = message.get("content", "")

                if text and ui_handler:
                    await ui_handler.on_stream_chunk(text)

                full_response += text
                streaming_response_buffer.append(text)

                if message.get("tool_calls"):
                    tool_calls.extend(message["tool_calls"])

                if chunk.get("done"):
                    done_reason = chunk.get("done_reason", "")
                    eval_count = chunk.get("eval_count", 0)
                    prompt_eval_count = chunk.get("prompt_eval_count", 0)
                    total_duration = chunk.get("total_duration", 0)
                    break

    return {
        "response": full_response,
        "respond_time": time.time() - request_time,
        "request_time": request_time,
        "total_duration": total_duration,
        "model": payload.get("model", ""),
        "tools": payload.get("tools", []),
        "messages": payload.get("messages", []),
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "token_used": eval_count + prompt_eval_count,
        "status_code": response.status_code,
        "tool_calls": tool_calls,
        "stop_reason": done_reason,
    }


async def get_sensei_response(  # noqa: C901, PLR0912, PLR0913
    prompt: str | None = None,
    model: str = "llama3.2",
    tools: list[Any] | None = None,
    *,
    messages: list[dict[str, Any]] | None = None,
    human_in_the_loop: bool = False,
    ui_handler: AsyncUIHandler | None = None,
) -> dict[str, Any]:
    """Get a response from the Sensei API iteratively resolving tools."""
    url = "https://ollama.tanouminou.com/api/chat"
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("API token not found in environment variables.")
    if messages is None:
        if prompt is None:
            raise ValueError("Either prompt or messages must be provided.")
        messages = [{"role": "user", "content": prompt}]

    headers = {"Authorization": f"Bearer {token}"}
    formatedtools = [tool.define() for tool in tools or []]

    current_messages = list(messages)

    while True:
        payload = {
            "messages": current_messages,
            "model": model,
            "tools": formatedtools,
            "stream": True,
        }

        try:
            response = await make_request(
                url, payload, headers=headers, stream=True, ui_handler=ui_handler
            )
        except Exception as e:
            if ui_handler:
                await ui_handler.on_error(e)
            raise

        tool_calls = response.get("tool_calls", [])
        if not tool_calls:
            return response

        current_messages.append(
            {"role": "assistant", "content": response.get("response", ""), "tool_calls": tool_calls}
        )

        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            fn_name = function.get("name", "")
            fn_args = function.get("arguments", {})

            if human_in_the_loop:
                approved = True
                if ui_handler:
                    approved = await ui_handler.on_tool_call_request(fn_name, fn_args)
                if not approved:
                    current_messages.append(
                        {"role": "tool", "content": "Action cancelled by user."}
                    )
                    continue

            tool_executed = False
            for tool in tools or []:
                if tool.name == fn_name:
                    tool_response = tool.execute(**fn_args)
                    content = (
                        tool_response
                        if isinstance(tool_response, str)
                        else json.dumps(tool_response)
                    )
                    current_messages.append({"role": "tool", "content": content})
                    if ui_handler:
                        await ui_handler.on_tool_call_result(fn_name, tool_response)
                    tool_executed = True
                    break

            if not tool_executed:
                current_messages.append({"role": "tool", "content": f"Tool '{fn_name}' not found."})
