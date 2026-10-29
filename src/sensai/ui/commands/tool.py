"""List the tools available to the agent, and enable or disable them alone or by group."""

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document
from rich.table import Table
from rich.text import Text

from sensai.data.profile.manager import ProfileManager
from sensai.data.profile.profile import update_profile_settings
from sensai.features.features import MCP, TOOLS
from sensai.features.tools.mcp.mcp_tools import MCPTools
from sensai.features.tools.tool import Tool
from sensai.ui.command import CommandContext

if TYPE_CHECKING:
    from sensai.agent import Agent

USAGE = "Usage: /tools [list | enable|disable <tool or group>...]"


def save_tool_settings(context: CommandContext) -> None:
    """Keep the disabled tools and features in the active profile, for the next launches."""
    profile = ProfileManager.current_profile
    if not profile or not profile.id:
        return
    try:
        settings = json.loads(profile.settings) if profile.settings else {}
    except json.JSONDecodeError:
        settings = {}
    features = context.config.features
    settings["disabled_tools"] = sorted(features.disabled_tools)
    settings["disabled_features"] = sorted(features.disabled)
    settings_str = json.dumps(settings)
    update_profile_settings(context.database, profile.id, settings_str)
    profile.settings = settings_str


def _groups(tools: Iterable[Tool]) -> dict[str, list[Tool]]:
    """The tools by group, in the order the groups first appear."""
    groups: dict[str, list[Tool]] = {}
    for tool in tools:
        groups.setdefault(tool.group, []).append(tool)
    return groups


def _disabled_reason(context: CommandContext, tool: Tool) -> str | None:
    """Why a tool is unavailable to the agent, or None if it is available."""
    features = context.config.features
    if not features.is_enabled(TOOLS):
        return "tools feature off"
    if isinstance(tool, MCPTools) and not features.is_enabled(MCP):
        return "mcp feature off"
    if not features.is_tool_enabled(tool.name):
        return "disabled"
    return None


async def _list_tools(context: CommandContext) -> None:
    """Display every tool by group, with its source, safety and why it is off."""
    if not context.agent.tools:
        await context.ui.on_system_message("No tools available.")
        return

    if not context.config.features.is_enabled(TOOLS):
        await context.ui.on_system_message(
            "[yellow]The tools feature is off: no tool is available. "
            "Turn it on in /settings → Features.[/yellow]"
        )
    table = Table(title="Tools", show_header=True, header_style="bold magenta")
    table.add_column("Tool", style="cyan")
    table.add_column("Group")
    table.add_column("Source")
    table.add_column("Safe")
    table.add_column("Status")
    table.add_column("Description")
    for group, tools in _groups(context.agent.tools).items():
        for tool in tools:
            reason = _disabled_reason(context, tool)
            status = "[green]on[/green]" if reason is None else f"[red]off ({reason})[/red]"
            source = group if isinstance(tool, MCPTools) else "built-in"
            table.add_row(
                Text(tool.name),
                Text(group),
                Text(source),
                "yes" if tool.safe else "no",
                status,
                Text(tool.description),
            )

    await context.ui.on_system_message(table)


def _resolve(agent: "Agent", names: Iterable[str]) -> tuple[list[str], list[str]]:
    """The tool names that the given tool or group names cover, and the unknown names."""
    groups = _groups(agent.tools)
    known = {tool.name for tool in agent.tools}
    tools: list[str] = []
    unknown: list[str] = []
    for name in names:
        if name in groups:
            tools.extend(tool.name for tool in groups[name])
        elif name in known:
            tools.append(name)
        else:
            unknown.append(name)
    return tools, unknown


async def _set_tools(context: CommandContext, names: list[str], *, enabled: bool) -> None:
    """Enable or disable tools or whole groups by name, and save that choice."""
    tools, unknown = _resolve(context.agent, names)
    if tools:
        context.config.features.set_tools(tools, enabled=enabled)
        save_tool_settings(context)
        state = "enabled" if enabled else "disabled"
        await context.ui.on_system_message(
            f"[bold green]Tools {state}: {', '.join(dict.fromkeys(tools))}.[/bold green]"
        )
    if unknown:
        await context.ui.on_system_message(
            f"[bold red]Unknown tool or group: {', '.join(unknown)}.[/bold red]"
        )


