"""Interactive CLI application using prompt_toolkit."""

from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.session.manager import build_messages, maybe_compress_session, update_session
from sensai.data.session.session import Session


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
    ) -> None:
        """Initialize the CLI Application.

        Args:
            agent: The configured ReAct agent.
            database: The active database connection.
            session: The active chat session.
            client: The Ollama client.
            config: The application configuration.
            profile_name: The name of the user profile.
        """
        self.agent = agent
        self.database = database
        self.session = session
        self.client = client
        self.config = config
        self.profile_name = profile_name
        self.console = Console()
        self.prompt_session: PromptSession[str] | None = None

        self._setup_prompt_session()

    def _setup_prompt_session(self) -> None:
        """Configure the prompt_toolkit session with custom key bindings."""
        kb = KeyBindings()

        @kb.add("enter")  # type: ignore[untyped-decorator]
        def _(event: Any) -> None:
            """Submit the input when Enter is pressed."""
            event.current_buffer.validate_and_handle()

        @kb.add("escape", "enter")  # type: ignore[untyped-decorator]
        def _(event: Any) -> None:
            """Insert a newline when Esc + Enter is pressed."""
            event.current_buffer.insert_text("\n")

        self.prompt_session = PromptSession[str](
            message="Vous > ",
            multiline=True,
            key_bindings=kb,
        )

    async def run(self) -> None:
        """Run the interactive REPL loop."""
        self.console.print(f"[bold cyan]Hello {self.profile_name}! Welcome to Sensai.[/bold cyan]")
        self.console.print(
            "[dim](Press Enter to submit, Alt+Enter/Esc+Enter for new line, Ctrl+C to exit)[/dim]\n"
        )

        if self.prompt_session is None:
            return

        try:
            while True:
                user_input = await self.prompt_session.prompt_async()
                if not user_input.strip():
                    continue

                messages = build_messages(self.session, user_input)
                sent_prefix_length = len(messages) - 1

                response = await self.agent.run(messages=messages)

                updated_session = update_session(
                    self.database, self.session, response, sent_prefix_length
                )
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

                self.console.print("\n")

        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[bold red]Program terminated by user.[/bold red]")
