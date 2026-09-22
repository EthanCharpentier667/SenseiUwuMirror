"""A module for making requests to the Ollama Sensei API."""

import json
import os
import time
from typing import Any, cast

import dotenv
import requests

dotenv.load_dotenv()

DEFAULT_TIMEOUT = 30


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
        timeout (float): The maximum time to wait for a response, in seconds. Default is

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
    context = ""
    eval_count = 0
    prompt_eval_count = 0
    total_duration = 0
    for line in response.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        text = chunk.get("response", "")
        print(text, end="", flush=True)  # noqa: T201
        full_response += text
        if chunk.get("done"):
            done_reason = chunk.get("done_reason", "")
            eval_count = chunk.get("eval_count", 0)
            prompt_eval_count = chunk.get("prompt_eval_count", 0)
            context = chunk.get("context", "")
            total_duration = chunk.get("total_duration", 0)
            break
    return {
        "response": full_response,
        "respond_time": time.time() - request_time,
        "request_time": request_time,
        "total_duration": total_duration,
        "model": payload.get("model", ""),
        "tools": payload.get("tools", []),
        "prompt": payload.get("prompt", ""),
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "token_used": eval_count + prompt_eval_count,
        "status_code": response.status_code,
        "context": context,
        "stop_reason": done_reason,
    }


def get_sensei_response(
    prompt: str, model: str = "llama3.2", tools: list[Any] | None = None, *, stream: bool = True
) -> dict[str, Any]:
    """Get a response from the Sensei API based on the provided prompt and model.

    Args:
        prompt (str): The input prompt for the Sensei model.
        model (str): The model to use for generating the response. Default is "llama3.2".
        tools (list, optional): A list of tools to use with the model. Default is None.
        stream (bool): Whether to stream the response. Default is True.

    Returns:
        dict: The JSON response from the Sensei API.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the request.
    """
    url = "https://ollama.tanouminou.com/api/generate"
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("API token not found in environment variables.")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "prompt": prompt,
        "model": model,
        "tools": tools if tools is not None else [],
        "stream": stream,
    }
    return make_request(url, payload, headers=headers, stream=stream)
