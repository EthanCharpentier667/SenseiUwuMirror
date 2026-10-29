"""Tests for the ``sensai.features.tools.tool`` module."""

from typing import Any

import pytest

from sensai.features.tools.tool import Tool, is_failure


class ConcreteTool(Tool):
    """Minimal concrete tool used to exercise the abstract base class."""

    def __init__(self) -> None:
        """Initialize the concrete test tool."""
        super().__init__(
            name="noop",
            description="Does nothing.",
            tool_type="function",
            parameters={"type": "object", "properties": {}},
        )

    def execute(self, *_args: Any, **_kwargs: Any) -> str:
        return "executed"


def test_tool_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Tool(name="x", description="y", tool_type="function", parameters={})  # type: ignore[abstract]


def test_tool_init_sets_attributes() -> None:
    tool = ConcreteTool()

    assert tool.name == "noop"
    assert tool.description == "Does nothing."
    assert tool.type == "function"
    assert tool.parameters == {"type": "object", "properties": {}}
    assert tool.show_output is False
    assert tool.group == "misc"


def test_tool_define_returns_openai_style_schema() -> None:
    tool = ConcreteTool()

    assert tool.define() == {
        "type": "function",
        "function": {
            "name": "noop",
            "description": "Does nothing.",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def test_tool_execute_runs_subclass_implementation() -> None:
    tool = ConcreteTool()

    assert tool.execute() == "executed"


@pytest.mark.parametrize(
    ("result", "failed"),
    [
        ({"error": "boom"}, True),
        ({"exit_code": 1, "output": ""}, True),
        ({"exit_code": 0, "output": "ok"}, False),
        ({"status": "running", "output": ""}, False),
        ({"error": ""}, False),
        ("plain text", False),
        (None, False),
    ],
)
def test_is_failure_detects_errors_and_non_zero_exit_codes(result: Any, *, failed: bool) -> None:
    assert is_failure(result) is failed
