"""Show the browser's current page to the model as an image."""

import base64
from typing import Any

from playwright.async_api import Error

from sensai.features.tools.tool import Tool

from .page import NO_PAGE_ERROR, current_page

JPEG_QUALITY = 80


class BrowserScreenshot(Tool):
    """Tool capturing the page open in the browser, for a vision model to look at."""

    def __init__(self) -> None:
        """Initialize the BrowserScreenshot tool definition."""
        super().__init__(
            name="browser_screenshot",
            description=(
                "Capture the page open in the browser as an image, shown to you right "
                "away: to check its rendering (layout, colors, images), which the "
                "snapshot doesn't show."
            ),
            tool_type="function",
            parameters={"type": "object", "required": [], "properties": {}},
            safe=True,
            requires={"vision"},
            repeatable=True,
        )

    async def execute(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """Capture the visible part of the page.

        Args:
            *_args: Unused positional arguments.
            **_kwargs: Unused keyword arguments.

        Returns:
            dict[str, Any]: The page's URL and the image in ``images``, or an error.
        """
        page = current_page()
        if page is None:
            return {"error": NO_PAGE_ERROR}
        try:
            image = await page.screenshot(type="jpeg", quality=JPEG_QUALITY)
        except Error as e:
            return {"error": str(e)}
        encoded = base64.b64encode(image).decode("ascii")
        return {"message": f"Screenshot of {page.url}.", "images": [encoded]}
