"""Tests for the auth wizard."""

from typing import Any

import pytest

from sensai.data.profile.profile import Profile
from sensai.ui.auth import authenticate_user


class MockConsole:
    def print(self, *args: Any, **kwargs: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_authenticate_user_auto_login(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_creds() -> tuple[str, str]:
        return "testuser", "testpwd"

    def fake_login(name: str, pwd: str, db: Any) -> Profile:
        return Profile(name=name, password=pwd, id=1)

    monkeypatch.setattr("sensai.ui.auth.get_saved_credentials", fake_get_creds)
    monkeypatch.setattr("sensai.ui.auth.login", fake_login)

    profile = await authenticate_user(None, MockConsole())  # type: ignore[arg-type]
    assert profile.name == "testuser"


@pytest.mark.asyncio
async def test_authenticate_user_interactive_login_create_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sensai.ui.auth.get_saved_credentials", lambda: (None, None))

    # We say 'y' to create, but it raises. The while loop will continue!
    # So we give it inputs: user, pwd, 'y', user, pwd, 'n' (to break or something,
    # wait no, if it fails it just prints error and loops. So user, pwd, 'y' (fails),
    # user, pwd, 'n' (no break, it will ask for username again. Let's just raise
    # an error on the second prompt to break the loop).
    inputs = ["testuser", "testpwd", "y", "stop"]

    monkeypatch.setattr("sensai.ui.auth.login", lambda *args: None)

    def fake_create(db: Any, name: str, pwd: str) -> Profile:
        raise ValueError("Simulated DB error")

    monkeypatch.setattr("sensai.ui.auth.create_new_profile", fake_create)

    class FakeSession:
        async def prompt_async(self, *_args: Any, **_kwargs: Any) -> str:
            if not inputs:
                return ""
            val = inputs.pop(0)
            if val == "stop":
                raise KeyboardInterrupt
            return val

    monkeypatch.setattr("sensai.ui.auth.PromptSession", FakeSession)

    with pytest.raises(KeyboardInterrupt):
        await authenticate_user(None, MockConsole())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_authenticate_user_auto_login_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_creds() -> tuple[str, str]:
        return "testuser", "testpwd"

    def fake_login(name: str, pwd: str, db: Any) -> Profile | None:
        return None

    monkeypatch.setattr("sensai.ui.auth.get_saved_credentials", fake_get_creds)
    monkeypatch.setattr("sensai.ui.auth.login", fake_login)

    class FakeSession:
        async def prompt_async(self, *_args: Any, **_kwargs: Any) -> str:
            raise KeyboardInterrupt

    monkeypatch.setattr("sensai.ui.auth.PromptSession", FakeSession)

    with pytest.raises(KeyboardInterrupt):
        await authenticate_user(None, MockConsole())  # type: ignore[arg-type]
