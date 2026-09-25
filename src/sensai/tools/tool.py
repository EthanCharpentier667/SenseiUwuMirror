"""Tool interface for the ``sensai`` package."""

from abc import ABC, abstractmethod
from typing import Any

CALL_GUARD_PREFIX = (
    "Only call a tool when the user explicitly asks for that specific information.\n"
)


class Tool(ABC):
    """Base class for tools that can be used with the ``sensai`` package."""

    @abstractmethod
    def __init__(
        self, name: str, description: str, tool_type: str, parameters: dict[str, Any]
    ) -> None:
        """Initialize the tool with a name and description.

        Args:
            name (str): The name of the tool.
            description (str): A brief description of the tool's functionality.
            tool_type (str): The type of the tool.
            parameters (dict[str, Any]): The parameters for the tool.
        """
        self.name = name
        self.description = description
        self.type = tool_type
        self.parameters = parameters

    def define(self) -> dict[str, Any]:
        """Define the tool's properties and behavior.

        Returns:
            dict[str, Any]: A dictionary containing the tool's properties and behavior.
        """
        return {
            "type": self.type,
            "function": {
                "name": self.name,
                "description": CALL_GUARD_PREFIX + self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool's functionality.

        This method should be overridden by subclasses to implement specific tool behavior.

        Args:
            *args: Positional arguments for the tool's execution.
            **kwargs: Keyword arguments for the tool's execution.

        Returns:
            Any: The result of the tool's execution.
        """
