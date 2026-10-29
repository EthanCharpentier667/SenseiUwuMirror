"""Configuration for the Sensai CLI."""

import json
import sys
from argparse import SUPPRESS, ArgumentParser, ArgumentTypeError, Namespace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from sensai.features.features import FEATURES, Features

load_dotenv()

AVAILABLE_MODELS = ["gemma4:e4b", "qwen3.5:9b", "llama3.2:latest"]
DEFAULT_MODEL = "llama3.2"
DEFAULT_DB_PATH = "./"
DEFAULT_DB_NAME = "sensai.db"
DEFAULT_COMPRESSION_TOKEN_THRESHOLD = 3000
DEFAULT_URL = "https://ollama.tanouminou.com/api/chat"
DEFAULT_TIMEOUT = 300.0
DEFAULT_NUM_CTX = 16384
DEFAULT_PERSONAS_FILE = "personas.json"


def _parse_output_schema(value: str) -> dict[str, Any]:
    """Parse an inline JSON schema supplied on the command line."""
    try:
        schema = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ArgumentTypeError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(schema, dict):
        raise ArgumentTypeError("the output schema must be a JSON object")
    return schema


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
        self.parser = ArgumentParser(prog=name, description=description, allow_abbrev=False)
        self.args: Namespace | None = None
        self._features: Features | None = None
        self.explicit_args: set[str] = set()
        self._register_arguments()

    def _register_arguments(self) -> None:
        """Register every CLI flag this config exposes, with its default."""
        self.add_argument(
            "--model",
            default=DEFAULT_MODEL,
            help=f"The LLM model to use. Default: {DEFAULT_MODEL}.",
        )
        self.add_argument(
            "--output-schema",
            type=_parse_output_schema,
            default=None,
            metavar="JSON",
            help="JSON Schema for final responses, supplied as an inline JSON object.",
        )
        self.add_argument(
            "--url",
            default=DEFAULT_URL,
            help=f"The URL of the Ollama API. Default: {DEFAULT_URL}.",
        )
        self.add_argument(
            "--token",
            default=None,
            help="The bearer token for the Ollama API. Default: None.",
        )
        self.add_argument(
            "--timeout",
            type=float,
            default=DEFAULT_TIMEOUT,
            help=f"The timeout for the Ollama API requests. Default: {DEFAULT_TIMEOUT} seconds.",
        )
        self.add_argument(
            "--num-ctx",
            "--context-length",
            dest="num_ctx",
            type=int,
            default=DEFAULT_NUM_CTX,
            help="Context window size (in tokens) requested from Ollama. "
            f"Default: {DEFAULT_NUM_CTX}.",
        )
        self.add_argument(
            "--temperature",
            type=float,
            default=None,
            help="Sampling temperature for Ollama generation (e.g. 0.7). Default: None.",
        )
        self.add_argument(
            "--top-p",
            type=float,
            default=None,
            help="Nucleus sampling probability threshold (e.g. 0.9). Default: None.",
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
        self.add_argument(
            "--files",
            nargs="*",
            type=Path,
            default=[],
            help="Files to attach to the session. Default: none.",
        )
        self.add_argument(
            "--disable",
            nargs="*",
            choices=list(FEATURES),
            default=[],
            metavar="FEATURE",
            help=f"Features to disable, among: {', '.join(FEATURES)}. Default: none.",
        )
        self.add_argument(
            "--disable-tool",
            nargs="*",
            default=[],
            metavar="TOOL",
            help="Tools to disable, by name (see /tool). Default: none.",
        )
        self.add_argument(
            "--verbose",
            action="store_true",
            help=SUPPRESS,
        )
        self.add_argument(
            "--persona",
            default=None,
            help="Persona key to use from the personas file (e.g. 'sensei_wu').",
        )
        self.add_argument(
            "--list-personas",
            action="store_true",
            default=False,
            help="List available personas from the personas file and exit.",
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
        raw_args = sys.argv[1:] if args is None else args
        self.explicit_args = {arg.split("=")[0] for arg in raw_args if arg.startswith("-")}
        self.args = self.parser.parse_args(args)
        for path in self.args.files:
            if not path.is_file():
                self.parser.error(f"file not found: {path}")
        self._features = Features.from_disabled(self.args.disable, self.args.disable_tool)
        return self.args

    def was_explicitly_set(self, *flags: str) -> bool:
        """Check if any of the given flag strings were explicitly passed on the command line."""
        return any(flag in self.explicit_args for flag in flags)

    def get_args(self) -> Namespace | None:
        """Get the parsed command-line arguments."""
        return self.args

    def _parsed(self) -> Namespace:
        """The parsed arguments, parsing them from ``sys.argv`` first if needed."""
        if self.args is None:
            return self.parse_args()
        return self.args

    @property
    def output_schema(self) -> dict[str, Any] | None:
        """The optional JSON schema for final agent responses."""
        schema: dict[str, Any] | None = self._parsed().output_schema
        return schema

    @property
    def model(self) -> str:
        """The LLM model to use."""
        return str(self._parsed().model)

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

    @property
    def url(self) -> str:
        """The URL of the Ollama API."""
        return str(self._parsed().url)

    @property
    def token(self) -> str | None:
        """The bearer token for the Ollama API."""
        token = self._parsed().token
        return str(token) if token is not None else None

    @property
    def timeout(self) -> float:
        """The timeout for the Ollama API requests."""
        return float(self._parsed().timeout)

    @property
    def num_ctx(self) -> int:
        """Context window size (in tokens) requested from Ollama."""
        return int(self._parsed().num_ctx)

    @property
    def context_length(self) -> int:
        """Alias for num_ctx: context window size (in tokens)."""
        return self.num_ctx

    @property
    def temperature(self) -> float | None:
        """Sampling temperature for generation, if set."""
        temp = self._parsed().temperature
        return float(temp) if temp is not None else None

    @property
    def top_p(self) -> float | None:
        """Nucleus sampling probability threshold for generation, if set."""
        val = self._parsed().top_p
        return float(val) if val is not None else None

    @property
    def files(self) -> list[Path]:
        """Files to attach to the session, as given on the command line."""
        return list(self._parsed().files)

    @property
    def verbose(self) -> bool:
        """Whether verbose mode is enabled."""
        return bool(self._parsed().verbose)

    @property
    def persona(self) -> str | None:
        """The persona key to use from the personas file."""
        persona = self._parsed().persona
        return str(persona) if persona is not None else None

    @property
    def personas_file(self) -> str:
        """Path to the personas JSON file."""
        return DEFAULT_PERSONAS_FILE

    @property
    def list_personas(self) -> bool:
        """Whether to list available personas and exit."""
        return bool(self._parsed().list_personas)

    @property
    def features(self) -> Features:
        """The feature flags, shared by everything that reads them."""
        if self._features is None:
            args = self._parsed()
            self._features = Features.from_disabled(args.disable, args.disable_tool)
        return self._features
