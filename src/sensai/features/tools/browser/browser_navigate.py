"""Open a web page in the browser, returning its title and snapshot."""

from typing import Any

from playwright.async_api import Error

from sensai.features.tools.tool import Tool

from .page import NAVIGATION_TIMEOUT_MS, is_web_url, open_page, page_state


class BrowserNavigate(Tool):
    """Tool opening a URL in the browser, launching it if needed."""

    def __init__(self) -> None:
        """Initialize the BrowserNavigate tool definition."""
        super().__init__(
            name="browser_navigate",
            group="browser",
            description=(
                "Open a web page in the user's browser (launching it if needed), to test a "
                "website or web app like a user would. Returns the page's title and a "
                "snapshot of its content, where each element you can act on has a [ref=…] "
                "to pass to browser_click or browser_type."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string", "description": "The http(s) URL to open"}},
            },
            safe=True,
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any] | str:
        """Open the URL and describe the page.

        Args:
            *_args: Unused positional arguments.
            **kwargs: ``url``, an absolute http(s) URL.

        Returns:
            dict[str, Any] | str: The page's URL, title and snapshot as text, or an error.
        """
        url = kwargs.get("url")
        if not isinstance(url, str) or not is_web_url(url):
            return {"url": url, "error": "Invalid URL. Must be an absolute http(s) URL."}
        try:
            page = await open_page()
            await page.goto(url, timeout=NAVIGATION_TIMEOUT_MS)
            return await page_state(page)
        except Error as e:
            return {"url": url, "error": str(e)}
