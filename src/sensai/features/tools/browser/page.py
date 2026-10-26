"""The browser shared by the browser tools: one Chrome page, opened on first use.

The page stays open between tool calls, so a page opened by ``browser_navigate`` is the
one ``browser_click`` acts on. The app closes it as it exits (``close_browser``).
"""

import contextlib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Browser, Error, Locator, Page, Playwright, async_playwright

MAX_SNAPSHOT_CHARS = 15_000
NAVIGATION_TIMEOUT_MS = 15_000
ACTION_TIMEOUT_MS = 5_000
NO_PAGE_ERROR = "No page is open. Use browser_navigate first."
REF_DESCRIPTION = "The element's ref, written as [ref=e12] in the latest snapshot: e12"
CLICKABLE_ROLES = ("button", "link", "checkbox", "radio", "tab", "menuitem", "option", "switch")
FIELD_ROLES = ("textbox", "searchbox", "combobox", "spinbutton")
TARGET_ERROR = "Give the element's name (as the snapshot quotes it) or its ref."
_REF = re.compile(r"(?:f\d+)?e\d+")
_NOISE = re.compile(r" \[(?:cursor=pointer|active)\]")


@dataclass
class _Session:
    """A running browser and its page."""

    playwright: Playwright
    browser: Browser
    page: Page


@dataclass
class _State:
    session: _Session | None = None


_STATE = _State()


def is_web_url(url: str) -> bool:
    """Whether a URL is an absolute HTTP(S) one: never a local file (``file://``)."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def current_page() -> Page | None:
    """The open page, or None if none was opened (or the user closed it)."""
    session = _STATE.session
    if session is None or session.page.is_closed():
        return None
    return session.page


async def open_page() -> Page:
    """The open page, launching the user's Chrome (visible) if none is open yet."""
    if page := current_page():
        return page
    await close_browser()
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(channel="chrome", headless=False)
    except Error:
        await playwright.stop()
        raise
    _STATE.session = _Session(playwright, browser, await browser.new_page())
    return _STATE.session.page


async def close_browser() -> None:
    """Close the browser, then stop Playwright. Does nothing if no browser is open."""
    session, _STATE.session = _STATE.session, None
    if session is None:
        return
    with contextlib.suppress(Error):
        await session.browser.close()
    with contextlib.suppress(Error):
        await session.playwright.stop()


def parse_ref(raw: str) -> str | None:
    """The snapshot ref the model meant, or None if it isn't one.

    Snapshots write ``[ref=e12]`` (``f1e12`` inside an iframe); models also pass it as
    ``[ref=e12]`` or ``ref=e12``. A bare number is refused, not read as ``e12``: models
    write one when they guess a ref, and it names an unrelated element (``e1`` is the
    page's body).
    """
    text = raw.strip().strip("[]").strip().removeprefix("ref=")
    return text if _REF.fullmatch(text) else None


async def find(page: Page, ref: str | None) -> Locator | None:
    """The element a snapshot names ``[ref=…]``, or None if the page has none."""
    if ref is None:
        return None
    locator = page.locator(f"aria-ref={ref}")
    return locator if await locator.count() else None


async def _by_name(page: Page, name: str, roles: tuple[str, ...]) -> list[Locator]:
    """The elements of these roles with this accessible name: exact matches if any."""
    for exact in (True, False):
        found: list[Locator] = []
        for role in roles:
            aria_role: Any = role  # Playwright types it as a Literal of every ARIA role
            locator = page.get_by_role(aria_role, name=name, exact=exact)
            found += [locator.nth(index) for index in range(await locator.count())]
        if found:
            return found
    return []


async def target(
    page: Page, ref: object, name: object, roles: tuple[str, ...]
) -> Locator | dict[str, Any]:
    """The element to act on, by its ref, else by its name, or the error to return.

    The name is the one the snapshot quotes (``textbox "Email"``): models give it far
    more reliably than a ref, which they tend to guess. The ref still tells apart two
    elements with the same name.
    """
    if isinstance(ref, str) and (found := await find(page, parse_ref(ref))):
        return found
    if isinstance(name, str) and name.strip():
        matches = await _by_name(page, name.strip(), roles)
        if len(matches) == 1:
            return matches[0]
        if matches:
            return await _not_found(
                page,
                f"{len(matches)} elements are named {name!r}: pass the ref of the one you mean.",
            )
        return await _not_found(page, f"No element is named {name!r}.")
    return await _not_found(page, f"No element has ref {ref!r}.")


async def _not_found(page: Page, reason: str) -> dict[str, Any]:
    """The error for an element that couldn't be found, with the page to try again."""
    return {
        "error": (
            f"{reason} Nothing was done. Pass the element's name as the page below quotes "
            'it (e.g. Email for textbox "Email"), or its ref (e23 for [ref=e23]).'
        ),
        "page": await page_state(page),
    }


async def settle(page: Page) -> None:
    """Wait for a page an action may have reloaded to be ready, without failing on it."""
    with contextlib.suppress(Error):
        await page.wait_for_load_state("domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)


async def snapshot(page: Page) -> str:
    """The page as an accessibility tree: what the model reads to pick its next action.

    Each element it can act on carries a ``[ref=…]``, to pass to the other tools. Hints
    meant for mouse users (``[cursor=pointer]``, ``[active]``) are dropped, and the
    snapshot is cut to fit the agent's observation limit.
    """
    text = _NOISE.sub("", await page.locator("body").aria_snapshot(mode="ai"))
    if len(text) <= MAX_SNAPSHOT_CHARS:
        return text
    return f"{text[:MAX_SNAPSHOT_CHARS]}\n[… {len(text) - MAX_SNAPSHOT_CHARS} characters cut]"


async def page_state(page: Page) -> str:
    """Where the page is and what it shows, after an action.

    Plain text rather than a dict: a dict reaches the model as JSON, where the
    snapshot's quotes and line breaks are escaped, longer and harder to read.
    """
    return f"URL: {page.url}\nTitle: {await page.title()}\n\n{await snapshot(page)}"
