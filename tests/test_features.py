"""Tests for the ``sensai.features`` module."""

import pytest

from sensai.features.features import FEATURES, RAG, TOOLS, Features


def test_every_feature_is_enabled_by_default() -> None:
    features = Features()

    assert all(features.is_enabled(name) for name in FEATURES)


def test_features_can_be_disabled_and_enabled_again() -> None:
    features = Features.from_disabled([RAG])

    assert not features.is_enabled(RAG)
    features.set(RAG, enabled=True)
    assert features.is_enabled(RAG)


def test_toggle_flips_a_feature_and_returns_its_new_state() -> None:
    features = Features()

    assert features.toggle(TOOLS) is False
    assert features.disabled == {TOOLS}
    assert features.toggle(TOOLS) is True
    assert features.disabled == set()


def test_unknown_features_are_rejected() -> None:
    features = Features()

    with pytest.raises(ValueError, match="Unknown feature"):
        features.is_enabled("teleport")
    with pytest.raises(ValueError, match="Unknown feature"):
        Features.from_disabled(["teleport"])


def test_single_tools_can_be_disabled_and_toggled() -> None:
    features = Features.from_disabled([], tools=["web_search"])

    assert not features.is_tool_enabled("web_search")
    assert features.is_tool_enabled("web_fetch")
    assert features.toggle_tool("web_search") is True
    assert features.toggle_tool("web_fetch") is False
    assert features.disabled_tools == {"web_fetch"}


def test_several_tools_can_be_set_at_once() -> None:
    features = Features()

    features.set_tools(["browser_click", "browser_type"], enabled=False)
    assert features.disabled_tools == {"browser_click", "browser_type"}
    features.set_tools(["browser_click"], enabled=True)
    assert features.disabled_tools == {"browser_type"}


def test_run_overrides_win_over_saved_choices_but_are_not_saved() -> None:
    features = Features.from_disabled([RAG], tools=["bash_tool"], enabled=[TOOLS])
    features.load_saved([TOOLS, "teleport"], ["web_search"])

    assert features.disabled == {RAG}
    assert features.disabled_tools == {"bash_tool", "web_search"}
    assert features.saved_disabled == {TOOLS}
    assert features.saved_disabled_tools == {"web_search"}


def test_enabled_tools_override_saved_choices() -> None:
    features = Features.from_disabled([], enabled_tools=["web_search"])
    features.load_saved([], ["web_search", "web_fetch"])

    assert features.disabled_tools == {"web_fetch"}


def test_a_runtime_choice_replaces_the_run_override_and_is_saved() -> None:
    features = Features.from_disabled([RAG], tools=["bash_tool"])

    features.set(RAG, enabled=True)
    features.set_tool("bash_tool", enabled=False)

    assert features.is_enabled(RAG)
    assert features.saved_disabled == set()
    assert features.saved_disabled_tools == {"bash_tool"}
    features.set_tool("bash_tool", enabled=True)
    assert features.disabled_tools == set()


def test_unknown_features_to_enable_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown feature"):
        Features.from_disabled([], enabled=["teleport"])
