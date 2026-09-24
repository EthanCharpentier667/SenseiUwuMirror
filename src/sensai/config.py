"""Configuration for the Sensai CLI."""

from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "llama3.2"
DEFAULT_SCHEMA_PATH = Path(__file__).parent / "data" / "database" / "schema.sql"
DEFAULT_DB_PATH = "./"
DEFAULT_DB_NAME = "sensai.db"
DEFAULT_COMPRESSION_TOKEN_THRESHOLD = 3000
REASONING_MODES = ["plan", "reflect"]


class Config:
    """Centralizes every CLI-configurable setting for the Sensai chatbot.

    Wraps an ``ArgumentParser`` so every knob a user could want to tweak when running
    ``sensai`` (which model to talk to, where the database lives, ...) is declared and
    defaulted here, instead of being hardcoded across the modules that use it.
    """

    def __init__(
        self,
        name: str = "sensai",
        description: str = "Sensai: LLM chatbot with unlimited functionalities.",
    ) -> None:
        """Initialize the config and register its command-line arguments.

        Args:
            name (str): The program name shown in ``--help``. Default is "sensai".
            description (str): The program description shown in ``--help``.
        """
        self.name = name
        self.description = description
        self.parser = ArgumentParser(prog=name, description=description)
        self.args: Namespace | None = None
        self._register_arguments()

    def _register_arguments(self) -> None:
        """Register every CLI flag this config exposes, with its default."""
        self.add_argument(
            "--model",
            default=DEFAULT_MODEL,
            help=f"The LLM model to use. Default: {DEFAULT_MODEL}.",
        )
        self.add_argument(
            "--reasoning-mode",
            default=None,
            choices=REASONING_MODES,
            help="Reasoning mode for the model. Not implemented yet.",
        )
        self.add_argument(
            "--schema-path",
            type=Path,
            default=DEFAULT_SCHEMA_PATH,
            help=f"Path to the SQL file used to initialize the database schema. "
            f"Default: {DEFAULT_SCHEMA_PATH}.",
        )
        self.add_argument(
            "--db-path",
            default=DEFAULT_DB_PATH,
            help=f"Directory where the SQLite database file is stored. Default: {DEFAULT_DB_PATH}.",
        )
        self.add_argument(
            "--db-name",
            default=DEFAULT_DB_NAME,
            help=f"File name of the SQLite database. Default: {DEFAULT_DB_NAME}.",
        )
        self.add_argument(
            "--compression-threshold",
            type=int,
            default=DEFAULT_COMPRESSION_TOKEN_THRESHOLD,
            help="Prompt token count above which a session's history gets compressed. "
            f"Default: {DEFAULT_COMPRESSION_TOKEN_THRESHOLD}.",
        )

    def add_argument(self, *args: Any, **kwargs: Any) -> None:
        """Add a command-line argument to the parser."""
        self.parser.add_argument(*args, **kwargs)

    def parse_args(self, args: list[str] | None = None) -> Namespace:
        """Parse the command-line arguments.

        Args:
            args (list[str], optional): The argument strings to parse, e.g. for tests.
                Default is None, which parses ``sys.argv``.
        """
        self.args = self.parser.parse_args(args)
        return self.args

    def get_args(self) -> Namespace | None:
        """Get the parsed command-line arguments."""
        return self.args

    def _parsed(self) -> Namespace:
        """The parsed arguments, parsing them from ``sys.argv`` first if needed."""
        if self.args is None:
            return self.parse_args()
        return self.args

    @property
    def model(self) -> str:
        """The LLM model to use."""
        return str(self._parsed().model)

    @property
    def reasoning_mode(self) -> str | None:
        """The reasoning mode to use. Not implemented yet."""
        return str(self._parsed().reasoning_mode)

    @property
    def schema_path(self) -> Path:
        """Path to the SQL file used to initialize the database schema."""
        return Path(self._parsed().schema_path)

    @property
    def db_path(self) -> str:
        """Directory where the SQLite database file is stored."""
        return str(self._parsed().db_path)

    @property
    def db_name(self) -> str:
        """File name of the SQLite database."""
        return str(self._parsed().db_name)

    @property
    def compression_threshold(self) -> int:
        """Prompt token count above which a session's history gets compressed."""
        return int(self._parsed().compression_threshold)
