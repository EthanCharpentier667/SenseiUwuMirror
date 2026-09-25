"""A module for making requests to the Ollama Sensei API."""

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import dotenv
import requests

dotenv.load_dotenv()

DEFAULT_TIMEOUT = 300

streaming_response_buffer: list[str] = []


class Message:
    """A class to represent a message in the Sensei API."""

    def __init__(self, role: str, content: str, response_time: float) -> None:
        """Initialize the Message object with a role and content.

        Args:
            role (str): The role of the message sender (e.g., "user", "assistant", "tool").
            content (str): The content of the message.
            response_time (float): The time taken to respond, in seconds.
        """
        self.role = role
        self.content = content
        self.response_time = response_time

    def to_dict(self) -> dict[str, Any]:
        """Convert the Message object to a dictionary.

        Returns:
            dict[str, Any]: A dictionary representation of the Message object.
        """
        return {"role": self.role, "content": self.content, "response_time": self.response_time}


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


def _response_from_json(
    data: dict[str, Any], payload: dict[str, Any], request_time: float, status_code: int
) -> Response:
    """Build a Response from a non-streamed Sensei API JSON payload."""
    message = data.get("message", {})
    respond_time = time.time()
    reply = message.get("content", "")
    prompt_eval_count = data.get("prompt_eval_count", 0)
    eval_count = data.get("eval_count", 0)
    return Response(
        response=reply,
        respond_time=respond_time,
        request_time=request_time,
        total_duration=data.get("total_duration", 0),
        model=payload.get("model", ""),
        tools=payload.get("tools", []),
        messages=_messages_with_reply(
            payload.get("messages", []), reply, request_time, respond_time
        ),
        prompt_eval_count=prompt_eval_count,
        eval_count=eval_count,
        token_used=prompt_eval_count + eval_count,
        status_code=status_code,
        tool_calls=message.get("tool_calls", []),
        stop_reason=data.get("done_reason", ""),
    )


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
) -> Response:
    """Make a POST request to the specified URL with the given payload.

    Args:
        url (str): The URL to send the request to.
        payload (dict): The data to send in the request body.
        headers (dict, optional): Additional headers to include in the request. Default is None.
        stream (bool): Whether to stream the response. Default is False.
        timeout (float): The maximum time to wait for a response, in seconds. Default is 300s.

    Returns:
        Response: The response from the server.

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
        return _response_from_json(response.json(), payload, request_time, response.status_code)

    full_response = ""
    done_reason = ""
    eval_count = 0
    prompt_eval_count = 0
    total_duration = 0
    tool_calls = []
    streaming_response_buffer.clear()
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
    token_used = prompt_eval_count + eval_count
    respond_time = time.time()
    return Response(
        response=full_response,
        respond_time=respond_time,
        request_time=request_time,
        total_duration=total_duration,
        model=payload.get("model", ""),
        tools=payload.get("tools", []),
        messages=_messages_with_reply(
            payload.get("messages", []), full_response, request_time, respond_time
        ),
        prompt_eval_count=prompt_eval_count,
        eval_count=eval_count,
        token_used=token_used,
        status_code=response.status_code,
        tool_calls=tool_calls,
        stop_reason=done_reason,
    )


def call_tool(
    toolcalls: list[dict[str, Any]],
    response: Response,
    messages: list[dict[str, Any]],
    tools: list[Any] | None = None,
) -> Response:
    """Call the appropriate tool based on the provided tool calls.

    Args:
        toolcalls (list): A list of tool call dictionaries.
        response (Response): The response from the Sensei API.
        messages (list): The list of messages in the conversation.
        tools (list, optional): A list of available tools. Default is None.

    Returns:
        Response: The updated response after executing the tool calls.
    """
    if not tools or not toolcalls:
        return response

    conversation = [
        *messages,
        {"role": "assistant", "content": response.response, "tool_calls": toolcalls},
    ]
    for tool_call in toolcalls:
        print(f"Calling tool: {tool_call.get('function', {}).get('name', 'unknown')}")  # noqa: T201
        function = tool_call.get("function", {})
        for tool in tools:
            if tool.name == function.get("name"):
                tool_response = tool.execute(**function.get("arguments", {}))
                content = (
                    tool_response if isinstance(tool_response, str) else json.dumps(tool_response)
                )
                conversation.append({"role": "tool", "content": content})
    return get_sensei_response(
        messages=conversation,
        model=response.model,
        tools=tools,
        stream=True,
    )


def get_sensei_response(
    prompt: str | None = None,
    model: str = "llama3.2",
    tools: list[Any] | None = None,
    *,
    messages: list[dict[str, Any]] | None = None,
    stream: bool = True,
) -> Response:
    """Get a response from the Sensei API based on the provided prompt and model.

    Args:
        prompt (str, optional): The input prompt for the Sensei model.
            Ignored if ``messages`` is given.
        model (str): The model to use for generating the response. Default is "llama3.2".
        tools (list, optional): A list of tools to use with the model. Default is None.
        messages (list, optional): The full conversation history to send.
            Overrides ``prompt`` when given.
        stream (bool): Whether to stream the response. Default is True.

    Returns:
        Response: The response from the Sensei API.

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
        "stream": stream,
    }
    print(f"Sending request to {url} with payload: {json.dumps(payload)}")  # noqa: T201
    reponse = make_request(url, payload, headers=headers, stream=stream)
    return call_tool(reponse.tool_calls, reponse, messages, tools)
