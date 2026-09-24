"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio

from .cli_handler import CLIHandler
from .requester import get_sensei_response
from .tools.registry import get_all_tools


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    print("Hello from sensei-uwu-mirror!")  # noqa: T201
    ui_handler = CLIHandler()
    await get_sensei_response(
        "Hello, Sensei! Who is Sweetie Fox ?",
        tools=get_all_tools(),
        human_in_the_loop=True,
        ui_handler=ui_handler,
    )


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
