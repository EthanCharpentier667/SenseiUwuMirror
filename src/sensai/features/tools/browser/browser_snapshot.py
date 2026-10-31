"""Read the browser's current page again."""

from typing import Any

from playwright.async_api import Error

from sensai.features.tools.tool import Tool

from .page import NO_PAGE_ERROR, current_page, page_state


class BrowserSnapshot(Tool):
    """Tool describing the page currently open in the browser."""

    def __init__(self) -> None:
        """Initialize the BrowserSnapshot tool definition."""
        super().__init__(
            name="browser_snapshot",
            group="browser",
            description=(
                "Read the page currently open in the browser again: its URL, title and "
                "snapshot, with a [ref=…] on each element you can act on. Use it when the "
                "page may have changed on its own (loading, animations, timers)."
            ),
            tool_type="function",
            parameters={"type": "object", "required": [], "properties": {}},
            safe=True,
            repeatable=True,
        )

    async def execute(self, *_args: Any, **_kwargs: Any) -> dict[str, Any] | str:
        """Describe the open page.

        Args:
            *_args: Unused positional arguments.
            **_kwargs: Unused keyword arguments.

        Returns:
            dict[str, Any] | str: The page's URL, title and snapshot as text, or an error.
        """
        page = current_page()
        if page is None:
            return {"error": NO_PAGE_ERROR}
        try:
            return await page_state(page)
        except Error as e:
            return {"error": str(e)}
