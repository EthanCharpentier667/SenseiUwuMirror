"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio

from .agent import Agent
from .client import OllamaClient
from .tools.registry import get_all_tools
from .ui import AsyncUIHandler, CLIHandler

__all__ = ["Agent", "AsyncUIHandler", "CLIHandler", "OllamaClient", "main"]


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    print("Hello from sensei-uwu-mirror!")  # noqa: T201
    ui_handler = CLIHandler()
    agent = Agent(
        tools=get_all_tools(),
        human_in_the_loop=True,
        ui_handler=ui_handler,
    )
    await agent.run("Hello, Sensei! Who is Sweetie Fox ?")


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
