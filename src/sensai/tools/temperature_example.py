"""Example web tool implementation."""

from typing import Any

import httpx

from .tool import Tool


class TempToolExample(Tool):
    """Example web tool implementation."""

    def __init__(self) -> None:
        """Initialize the temperature tool definition."""
        super().__init__(
            name="get_temperature",
            description="Get the current temperature for a city.",
            tool_type="function",
            parameters={
                "type": "object",
                "required": ["city"],
                "properties": {"city": {"type": "string", "description": "The name of the city"}},
            },
        )

    def execute(self, *_args: Any, **kwargs: Any) -> str:
        """Execute the web tool's functionality.

        This method should be overridden to implement specific web tool behavior.

        Args:
            *_args: Unused positional arguments.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            str: A message indicating that the web tool has been executed.
        """
        city = kwargs.get("city", "Unknown City")
        data = httpx.get(f"https://wttr.in/{city}?format=j1", timeout=10).json()
        condition = data["current_condition"][0]
        return (
            f"The current temperature in {city} is {condition['temp_C']}°C. "
            f"The weather is {condition['weatherDesc'][0]['value']}. "
            f"The humidity is {condition['humidity']}% "
            f"and the wind speed is {condition['windspeedKmph']} km/h."
        )
