"""Tests for the ``sensai.persona`` module."""

import json

import pytest

from sensai.persona.manager import get_persona, list_personas, load_personas
from sensai.persona.persona import Persona


@pytest.fixture
def personas_file(tmp_path):
    data = {
        "assistant": {
            "name": "Sensai",
            "description": "A helpful assistant",
            "system_prompt": "You are Sensai.",
        },
        "sensei_wu": {
            "name": "Sensei Wu",
            "description": "A wise master",
            "system_prompt": "You are Sensei Wu.",
        },
    }
    path = tmp_path / "personas.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_load_personas_returns_all_entries(personas_file):
    personas = load_personas(personas_file)
    assert set(personas.keys()) == {"assistant", "sensei_wu"}


def test_load_personas_returns_persona_instances(personas_file):
    personas = load_personas(personas_file)
    assert isinstance(personas["assistant"], Persona)


def test_load_personas_maps_fields_correctly(personas_file):
    personas = load_personas(personas_file)
    p = personas["sensei_wu"]
    assert p.name == "Sensei Wu"
    assert p.description == "A wise master"
    assert p.system_prompt == "You are Sensei Wu."


def test_load_personas_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_personas("nonexistent.json")


def test_load_personas_raises_on_missing_field(tmp_path):
    data = {"bad": {"name": "Bad", "description": "Missing system_prompt"}}
    path = tmp_path / "personas.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="system_prompt"):
        load_personas(str(path))


def test_get_persona_returns_correct_persona(personas_file):
    personas = load_personas(personas_file)
    p = get_persona(personas, "assistant")
    assert p is not None
    assert p.name == "Sensai"


def test_get_persona_returns_none_for_unknown_key(personas_file):
    personas = load_personas(personas_file)
    assert get_persona(personas, "unknown") is None


def test_list_personas_returns_sorted_keys(personas_file):
    personas = load_personas(personas_file)
    assert list_personas(personas) == ["assistant", "sensei_wu"]


def test_persona_is_immutable():
    p = Persona(name="Test", description="desc", system_prompt="prompt")
    with pytest.raises(AttributeError):
        p.name = "other"  # type: ignore[misc]
