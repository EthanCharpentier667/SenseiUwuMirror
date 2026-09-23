"""Sensai: LLM chatbot with unlimited functionalities."""

import json

from .requester import get_sensei_response
from .tool.temperature_example import TempToolExample


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    print("Hello from sensei-uwu-mirror!")  # noqa: T201

    temp_tool = TempToolExample()
    print("Temp Tool Definition:", json.dumps(temp_tool.define(), indent=2))  # noqa: T201
    get_sensei_response(
        "Hello, Sensei! What are the current weather conditions and temperature in New York?",
        tools=[temp_tool],
        human_in_the_loop=True,
    )
