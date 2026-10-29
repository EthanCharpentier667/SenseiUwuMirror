"""Tests for the ``sensai.config`` module."""

import sys
from pathlib import Path

import pytest

from sensai.config import (
    DEFAULT_COMPRESSION_TOKEN_THRESHOLD,
    DEFAULT_DB_NAME,
    DEFAULT_DB_PATH,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_PERSONAS_FILE,
    DEFAULT_URL,
    Config,
)


def test_config_uses_defaults_when_no_arguments_are_given() -> None:
    config = Config()
    config.parse_args([])

    assert config.model == DEFAULT_MODEL
    assert config.db_path == DEFAULT_DB_PATH
    assert config.db_name == DEFAULT_DB_NAME
    assert config.compression_threshold == DEFAULT_COMPRESSION_TOKEN_THRESHOLD
    assert config.num_ctx == DEFAULT_NUM_CTX
    assert config.output_schema is None


def test_config_parses_output_schema() -> None:
    config = Config()
    config.parse_args(["--output-schema", '{"type":"object","required":["name"]}'])

    assert config.output_schema == {"type": "object", "required": ["name"]}


@pytest.mark.parametrize("value", ["not json", "[]", "null", '"object"'])
def test_config_rejects_invalid_output_schema(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    config = Config()

    with pytest.raises(SystemExit) as exc:
        config.parse_args(["--output-schema", value])

    assert exc.value.code == 2
    assert "--output-schema" in capsys.readouterr().err


def test_config_parses_provided_arguments(tmp_path: Path) -> None:
    db_path = tmp_path / "data"
    config = Config()
    config.parse_args(
        [
            "--model",
            "llama3.1",
            "--db-path",
            str(db_path),
            "--db-name",
            "custom.db",
            "--compression-threshold",
            "42",
            "--num-ctx",
            "8192",
        ]
    )

    assert config.model == "llama3.1"
    assert config.db_path == str(db_path)
    assert config.db_name == "custom.db"
    assert config.compression_threshold == 42
    assert config.num_ctx == 8192


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


def test_config_persona_defaults_to_none() -> None:
    config = Config()
    config.parse_args([])

    assert config.persona is None


def test_config_personas_file_defaults_to_default_value() -> None:
    config = Config()
    config.parse_args([])

    assert config.personas_file == DEFAULT_PERSONAS_FILE


def test_config_parses_persona() -> None:
    config = Config()
    config.parse_args(["--persona", "sensei_wu"])

    assert config.persona == "sensei_wu"
    assert config.personas_file == DEFAULT_PERSONAS_FILE


def test_config_enables_every_feature_by_default() -> None:
    config = Config()
    config.parse_args([])

    assert config.features.disabled == set()


def test_config_disables_the_features_given_on_the_command_line() -> None:
    config = Config()
    config.parse_args(["--disable", "rag", "react"])

    assert config.features.disabled == {"rag", "react"}
    assert not config.features.is_enabled("rag")
    assert config.features.is_enabled("tools")


def test_config_rejects_an_unknown_feature() -> None:
    config = Config()

    with pytest.raises(SystemExit):
        config.parse_args(["--disable", "teleport"])


def test_config_generation_parameters_defaults() -> None:
    config = Config()
    config.parse_args([])

    assert config.temperature is None
    assert config.top_p is None
    assert config.num_ctx == DEFAULT_NUM_CTX
    assert config.context_length == DEFAULT_NUM_CTX
    assert not config.was_explicitly_set("--temperature")
    assert not config.was_explicitly_set("--top-p")
    assert not config.was_explicitly_set("--num-ctx", "--context-length")


def test_config_parses_generation_parameters() -> None:
    config = Config()
    config.parse_args(["--temperature", "0.7", "--top-p", "0.85", "--context-length", "4096"])

    assert config.temperature == 0.7
    assert config.top_p == 0.85
    assert config.num_ctx == 4096
    assert config.context_length == 4096
    assert config.was_explicitly_set("--temperature")
    assert config.was_explicitly_set("--top-p")
    assert config.was_explicitly_set("--num-ctx", "--context-length")
    assert not config.was_explicitly_set("--model")


def test_config_disables_the_tools_given_on_the_command_line() -> None:
    config = Config()
    config.parse_args(["--disable-tool", "web_search", "web_fetch"])

    assert config.features.disabled_tools == {"web_search", "web_fetch"}


def test_config_embed_url_stays_on_the_default_when_url_changes() -> None:
    config = Config()
    config.parse_args(["--url", "https://ollama.com/api/chat", "--token", "secret"])

    assert config.embed_url == DEFAULT_URL
    assert config.embed_token is None


def test_config_embed_token_falls_back_to_token_on_the_same_url() -> None:
    config = Config()
    config.parse_args(["--token", "secret"])

    assert config.embed_token == "secret"  # noqa: S105


def test_config_parses_embed_url_and_token() -> None:
    config = Config()
    config.parse_args(
        ["--embed-url", "http://localhost:11434/api/chat", "--embed-token", "local", "--token", "x"]
    )

    assert config.embed_url == "http://localhost:11434/api/chat"
    assert config.embed_token == "local"  # noqa: S105
