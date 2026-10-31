"""Click an element of the browser's current page."""

from typing import Any

from playwright.async_api import Error

from sensai.features.tools.tool import Tool

from .page import (
    ACTION_TIMEOUT_MS,
    CLICKABLE_ROLES,
    NO_PAGE_ERROR,
    REF_DESCRIPTION,
    TARGET_ERROR,
    current_page,
    page_state,
    settle,
    target,
)


class BrowserClick(Tool):
    """Tool clicking an element named by the page's snapshot."""

    def __init__(self) -> None:
        """Initialize the BrowserClick tool definition."""
        super().__init__(
            name="browser_click",
            group="browser",
            description=(
                "Click an element of the page open in the browser (a button, a link…), "
                "given its name as the latest snapshot quotes it (Se connecter for "
                'button "Se connecter"), or its ref. Returns the page as it is after '
                "the click."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": [],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The element's name in the snapshot, e.g. Se connecter",
                    },
                    "ref": {"type": "string", "description": REF_DESCRIPTION},
                },
            },
            safe=False,
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any] | str:
        """Click the element, then describe the page.

        Args:
            *_args: Unused positional arguments.
            **kwargs: ``name``, the element's name in the snapshot, or ``ref``, its ref.

        Returns:
            dict[str, Any] | str: The page's URL, title and snapshot after the click, as
                text, or an error.
        """
        ref, name = kwargs.get("ref"), kwargs.get("name")
        if not any(isinstance(value, str) and value.strip() for value in (ref, name)):
            return {"error": TARGET_ERROR}
        page = current_page()
        if page is None:
            return {"error": NO_PAGE_ERROR}
        try:
            element = await target(page, ref, name, CLICKABLE_ROLES)
            if isinstance(element, dict):
                return element
            await element.click(timeout=ACTION_TIMEOUT_MS)
            await settle(page)
            return await page_state(page)
        except Error as e:
            return {"error": str(e)}
