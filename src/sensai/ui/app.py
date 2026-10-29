"""Interactive CLI application using prompt_toolkit."""

import asyncio
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.session.document import get_document
from sensai.data.session.manager import (
    build_messages,
    ensure_persisted,
    generate_session_title,
    maybe_compress_session,
    retrieve_chunks,
    set_current_session,
    update_session,
)
from sensai.data.session.message import get_document_ids_by_session
from sensai.data.session.session import Session
from sensai.features.features import COMPRESSION, RAG, TITLE
from sensai.features.rag.embedder import Embedder
from sensai.features.rag.rag import ingest_document
from sensai.features.tools.browser.page import close_browser
from sensai.ui.command import CommandContext, CommandRegistry
from sensai.ui.commands import setup_builtin_commands
from sensai.ui.commands.mcp.mcp_commands import MCPCommands


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
        setup_builtin_commands(self.command_registry, agent, database)
        self.mcp_commands = MCPCommands(agent)
        self.mcp_commands.register(self.command_registry)
        self.prompt_session: PromptSession[str] | None = None
        self._setup_prompt_session()

    def _setup_prompt_session(self) -> None:
        """Configure the prompt_toolkit session with custom key bindings."""
        kb = KeyBindings()

        def _handle_enter(event: Any) -> None:
            """Accept a selected completion before allowing the user to submit."""
            buffer = event.current_buffer
            if buffer.complete_state is not None and buffer.complete_state.current_completion:
                buffer.complete_state = None
                return
            buffer.validate_and_handle()

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
        ctx = CommandContext(
            database=self.database,
            ui=self.agent.ui_handler,
            agent=self.agent,
            config=self.config,
            session=self.session,
            switch_session=self.switch_session,
        )
        await self.command_registry.execute(user_input, ctx)

    def switch_session(self, session: Session) -> None:
        """Make ``session`` the one the chat continues, here and process-wide."""
        self.session = session
        set_current_session(session)
        self.agent.last_prompt_tokens = 0

    async def _handle_chat(self, user_input: str) -> None:
        """Process a standard chat message with the AI."""
        features = self.config.features
        if self.agent.ui_handler:
            await self.agent.ui_handler.start_spinner("Thinking...")
        try:
            retrieved = (
                await retrieve_chunks(self.database, self.embedder, self.session, user_input)
                if features.is_enabled(RAG)
                else []
            )
            messages = build_messages(self.session, user_input, retrieved)
            sent_prefix_length = len(messages) - 1

            response = await self.agent.run(messages=messages)
            self.agent.last_prompt_tokens = response.prompt_eval_count

            self._set_session(ensure_persisted(self.database, self.session))
            updated_session = update_session(
                self.database, self.session, response, sent_prefix_length
            )
            if updated_session is None:
                msg = "Failed to update the session after the response."
                raise ValueError(msg)

            self._set_session(updated_session)
            if features.is_enabled(RAG):
                await self._ingest_read_documents()

            if features.is_enabled(TITLE) and not self.session.name:
                await self._generate_title(response.model or self.agent.model)

            if features.is_enabled(COMPRESSION):
                compressed = await maybe_compress_session(
                    self.database,
                    self.session,
                    response,
                    threshold=self.config.compression_threshold,
                    client=self.client,
                    ui_handler=self.agent.ui_handler,
                )
                self._set_session(compressed)
        finally:
            if self.agent.ui_handler:
                await self.agent.ui_handler.stop_spinner()

    def _set_session(self, session: Session) -> None:
        """Replace the current session with a newer copy of itself, here and process-wide."""
        self.session = session
        set_current_session(session)

    async def _generate_title(self, model: str) -> None:
        """Name the session from its first exchange; a failure never fails the turn."""
        try:
            self._set_session(
                await generate_session_title(self.database, self.session, self.client, model)
            )
        except Exception as e:  # noqa: BLE001
            if self.config.verbose:
                self.console.print(f"[dim]Could not generate a session title: {e}[/dim]")

    async def _ingest_read_documents(self) -> None:
        """Ingest the files the agent read this turn, attached to the turn's user message.

        Later turns then retrieve their relevant chunks, beyond the part of the file the
        model saw in the tool's (truncated) observation. A file whose content the session
        already holds (read at an earlier turn, attached on the command line, or reached
        by another path) is skipped, so its chunks aren't retrieved twice.
        """
        if not self.agent.read_documents:
            return
        turn_message = next(
            (message for message in reversed(self.session.messages) if message.role == "user"),
            None,
        )
        if turn_message is None or turn_message.id is None:
            return
        known = {
            document.content
            for document_id in get_document_ids_by_session(self.database, turn_message.session_id)
            if (document := get_document(self.database, document_id)) is not None
        }
        for path in dict.fromkeys(self.agent.read_documents):
            try:
                content = await asyncio.to_thread(Path(path).read_bytes)
                if content in known:
                    continue
                await ingest_document(
                    self.database, self.embedder, turn_message.id, content, Path(path).name
                )
                known.add(content)
            except (OSError, ValueError) as e:
                if self.agent.ui_handler:
                    await self.agent.ui_handler.on_error(e, title=f"RAG: {path}")

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
                        if self.agent.ui_handler:
                            await self.agent.ui_handler.on_error(e, title="Chat Error")
                        else:
                            self.console.print(f"[bold red]Chat failed:[/bold red] {e}")
                    self.console.print("\n")

        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[bold red]Program terminated by user.[/bold red]")
        finally:
            await self.mcp_commands.aclose()
            await close_browser()
