"""Tests for the browser tools, against a fake Playwright: no real browser is launched."""

import base64
from dataclasses import dataclass, field
from typing import Any

import pytest
from playwright.async_api import Error

from sensai.features.tools.browser import page as browser_page
from sensai.features.tools.browser.browser_click import BrowserClick
from sensai.features.tools.browser.browser_navigate import BrowserNavigate
from sensai.features.tools.browser.browser_screenshot import BrowserScreenshot
from sensai.features.tools.browser.browser_snapshot import BrowserSnapshot
from sensai.features.tools.browser.browser_type import BrowserType
from sensai.features.tools.browser.page import NO_PAGE_ERROR, close_browser, parse_ref

SNAPSHOT = '- textbox "Email" [ref=e1]\n- button "Log in" [ref=e2]'
ELEMENTS = [("textbox", "Email"), ("button", "Log in"), ("link", "More"), ("link", "More")]


@dataclass
class FakeLocator:
    page: "FakePage"
    selector: str
    matches: int | None = None

    def _check(self) -> None:
        if not self.matches and self.selector not in {"body", "aria-ref=e1", "aria-ref=e2"}:
            raise Error(f"No element matches {self.selector}")

    async def count(self) -> int:
        if self.matches is not None:
            return self.matches
        return int(self.selector in {"body", "aria-ref=e1", "aria-ref=e2"})

    def nth(self, index: int) -> "FakeLocator":
        return FakeLocator(self.page, f"{self.selector} >> nth={index}", matches=1)

    async def aria_snapshot(self, *, mode: str) -> str:
        self.page.events.append(f"snapshot {mode}")
        return self.page.content

    async def click(self, **options: int) -> None:
        self._check()
        self.page.events.append(f"click {self.selector} {options['timeout']}")
        self.page.url = "https://example.com/home"

    async def fill(self, text: str, **options: int) -> None:
        self._check()
        self.page.events.append(f"fill {self.selector} {text!r} {options['timeout']}")

    async def press(self, key: str, **options: int) -> None:
        self.page.events.append(f"press {self.selector} {key} {options['timeout']}")


@dataclass
class FakePage:
    url: str = "about:blank"
    content: str = SNAPSHOT
    closed: bool = False
    goto_error: str | None = None
    events: list[str] = field(default_factory=list)

    def is_closed(self) -> bool:
        return self.closed

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def get_by_role(self, role: str, *, name: str, exact: bool) -> FakeLocator:
        matches = sum(
            1
            for element_role, element_name in ELEMENTS
            if element_role == role
            and (element_name == name if exact else name.lower() in element_name.lower())
        )
        return FakeLocator(self, f"role={role}[name={name!r}]", matches=matches)

    async def goto(self, url: str, **options: int) -> None:
        if self.goto_error:
            raise Error(self.goto_error)
        self.events.append(f"goto {url} {options['timeout']}")
        self.url = url

    async def title(self) -> str:
        return "Example"

    async def wait_for_load_state(self, state: str, **options: int) -> None:
        self.events.append(f"wait {state} {options['timeout']}")

    async def screenshot(self, *, type: str, quality: int) -> bytes:  # noqa: A002
        self.events.append(f"screenshot {type} {quality}")
        return b"jpeg-bytes"


@dataclass
class FakeBrowser:
    log: list[str]
    pages: list[FakePage] = field(default_factory=list)

    async def new_page(self) -> FakePage:
        self.pages.append(FakePage())
        return self.pages[-1]

    async def close(self) -> None:
        self.log.append("browser.close")


@dataclass
class FakeChromium:
    playwright: "FakePlaywright"

    async def launch(self, **kwargs: Any) -> FakeBrowser:
        self.playwright.log.append(f"launch {kwargs}")
        if self.playwright.launch_error:
            raise Error(self.playwright.launch_error)
        self.playwright.browsers.append(FakeBrowser(self.playwright.log))
        return self.playwright.browsers[-1]


@dataclass
class FakePlaywright:
    log: list[str] = field(default_factory=list)
    browsers: list[FakeBrowser] = field(default_factory=list)
    launch_error: str | None = None

    @property
    def chromium(self) -> FakeChromium:
        return FakeChromium(self)

    async def start(self) -> "FakePlaywright":
        return self

    async def stop(self) -> None:
        self.log.append("playwright.stop")

    @property
    def page(self) -> FakePage:
        return self.browsers[-1].pages[-1]


@pytest.fixture
def playwright(monkeypatch: pytest.MonkeyPatch) -> FakePlaywright:
    fake = FakePlaywright()
    monkeypatch.setattr(browser_page, "async_playwright", lambda: fake)
    monkeypatch.setattr(browser_page, "_STATE", browser_page._State())  # noqa: SLF001
    return fake


