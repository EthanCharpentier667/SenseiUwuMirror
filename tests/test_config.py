"""Tests for the ``sensai.config`` module."""

import sys
from pathlib import Path

import pytest

from sensai.config import (
    DEFAULT_COMPRESSION_TOKEN_THRESHOLD,
    DEFAULT_DB_NAME,
    DEFAULT_DB_PATH,
    DEFAULT_MODEL,
    Config,
)


def test_config_uses_defaults_when_no_arguments_are_given() -> None:
    config = Config()
    config.parse_args([])

    assert config.model == DEFAULT_MODEL
    assert config.db_path == DEFAULT_DB_PATH
    assert config.db_name == DEFAULT_DB_NAME
    assert config.compression_threshold == DEFAULT_COMPRESSION_TOKEN_THRESHOLD


def test_config_parses_provided_arguments(tmp_path: Path) -> None:
    db_path = tmp_path / "data"
    config = Config()
    config.parse_args(
        [
            "--model",
            "llama3.1",
            "--reasoning-mode",
            "plan",
            "--db-path",
            str(db_path),
            "--db-name",
            "custom.db",
            "--compression-threshold",
            "42",
        ]
    )

    assert config.model == "llama3.1"
    assert config.reasoning_mode == "plan"
    assert config.db_path == str(db_path)
    assert config.db_name == "custom.db"
    assert config.compression_threshold == 42


def test_config_rejects_an_unknown_reasoning_mode() -> None:
    config = Config()

    with pytest.raises(SystemExit) as exc_info:
        config.parse_args(["--reasoning-mode", "guess"])

    assert exc_info.value.code == 2


def test_config_get_args_returns_none_before_parsing() -> None:
    config = Config()

    assert config.get_args() is None


def test_config_get_args_returns_the_parsed_namespace() -> None:
    config = Config()
    parsed = config.parse_args([])

    assert config.get_args() is parsed


def test_config_properties_parse_lazily_when_accessed_without_parse_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Config()
    monkeypatch.setattr(sys, "argv", ["sensai"])

    assert config.model == DEFAULT_MODEL
    assert config.get_args() is not None