async def _fine_tune_group(context: CommandContext, groups: dict[str, list[Tool]]) -> None:
    """Let the user pick a group, then tick its tools one by one."""
    features = context.config.features
    group = await context.ui.prompt_choice(
        title="Tools",
        text="Select a group to fine-tune:",
        choices=[*((name, name) for name in groups), ("back", "Back")],
    )
    if group is None or group not in groups:
        return
    tools = groups[group]
    result = await context.ui.prompt_checklist(
        title=f"Tools: {group}",
        text="Tick the tools the agent may use. Unsafe tools ask approval in partial trust.",
        choices=[(tool.name, f"{tool.name}{'' if tool.safe else ' (unsafe)'}") for tool in tools],
        checked=[tool.name for tool in tools if features.is_tool_enabled(tool.name)],
    )
    if result is None:
        return
    _, ticked = result
    for tool in tools:
        features.set_tool(tool.name, enabled=tool.name in ticked)


async def edit_tools(context: CommandContext) -> bool:
    """Open the tool dialog: the groups, then optionally one group's tools.

    Changes are saved to the profile once confirmed; cancelling leaves everything as it was.

    Returns:
        bool: Whether changes were applied.
    """
    features = context.config.features
    groups = _groups(context.agent.tools)
    group_on = {
        name: any(features.is_tool_enabled(tool.name) for tool in tools)
        for name, tools in groups.items()
    }
    choices = []
    for name, tools in groups.items():
        on = sum(features.is_tool_enabled(tool.name) for tool in tools)
        choices.append((f"group:{name}", f"{name} ({on}/{len(tools)} on)"))
    checked = [f"group:{name}" for name, on in group_on.items() if on]

    result = await context.ui.prompt_checklist(
        title="Tools",
        text=(
            "Tick what the agent may use. A group counts as on while any of its tools is; "
            "use Fine-tune to pick tools within a group."
        ),
        choices=choices,
        checked=checked,
        extra="Fine-tune…",
    )
    if result is None:
        return False
    action, ticked = result
    for name, tools in groups.items():
        on = f"group:{name}" in ticked
        if on != group_on[name]:
            features.set_tools((tool.name for tool in tools), enabled=on)
    if action == "extra" and groups:
        await _fine_tune_group(context, groups)
    save_tool_settings(context)
    return True


class ToolNameCompleter(Completer):  # type: ignore[misc,unused-ignore]
    """Suggest group and tool names after /tools enable|disable."""

    def __init__(self, agent: "Agent") -> None:
        """Complete against the tools of this agent, as they are when completing."""
        self.agent = agent

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Complete the name under the cursor, skipping the names already typed."""
        words = document.text_before_cursor.split(" ")
        if len(words) < 3 or words[1] not in {"enable", "disable"}:  # noqa: PLR2004
            return
        word = words[-1]
        typed = set(words[2:-1])
        groups = _groups(self.agent.tools)
        candidates = [(name, f"group, {len(tools)} tool(s)") for name, tools in groups.items()]
        candidates += [(tool.name, tool.group) for tool in self.agent.tools]
        for name, meta in dict(candidates).items():
            if name.startswith(word) and name not in typed:
                yield Completion(name, start_position=-len(word), display_meta=meta)


async def tool_execute(context: CommandContext, args: list[str]) -> None:
    """Execute the /tools command: open the dialog, list the tools, or enable or disable some."""
    if not args:
        if not context.agent.tools:
            await context.ui.on_system_message("No tools available.")
        elif await edit_tools(context):
            await context.ui.on_system_message("[bold green]Tool settings saved.[/bold green]")
    elif args == ["list"]:
        await _list_tools(context)
    elif len(args) >= 2 and args[0] in {"enable", "disable"}:  # noqa: PLR2004
        await _set_tools(context, args[1:], enabled=args[0] == "enable")
    else:
        await context.ui.on_system_message(USAGE)
