"""Feature flags: every optional capability of Sensai can be switched on or off."""

from collections.abc import Iterable
from dataclasses import dataclass, field

TOOLS = "tools"
REACT = "react"
RAG = "rag"
COMPRESSION = "compression"
MCP = "mcp"

FEATURES: dict[str, str] = {
    TOOLS: "Let the agent call tools (built-in and MCP).",
    REACT: "Plan tool calls with the ReAct loop before replying.",
    RAG: "Retrieve chunks of attached documents for each prompt.",
    COMPRESSION: "Summarize the session history once it grows too long.",
    MCP: "Connect MCP servers with /mcp and use their tools.",
}


def _check(name: str) -> None:
    if name not in FEATURES:
        msg = f"Unknown feature '{name}'. Choose one of: {', '.join(FEATURES)}."
        raise ValueError(msg)


@dataclass
class Features:
    """Which features and tools are enabled. Everything is enabled unless disabled here.

    A single instance is shared by the config, the agent and the CLI, so toggling a
    feature at runtime (e.g. from ``/settings``) takes effect everywhere at once.
    """

    disabled: set[str] = field(default_factory=set)
    disabled_tools: set[str] = field(default_factory=set)

    @classmethod
    def from_disabled(cls, names: Iterable[str], tools: Iterable[str] = ()) -> "Features":
        """Build the flags from the names of the features and tools to disable."""
        features = cls(disabled_tools=set(tools))
        for name in names:
            features.set(name, enabled=False)
        return features

    def is_enabled(self, name: str) -> bool:
        """Whether a feature is enabled."""
        _check(name)
        return name not in self.disabled

    def set(self, name: str, *, enabled: bool) -> None:
        """Enable or disable a feature."""
        _check(name)
        if enabled:
            self.disabled.discard(name)
        else:
            self.disabled.add(name)

    def toggle(self, name: str) -> bool:
        """Flip a feature, returning whether it is now enabled."""
        enabled = not self.is_enabled(name)
        self.set(name, enabled=enabled)
        return enabled

    def is_tool_enabled(self, name: str) -> bool:
        """Whether a single tool is enabled.

        Tool names aren't checked: MCP tools only exist once their server is connected,
        so a tool may be disabled before it is known.
        """
        return name not in self.disabled_tools

    def set_tool(self, name: str, *, enabled: bool) -> None:
        """Enable or disable a single tool."""
        if enabled:
            self.disabled_tools.discard(name)
        else:
            self.disabled_tools.add(name)

    def set_tools(self, names: Iterable[str], *, enabled: bool) -> None:
        """Enable or disable several tools at once, e.g. every tool of a group."""
        for name in names:
            self.set_tool(name, enabled=enabled)

    def toggle_tool(self, name: str) -> bool:
        """Flip a single tool, returning whether it is now enabled."""
        enabled = not self.is_tool_enabled(name)
        self.set_tool(name, enabled=enabled)
        return enabled
