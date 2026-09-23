"""Sensai: LLM chatbot with unlimited functionalities."""

from .requester import get_sensei_response
from .tools.registry import get_all_tools


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    print("Hello from sensei-uwu-mirror!")  # noqa: T201
    get_sensei_response(
        "Hello, Sensei! Who is Sweetie Fox ?",
        stream=True,
        tools=get_all_tools(),
    )
