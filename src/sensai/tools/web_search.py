##
## EPITECH PROJECT, 2026
## SenseiUwuMirror
## File description:
## web_search
##


"""Example web tool implementation."""

import json
import os
from typing import Any, cast

import requests

from .tool import Tool

DEFAULT_TIMEOUT = 300
DEFAULT_CODE = 200


class WebSearch(Tool):
    """Web search tool implementation."""

    def __init__(self) -> None:
        """Initialize the Web search tool definition."""
        super().__init__(
            name="web_search",
            description=(
                "Search the web for information. Use this tool only as a last resort, "
                "when you do not know the answer and it cannot be found anywhere in the "
                "conversation, session, or profile context. This includes results from a "
                "previous call to this same tool earlier in the conversation: if that "
                "already answered the question, reuse it instead of searching again. "
                "Never call this for information you already know, can infer, or have "
                "already retrieved."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["query"],
                "properties": {"query": {"type": "string", "description": "The search query"}},
            },
        )

    def execute(self, *_args: Any, **kwargs: Any) -> str:
        """Execute the web tool's functionality.

        This method should be overridden to implement specific web tool behavior.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            str: A message indicating that the web tool has been executed.
        """
        query = kwargs.get("query", "Unknown Query")

        web_search_result = web_search(query)
        return f"Web search result for '{query}': {web_search_result}"


def web_search(query: str) -> dict[str, Any]:
    """Perform a web search using the specified query.

    Args:
        query (str): The search query to perform.

    Returns:
        dict: The JSON response from the web search.
    """
    url = "https://ollama.com/api/web_search"
    token = os.getenv("API_TOKEN")
    if not token:
        return {"message": "Web search is not available."}
    header = {"Authorization": f"Bearer {token}"}
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(header)
    payload: dict[str, str | int] = {
        "query": query,
    }
    response = requests.post(
        url,
        headers=request_headers,
        data=json.dumps(payload),
        timeout=DEFAULT_TIMEOUT,
    )
    if response.status_code != DEFAULT_CODE:
        return {"message": "Web search failed."}
    return cast("dict[str, Any]", response.json())
