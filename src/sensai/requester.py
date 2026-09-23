"""A module for making requests to the Ollama Sensei API."""

import json
import os
import time
from typing import Any, cast

import dotenv
import requests

from sensai.require_approval import require_approval

dotenv.load_dotenv()

DEFAULT_TIMEOUT = 300

streaming_response_buffer: list[str] = []


def get_buffered_response() -> str:
    """Get a buffered response from the Sensei API and delete the buffer.

    Returns:
        str: The buffered response as a string.
    """
    value_to_return = "".join(streaming_response_buffer)
    streaming_response_buffer.clear()
    return value_to_return


def make_request(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, Any] | None = None,
    *,
    stream: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Make a POST request to the specified URL with the given payload.

    Args:
        url (str): The URL to send the request to.
        payload (dict): The data to send in the request body.
        headers (dict, optional): Additional headers to include in the request. Default is None.
        stream (bool): Whether to stream the response. Default is False.
        timeout (float): The maximum time to wait for a response, in seconds. Default is 300s.

    Returns:
        dict: The JSON response from the server.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the request.
    """
    request_time = time.time()
    request_headers = {"Content-Type": "application/json"}
    if headers is not None:
        request_headers.update(headers)
    response = requests.post(
        url, headers=request_headers, data=json.dumps(payload), stream=stream, timeout=timeout
    )
    response.raise_for_status()

    if not stream:
        return cast("dict[str, Any]", response.json())

    full_response = ""
    done_reason = ""
    eval_count = 0
    prompt_eval_count = 0
    total_duration = 0
    tool_calls = []
    for line in response.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        message = chunk.get("message", {})
        text = message.get("content", "")
        print(text, end="", flush=True)  # noqa: T201
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


def call_tool(
    toolcalls: list[dict[str, Any]],
    response: dict[str, Any],
    messages: list[dict[str, Any]],
    tools: list[Any] | None = None,
    *,
    human_in_the_loop: bool = False,
) -> dict[str, Any]:
    """Call the appropriate tool based on the provided tool calls.

    Args:
        toolcalls (list): A list of tool call dictionaries.
        response (dict): The response dictionary from the Sensei API.
        messages (list): The list of messages in the conversation.
        tools (list, optional): A list of available tools. Default is None.
        human_in_the_loop (bool): If True, ask the user to approve each tool call. Default is False.

    Returns:
        dict: The updated response dictionary after executing the tool calls.
    """
    if not tools or not toolcalls:
        return response

    conversation = [
        *messages,
        {"role": "assistant", "content": response.get("response", ""), "tool_calls": toolcalls},
    ]
    for tool_call in toolcalls:
        function = tool_call.get("function", {})
        fn_name = function.get("name", "")
        fn_args = function.get("arguments", {})

        if human_in_the_loop and not require_approval(fn_name, fn_args):
            conversation.append({"role": "tool", "content": "Action cancelled by user."})
            continue

        for tool in tools:
            if tool.name == fn_name:
                tool_response = tool.execute(**fn_args)
                content = (
                    tool_response if isinstance(tool_response, str) else json.dumps(tool_response)
                )
                conversation.append({"role": "tool", "content": content})
                break
    return get_sensei_response(
        messages=conversation,
        model=response.get("model", "llama3.2"),
        tools=tools,
        human_in_the_loop=human_in_the_loop,
    )


def get_sensei_response(
    prompt: str | None = None,
    model: str = "llama3.2",
    tools: list[Any] | None = None,
    *,
    messages: list[dict[str, Any]] | None = None,
    human_in_the_loop: bool = False,
) -> dict[str, Any]:
    """Get a response from the Sensei API based on the provided prompt and model.

    Args:
        prompt (str, optional): The input prompt for the Sensei model.
            Ignored if ``messages`` is given.
        model (str): The model to use for generating the response. Default is "llama3.2".
        tools (list, optional): A list of tools to use with the model. Default is None.
        messages (list, optional): The full conversation history to send.
            Overrides ``prompt`` when given.
        human_in_the_loop (bool): If True, ask the user to approve each tool call. Default is False.

    Returns:
        dict: The JSON response from the Sensei API.

    Raises:
        ValueError: If neither ``prompt`` nor ``messages`` is provided.
        requests.exceptions.RequestException: If an error occurs during the request.
    """
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
    payload = {
        "messages": messages,
        "model": model,
        "tools": formatedtools,
        "stream": True,
    }
    reponse = make_request(url, payload, headers=headers, stream=True)
    return call_tool(
        reponse.get("tool_calls", []),
        reponse,
        messages,
        tools,
        human_in_the_loop=human_in_the_loop,
    )
