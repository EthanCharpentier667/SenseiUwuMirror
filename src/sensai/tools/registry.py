"""Registry of the tools available to Sensai."""

from .temperature_example import TempToolExample
from .tool import Tool
from .web_search import WebSearch


def get_all_tools() -> list[Tool]:
    """Create all tools that can be passed to the language model.

    Returns:
        list[Tool]: Instantiated tools ready to be defined and executed.
    """
    return [WebSearch(), TempToolExample()]