@pytest.mark.asyncio
async def test_navigate_opens_a_visible_chrome_once_and_describes_the_page(
    playwright: FakePlaywright,
) -> None:
    tool = BrowserNavigate()

    first = await tool.execute(url="https://example.com")
    second = await tool.execute(url="https://example.com/about")

    assert first == f"URL: https://example.com\nTitle: Example\n\n{SNAPSHOT}"
    assert isinstance(second, str)
    assert second.startswith("URL: https://example.com/about\n")
    assert playwright.log == ["launch {'channel': 'chrome', 'headless': False}"]
    assert "snapshot ai" in playwright.page.events


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["file:///etc/passwd", "example.com", "", None])
async def test_navigate_rejects_what_is_not_a_web_url(playwright: FakePlaywright, url: Any) -> None:
    result = await BrowserNavigate().execute(url=url)

    assert isinstance(result, dict)
    assert "absolute http(s) URL" in result["error"]
    assert playwright.log == []


@pytest.mark.asyncio
async def test_navigate_reports_a_page_that_fails_to_load(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")
    playwright.page.goto_error = "net::ERR_CONNECTION_REFUSED"

    result = await BrowserNavigate().execute(url="http://localhost:9")

    assert result == {"url": "http://localhost:9", "error": "net::ERR_CONNECTION_REFUSED"}


@pytest.mark.asyncio
async def test_navigate_stops_playwright_when_chrome_fails_to_launch(
    playwright: FakePlaywright,
) -> None:
    playwright.launch_error = "Chromium distribution 'chrome' is not found"

    result = await BrowserNavigate().execute(url="https://example.com")

    assert isinstance(result, dict)
    assert result["error"] == "Chromium distribution 'chrome' is not found"
    assert playwright.log[-1] == "playwright.stop"


@pytest.mark.asyncio
async def test_navigate_opens_a_new_browser_once_the_user_closed_the_page(
    playwright: FakePlaywright,
) -> None:
    await BrowserNavigate().execute(url="https://example.com")
    playwright.page.closed = True

    await BrowserNavigate().execute(url="https://example.com")

    assert len(playwright.browsers) == 2
    assert playwright.log[1:3] == ["browser.close", "playwright.stop"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "args"),
    [
        (BrowserSnapshot(), {}),
        (BrowserClick(), {"ref": "e2"}),
        (BrowserType(), {"ref": "e1", "text": "a"}),
        (BrowserScreenshot(), {}),
    ],
)
async def test_page_tools_need_an_open_page(
    playwright: FakePlaywright, tool: Any, args: dict[str, Any]
) -> None:
    assert await tool.execute(**args) == {"error": NO_PAGE_ERROR}
    assert playwright.log == []


