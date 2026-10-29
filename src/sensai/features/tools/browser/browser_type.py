"""Type text into a field of the browser's current page."""

from typing import Any

from playwright.async_api import Error

from sensai.features.tools.tool import Tool

from .page import (
    ACTION_TIMEOUT_MS,
    FIELD_ROLES,
    NO_PAGE_ERROR,
    REF_DESCRIPTION,
    TARGET_ERROR,
    current_page,
    page_state,
    settle,
    target,
)


class BrowserType(Tool):
    """Tool filling a field named by the page's snapshot."""

    def __init__(self) -> None:
        """Initialize the BrowserType tool definition."""
        super().__init__(
            name="browser_type",
            group="browser",
            description=(
                "Type text into a field of the page open in the browser (replacing what it "
                "held), given its name as the latest snapshot quotes it (Email for textbox "
                '"Email"), or its ref. Set submit to true to press Enter afterwards, e.g. to '
                "send a form. Returns the page as it is after."
            ),
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["text"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The field's name in the snapshot, e.g. Email",
                    },
                    "ref": {"type": "string", "description": REF_DESCRIPTION},
                    "text": {"type": "string", "description": "The text to type"},
                    "submit": {
                        "type": "boolean",
                        "description": "Press Enter after typing.",
                    },
                },
            },
            safe=False,
        )

    async def execute(self, *_args: Any, **kwargs: Any) -> dict[str, Any] | str:
        """Fill the field, press Enter if asked, then describe the page.

        Args:
            *_args: Unused positional arguments.
            **kwargs: ``name`` (the field's name in the snapshot) or ``ref``, ``text``,
                and ``submit`` to press Enter afterwards.

        Returns:
            dict[str, Any] | str: The page's URL, title and snapshot afterwards, as text,
                or an error.
        """
        ref, name, text = kwargs.get("ref"), kwargs.get("name"), kwargs.get("text")
        if not any(isinstance(value, str) and value.strip() for value in (ref, name)):
            return {"error": TARGET_ERROR}
        if not isinstance(text, str):
            return {"error": "Invalid text. Must be a string."}
        page = current_page()
        if page is None:
            return {"error": NO_PAGE_ERROR}
        try:
            field = await target(page, ref, name, FIELD_ROLES)
            if isinstance(field, dict):
                return field
            await field.fill(text, timeout=ACTION_TIMEOUT_MS)
            if kwargs.get("submit"):
                await field.press("Enter", timeout=ACTION_TIMEOUT_MS)
                await settle(page)
            return await page_state(page)
        except Error as e:
            return {"error": str(e)}
