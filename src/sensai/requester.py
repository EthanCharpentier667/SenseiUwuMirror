"""A module for making requests to the Ollama Sensei API."""

import json
import requests
import dotenv
import time

dotenv.load_dotenv()


def make_request(url, payload, headers=None, stream=False):
    """Make a POST request to the specified URL with the given payload.

    Args:
        url (str): The URL to send the request to.
        payload (dict): The data to send in the request body.

    Returns:
        dict: The JSON response from the server.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the request.
    """
    request_time = time.time()
    request_headers = {"Content-Type": "application/json"}
    if headers is not None:
        request_headers.update(headers)
    response = requests.post(url, headers=request_headers, data=json.dumps(payload), stream=stream)
    response.raise_for_status()

    if not stream:
        return response.json()

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
        print(text, end="", flush=True)
        full_response += text
        if chunk.get("done"):
            done_reason = chunk.get("done_reason", "")
            eval_count = chunk.get("eval_count", 0)
            prompt_eval_count = chunk.get("prompt_eval_count", 0)
            context = chunk.get("context", "")
            total_duration = chunk.get("total_duration", 0)
            break
    print()
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


def get_sensei_response(prompt, model="llama3.2", tools=None, stream=True):
    """Get a response from the Sensei API based on the provided prompt and model.

    Args:
        prompt (str): The input prompt for the Sensei model.
        model (str): The model to use for generating the response. Default is "llama3.2".
        tools (list, optional): A list of tools to use with the model. Default is None.

    Returns:
        dict: The JSON response from the Sensei API.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the request.
    """
    url = "https://ollama.tanouminou.com/api/generate"
    token = dotenv.get_key(dotenv.find_dotenv(), "TOKEN")
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
