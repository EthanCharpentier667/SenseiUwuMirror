"""Sensai: LLM chatbot with unlimited functionalities."""

from .requester import get_sensei_response  # noqa: F401

def main() -> None:
    """Entry point for the ``sensai`` console script."""
    print("Hello from sensei-uwu-mirror!")  # noqa: T201
    get_sensei_response("Hello, Sensei! Can you tell me a joke?", stream=True)  # noqa: F821
