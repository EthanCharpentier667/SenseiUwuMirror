"""Interactive CLI application using prompt_toolkit."""

from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.session.manager import (
    build_messages,
    maybe_compress_session,
    retrieve_chunks,
    update_session,
)
from sensai.data.session.session import Session
from sensai.embedder import Embedder
from sensai.persona.manager import get_persona, list_personas, load_personas
from sensai.ui.builtin_commands import setup_builtin_commands
from sensai.ui.command import Command, CommandContext, CommandRegistry


class CLIApp:
    """Manages the interactive CLI loop using prompt_toolkit."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        agent: Agent,
        database: Database,
        session: Session,
        client: OllamaClient,
        config: Config,
        profile_name: str,
        embedder: Embedder | None = None,
    ) -> None:
        """Initialize the CLI Application.

        Args:
            agent: The configured ReAct agent.
            database: The active database connection.
            session: The active chat session.
            client: The Ollama client.
            config: The application configuration.
            profile_name: The name of the user profile.
            embedder: Optional embedder for document chunk retrieval.
        """
        self.agent = agent
        self.database = database
        self.session = session
        self.client = client
        self.config = config
        self.profile_name = profile_name
        self.embedder = embedder or Embedder(client)
        self.console = Console()

        self.command_registry = CommandRegistry()
        setup_builtin_commands(self.command_registry)
        self._setup_persona_commands()
        self.prompt_session: PromptSession[str] | None = None
        self._setup_prompt_session()

    def _setup_persona_commands(self) -> None:
        personas_file = self.config.personas_file
        agent = self.agent

        async def _switch_persona_execute(context: CommandContext, args: list[str]) -> None:
            if not args:
                await context.ui.on_system_message("[red]Usage: /switch-persona <key>[/red]")
                return
            new_key = args[0]
            try:
                personas = load_personas(personas_file)
                new_persona = get_persona(personas, new_key)
                if new_persona is not None:
                    agent.system_prompt = new_persona.system_prompt
                    await context.ui.on_system_message(
                        f"[bold green]Persona switched to '{new_key}': "
                        f"{new_persona.name}[/bold green]"
                    )
                else:
                    await context.ui.on_system_message(f"Warning: persona '{new_key}' not found.")
            except (FileNotFoundError, ValueError) as exc:
                await context.ui.on_system_message(
                    f"[red]Warning: could not switch persona: {exc}[/red]"
                )

        async def _list_personas_execute(context: CommandContext, _args: list[str]) -> None:
            try:
                personas = load_personas(personas_file)
                keys = list_personas(personas)
                if keys:
                    for key in keys:
                        p = personas[key]
                        await context.ui.on_system_message(
                            f"  [cyan]{key}[/cyan]: {p.name} — {p.description}"
                        )
                else:
                    await context.ui.on_system_message("[dim]No personas found.[/dim]")
            except (FileNotFoundError, ValueError) as exc:
                await context.ui.on_system_message(
                    f"[red]Warning: could not load personas: {exc}[/red]"
                )

        self.command_registry.register(
            Command("/switch-persona", "Switch the active persona.", _switch_persona_execute)
        )
        self.command_registry.register(
            Command("/list-personas", "List available personas.", _list_personas_execute)
        )

    def _setup_prompt_session(self) -> None:
        """Configure the prompt_toolkit session with custom key bindings."""
        kb = KeyBindings()

        def _handle_enter(event: Any) -> None:
            """Submit the input when Enter is pressed."""
            event.current_buffer.validate_and_handle()

        kb.add("enter")(_handle_enter)

        def _handle_esc_enter(event: Any) -> None:
            """Insert a newline when Esc + Enter is pressed."""
            event.current_buffer.insert_text("\n")

        kb.add("escape", "enter")(_handle_esc_enter)

        self.prompt_session = PromptSession[str](
            message="Vous > ",
            multiline=True,
            key_bindings=kb,
            completer=self.command_registry.get_completer(),
        )

    async def _handle_command(self, user_input: str) -> None:
        """Execute a built-in slash command."""
        if self.agent.ui_handler is None:
            raise ValueError("UI handler is not set on the agent.")
        ctx = CommandContext(database=self.database, ui=self.agent.ui_handler)
        await self.command_registry.execute(user_input, ctx)

    async def _handle_chat(self, user_input: str) -> None:
        """Process a standard chat message with the AI."""
        retrieved = await retrieve_chunks(self.database, self.embedder, self.session, user_input)
        messages = build_messages(self.session, user_input, retrieved)
        sent_prefix_length = len(messages) - 1

        response = await self.agent.run(messages=messages)

        updated_session = update_session(self.database, self.session, response, sent_prefix_length)
        if updated_session is None:
            msg = "Failed to update the session after the response."
            raise ValueError(msg)

        self.session = updated_session

        self.session = await maybe_compress_session(
            self.database,
            self.session,
            response,
            threshold=self.config.compression_threshold,
            client=self.client,
        )

    async def run(self) -> None:
        """Run the interactive REPL loop."""
        self.console.print(f"[bold cyan]Hello {self.profile_name}! Welcome to Sensai.[/bold cyan]")
        self.console.print(
            "[dim](Type /help for commands, Press Enter to submit, "
            "Alt+Enter for new line, Ctrl+C to exit)[/dim]\n"
        )

        if self.prompt_session is None:
            return

        try:
            while True:
                user_input = await self.prompt_session.prompt_async()
                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                else:
                    try:
                        await self._handle_chat(user_input)
                    except Exception as e:  # noqa: BLE001
                        self.console.print(f"[bold red]Chat failed:[/bold red] {e}")
                    self.console.print("\n")

        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[bold red]Program terminated by user.[/bold red]")
