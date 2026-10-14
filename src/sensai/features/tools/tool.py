"""Tool interface for the ``sensai`` package."""

from abc import ABC, abstractmethod
from collections.abc import Collection
from typing import Any


class Tool(ABC):
    """Base class for tools that can be used with the ``sensai`` package."""

    @abstractmethod
    def __init__(  # noqa: PLR0913
        self,
        name: str,
        description: str,
        tool_type: str,
        parameters: dict[str, Any],
        *,
        safe: bool = False,
        show_output: bool = False,
        requires: Collection[str] = (),
    ) -> None:
        """Initialize the tool with a name and description.

        Args:
            name (str): The name of the tool.
            description (str): A brief description of the tool's functionality.
            tool_type (str): The type of the tool.
            parameters (dict[str, Any]): The parameters for the tool.
            safe (bool): Whether this tool is safe to run automatically in partial trust mode.
            show_output (bool): Whether this tool's execution result should be displayed in the UI.
            requires (Collection[str]): The model capabilities (as Ollama names them, e.g.
                "vision") this tool needs: it is hidden from a model lacking one of them.
        """
        self.name = name
        self.description = description
        self.type = tool_type
        self.parameters = parameters
        self.safe = safe
        self.show_output = show_output
        self.requires = frozenset(requires)

    def define(self) -> dict[str, Any]:
        """Define the tool's properties and behavior.

        Returns:
            dict[str, Any]: A dictionary containing the tool's properties and behavior.
        """
        return {
            "type": self.type,
            "function": {
                "name": self.name,
                "description": self.description,
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
            Any: The result of the tool's execution. A dict result may carry an "images"
                list of base64 images: the agent shows them to the model (if it can see
                images) instead of putting them in the text observation.
        """
