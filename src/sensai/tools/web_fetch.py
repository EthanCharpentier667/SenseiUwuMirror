##
## EPITECH PROJECT, 2026
## SenseiUwuMirror
## File description:
## web_fetch
##

"""Web fetch tool implementation."""

import os
from typing import Any, cast

import httpx

from sensai.tools.tool import Tool
from sensai.tools.web_search import DEFAULT_CODE

DEFAULT_TIMEOUT = 100


class WebFetch(Tool):
    """Web fetch tool implementation."""

    def __init__(self) -> None:
        """Initialize the Web fetch tool definition."""
        super().__init__(
            name="web_fetch",
            description=(
                "Read a specific web page to answer the user's question about its "
                "readable content, purpose, or available activities. "
                "The result may contain irrelevant CSS, JavaScript, or framework data. "
                "Ignore these technical details unless the user explicitly asks "
                "about the site's implementation. "
                "If the readable content is missing or insufficient, use web_search "
                "to find relevant information and identify the sources used."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
            },
        )

    def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the web fetch tool's functionality.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            dict[str, Any]: The content fetched from the specified URL.
        """
        url = kwargs.get("url", "Unknown URL")

        return fetch_url(url)


def fetch_url(url: str) -> dict[str, Any]:
    """Fetch content from the specified URL.

    Args:
        url (str): The URL to fetch.

    Returns:
        dict[str, Any]: The content fetched from the specified URL.
    """
    url_api = "https://ollama.com/api/web_fetch"
    token = os.getenv("API_TOKEN")
    if not token:
        return {"message": "Web search is not available."}

    request_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload: dict[str, str | int] = {
        "url": url,
    }

    response = httpx.post(
        url_api,
        headers=request_headers,
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    if response.status_code != DEFAULT_CODE:
        return {"message": "Web fetch failed."}
    return cast("dict[str, Any]", response.json())