@pytest.mark.asyncio
async def test_snapshot_reads_the_open_page_again(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")
    playwright.page.content = '- heading "Welcome"'

    result = await BrowserSnapshot().execute()

    assert result == 'URL: https://example.com\nTitle: Example\n\n- heading "Welcome"'
    assert len(playwright.browsers) == 1


@pytest.mark.asyncio
async def test_snapshot_drops_the_hints_meant_for_mouse_users(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")
    playwright.page.content = '- link "Events" [active] [ref=e4] [cursor=pointer]'

    result = await BrowserSnapshot().execute()

    assert isinstance(result, str)
    assert result.endswith('- link "Events" [ref=e4]')


@pytest.mark.asyncio
async def test_snapshot_cuts_a_long_page(
    playwright: FakePlaywright, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(browser_page, "MAX_SNAPSHOT_CHARS", 10)
    await BrowserNavigate().execute(url="https://example.com")

    result = await BrowserSnapshot().execute()

    assert isinstance(result, str)
    assert result.endswith(f"\n\n{SNAPSHOT[:10]}\n[… {len(SNAPSHOT) - 10} characters cut]")


@pytest.mark.asyncio
async def test_click_acts_on_the_snapshot_ref_and_returns_the_new_page(
    playwright: FakePlaywright,
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    result = await BrowserClick().execute(ref="e2")

    events = playwright.page.events
    assert events.index("click aria-ref=e2 5000") < events.index("wait domcontentloaded 15000")
    assert result == f"URL: https://example.com/home\nTitle: Example\n\n{SNAPSHOT}"


@pytest.mark.parametrize(
    ("raw", "ref"),
    [
        ("e12", "e12"),
        ("[ref=e12]", "e12"),
        ("ref=e12", "e12"),
        (" e12 ", "e12"),
        ("12", None),
        ("ref=12", None),
        ("f1e3", "f1e3"),
        ("button[type='submit']", None),
        ("Log in", None),
    ],
)
def test_parse_ref_reads_the_ways_models_write_a_ref(raw: str, ref: str | None) -> None:
    assert parse_ref(raw) == ref


@pytest.mark.asyncio
async def test_click_accepts_a_ref_written_like_the_snapshot(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    await BrowserClick().execute(ref="[ref=e2]")

    assert "click aria-ref=e2 5000" in playwright.page.events


@pytest.mark.asyncio
@pytest.mark.parametrize("ref", ["e99", "2", "button[type='submit']"])
async def test_click_on_an_unknown_ref_returns_the_snapshot_to_retry(
    playwright: FakePlaywright, ref: str
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    result = await BrowserClick().execute(ref=ref)

    assert result == {
        "error": f"No element has ref {ref!r}. Nothing was done. Pass the element's name as "
        'the page below quotes it (e.g. Email for textbox "Email"), or its ref (e23 for '
        "[ref=e23]).",
        "page": f"URL: https://example.com\nTitle: Example\n\n{SNAPSHOT}",
    }
    assert not any(event.startswith("click") for event in playwright.page.events)


@pytest.mark.asyncio
async def test_click_reports_an_element_that_cannot_be_clicked(
    playwright: FakePlaywright, monkeypatch: pytest.MonkeyPatch
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    async def covered(_self: FakeLocator, **_options: int) -> None:
        raise Error("Element is covered by another one")

    monkeypatch.setattr(FakeLocator, "click", covered)

    result = await BrowserClick().execute(ref="e2")

    assert result == {"error": "Element is covered by another one"}


@pytest.mark.asyncio
async def test_type_on_an_unknown_ref_returns_the_snapshot_to_retry(
    playwright: FakePlaywright,
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    result = await BrowserType().execute(ref="ref=15", text="Test Event")

    assert isinstance(result, dict)
    assert result["error"].startswith("No element has ref 'ref=15'. Nothing was done.")
    assert result["page"].endswith(SNAPSHOT)
    assert not any(event.startswith("fill") for event in playwright.page.events)


@pytest.mark.asyncio
@pytest.mark.parametrize("args", [{}, {"ref": " "}, {"name": ""}, {"ref": 3, "name": None}])
async def test_click_needs_a_name_or_a_ref(
    playwright: FakePlaywright, args: dict[str, Any]
) -> None:
    result = await BrowserClick().execute(**args)

    assert result == {"error": "Give the element's name (as the snapshot quotes it) or its ref."}


@pytest.mark.asyncio
async def test_click_finds_an_element_by_its_name(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    await BrowserClick().execute(name="Log in")

    assert "click role=button[name='Log in'] >> nth=0 5000" in playwright.page.events


@pytest.mark.asyncio
async def test_a_guessed_ref_falls_back_on_the_name(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    await BrowserType().execute(ref="1", name="Email", text="admin@example.com")

    assert "fill role=textbox[name='Email'] >> nth=0 'admin@example.com' 5000" in (
        playwright.page.events
    )


@pytest.mark.asyncio
async def test_a_partial_name_is_used_when_no_name_matches_exactly(
    playwright: FakePlaywright,
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    await BrowserClick().execute(name="log")

    assert "click role=button[name='log'] >> nth=0 5000" in playwright.page.events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("More", "2 elements are named 'More': pass the ref of the one you mean."),
        ("Sign up", "No element is named 'Sign up'."),
    ],
)
async def test_click_reports_a_name_matching_several_elements_or_none(
    playwright: FakePlaywright, name: str, reason: str
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    result = await BrowserClick().execute(name=name)

    assert isinstance(result, dict)
    assert result["error"].startswith(f"{reason} Nothing was done.")
    assert result["page"].endswith(SNAPSHOT)
    assert not any(event.startswith("click") for event in playwright.page.events)


@pytest.mark.asyncio
async def test_type_fills_the_field_and_submits_only_when_asked(
    playwright: FakePlaywright,
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    await BrowserType().execute(ref="e1", text="ethan@epitech.eu")
    await BrowserType().execute(ref="e1", text="ethan@epitech.eu", submit=True)

    events = [event for event in playwright.page.events if event.startswith(("fill", "press"))]
    assert events == [
        "fill aria-ref=e1 'ethan@epitech.eu' 5000",
        "fill aria-ref=e1 'ethan@epitech.eu' 5000",
        "press aria-ref=e1 Enter 5000",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"ref": "", "text": "a"}, "Give the element's name"),
        ({"ref": "e1", "text": 3}, "Invalid text"),
    ],
)
async def test_type_rejects_invalid_arguments(
    playwright: FakePlaywright, args: dict[str, Any], error: str
) -> None:
    result = await BrowserType().execute(**args)

    assert isinstance(result, dict)
    assert error in result["error"]


@pytest.mark.asyncio
async def test_screenshot_shows_the_page_as_an_image(playwright: FakePlaywright) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    result = await BrowserScreenshot().execute()

    assert result == {
        "message": "Screenshot of https://example.com.",
        "images": [base64.b64encode(b"jpeg-bytes").decode("ascii")],
    }
    assert "screenshot jpeg 80" in playwright.page.events


@pytest.mark.asyncio
async def test_close_browser_closes_the_browser_then_stops_playwright(
    playwright: FakePlaywright,
) -> None:
    await BrowserNavigate().execute(url="https://example.com")

    await close_browser()
    await close_browser()

    assert playwright.log[1:] == ["browser.close", "playwright.stop"]
    assert await BrowserSnapshot().execute() == {"error": NO_PAGE_ERROR}


def test_tools_declare_their_safety_and_needs() -> None:
    assert BrowserNavigate().safe
    assert BrowserSnapshot().safe
    assert BrowserSnapshot().repeatable
    assert not BrowserClick().safe
    assert not BrowserType().safe
    assert BrowserScreenshot().requires == {"vision"}
    assert BrowserScreenshot().repeatable
