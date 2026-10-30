"""Feature flags: every optional capability of SensaiUwu can be switched on or off."""

from collections.abc import Iterable

TOOLS = "tools"
REACT = "react"
RAG = "rag"
COMPRESSION = "compression"
MCP = "mcp"
TITLE = "title"

FEATURES: dict[str, str] = {
    TOOLS: "Let the agent call tools (built-in and MCP).",
    REACT: "Plan tool calls with the ReAct loop before replying.",
    RAG: "Retrieve chunks of attached documents for each prompt.",
    COMPRESSION: "Summarize the session history once it grows too long.",
    MCP: "Connect MCP servers with /mcp and use their tools.",
    TITLE: "Name each new session from its first exchange.",
}


def _check(name: str) -> None:
    if name not in FEATURES:
        msg = f"Unknown feature '{name}'. Choose one of: {', '.join(FEATURES)}."
        raise ValueError(msg)


class Features:
    """Which features and tools are enabled. Everything is enabled unless disabled here.

    A single instance is shared by the config, the agent and the CLI, so toggling a
    feature at runtime (e.g. from ``/settings``) takes effect everywhere at once.

    Two layers are kept apart: the saved choices, which the profile stores between
    launches, and the overrides of the current run (``--disable``, ``--enable``...),
    which win over the saved choices but are never saved. Choosing a feature or tool at
    runtime drops its override, so the choice takes effect at once and is saved.
    """

    def __init__(self) -> None:
        """Enable every feature and tool, with no override."""
        self.saved_disabled: set[str] = set()
        self.saved_disabled_tools: set[str] = set()
        self._run_off: set[str] = set()
        self._run_on: set[str] = set()
        self._run_off_tools: set[str] = set()
        self._run_on_tools: set[str] = set()

    @classmethod
    def from_disabled(
        cls,
        names: Iterable[str],
        tools: Iterable[str] = (),
        *,
        enabled: Iterable[str] = (),
        enabled_tools: Iterable[str] = (),
    ) -> "Features":
        """Build the flags from the features and tools to disable or enable for this run.

        These are overrides: they win over the saved choices but are never saved.
        """
        features = cls()
        for name in (*names, *enabled):
            _check(name)
        features._run_off = set(names)
        features._run_on = set(enabled) - features._run_off
        features._run_off_tools = set(tools)
        features._run_on_tools = set(enabled_tools) - features._run_off_tools
        return features

    def load_saved(self, names: Iterable[str], tools: Iterable[str]) -> None:
        """Restore the saved choices (e.g. from the profile); unknown features are skipped."""
        self.saved_disabled = {name for name in names if name in FEATURES}
        self.saved_disabled_tools = set(tools)

    @property
    def disabled(self) -> set[str]:
        """The features disabled for this run."""
        return (self.saved_disabled | self._run_off) - self._run_on

    @property
    def disabled_tools(self) -> set[str]:
        """The tools disabled for this run."""
        return (self.saved_disabled_tools | self._run_off_tools) - self._run_on_tools

    def is_enabled(self, name: str) -> bool:
        """Whether a feature is enabled."""
        _check(name)
        return name not in self.disabled

    def set(self, name: str, *, enabled: bool) -> None:
        """Enable or disable a feature, as a choice to save."""
        _check(name)
        self._run_off.discard(name)
        self._run_on.discard(name)
        if enabled:
            self.saved_disabled.discard(name)
        else:
            self.saved_disabled.add(name)

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
        """Enable or disable a single tool, as a choice to save."""
        self._run_off_tools.discard(name)
        self._run_on_tools.discard(name)
        if enabled:
            self.saved_disabled_tools.discard(name)
        else:
            self.saved_disabled_tools.add(name)

    def set_tools(self, names: Iterable[str], *, enabled: bool) -> None:
        """Enable or disable several tools at once, e.g. every tool of a group."""
        for name in names:
            self.set_tool(name, enabled=enabled)

    def toggle_tool(self, name: str) -> bool:
        """Flip a single tool, returning whether it is now enabled."""
        enabled = not self.is_tool_enabled(name)
        self.set_tool(name, enabled=enabled)
        return enabled
