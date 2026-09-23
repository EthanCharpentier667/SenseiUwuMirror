"""Tests for the tool registry."""

from sensai.tools.registry import get_all_tools
from sensai.tools.temperature_example import TempToolExample
from sensai.tools.web_search import WebSearch


def test_get_all_tools_returns_tool_instances() -> None:
    tools = get_all_tools()

    assert len(tools) == 2
    assert isinstance(tools[0], WebSearch)
    assert isinstance(tools[1], TempToolExample)
