"""Sensai: LLM chatbot with unlimited functionalities."""

import asyncio
import json
from typing import Any

from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import TRUST_LEVELS, Config
from sensai.core.setup import (
    ingest_initial_files,
    setup_ai_engine,
    setup_database,
    setup_embedder,
    start_session,
)
from sensai.data.profile.profile import load_profile_settings
from sensai.data.session.manager import ensure_persisted, set_current_session
from sensai.features.persona.manager import get_persona, list_personas, load_personas
from sensai.ui.app import CLIApp
from sensai.ui.auth import authenticate_user

__all__ = ["CLIApp", "main"]


def _handle_list_personas(config: Config, console: Console) -> bool:
    """Print available personas and return True if --list-personas was requested."""
    if not config.list_personas:
        return False
    try:
        personas = load_personas(config.personas_file)
        keys = list_personas(personas)
        if keys:
            console.print("Available personas:")
            for key in keys:
                p = personas[key]
                console.print(f"  [cyan]{key}[/cyan]: {p.name} — {p.description}")
        else:
            console.print("[dim]No personas found.[/dim]")
    except FileNotFoundError:
        console.print(f"[red]Warning: personas file not found: {config.personas_file}[/red]")
    return True


def _apply_persona(config: Config, agent: Agent, console: Console, key: str | None) -> None:
    """Load and apply the persona with this key to the agent, if any."""
    if not key:
        return
    try:
        personas = load_personas(config.personas_file)
        persona = get_persona(personas, key)
        if persona is not None:
            agent.system_prompt = persona.system_prompt
            agent.persona_key = key
        else:
            console.print(f"[red]Warning: persona '{key}' not found.[/red]")
    except FileNotFoundError:
        console.print(f"[red]Warning: personas file not found: {config.personas_file}[/red]")
    except ValueError as exc:
        console.print(f"[red]Warning: invalid personas file: {exc}[/red]")


def _apply_generation_settings(
    config: Config, client: OllamaClient, settings: dict[str, Any]
) -> None:
    """Apply persisted generation parameters to the client and config args."""
    args = config.get_args()
    if "temperature" in settings and not config.was_explicitly_set("--temperature"):
        client.temperature = settings["temperature"]
        if args and hasattr(args, "temperature"):
            args.temperature = settings["temperature"]
    if "top_p" in settings and not config.was_explicitly_set("--top-p"):
        client.top_p = settings["top_p"]
        if args and hasattr(args, "top_p"):
            args.top_p = settings["top_p"]
    if "num_ctx" in settings and not config.was_explicitly_set("--num-ctx", "--context-length"):
        client.num_ctx = settings["num_ctx"]
        if args and hasattr(args, "num_ctx"):
            args.num_ctx = settings["num_ctx"]
    if "timeout" in settings and not config.was_explicitly_set("--timeout"):
        client.timeout = settings["timeout"]
        if args:
            args.timeout = settings["timeout"]


def _apply_profile_settings(
    config: Config, agent: Agent, client: OllamaClient, settings_json: str
) -> None:
    """Apply persisted profile settings to the agent and client.

    Flags given explicitly on the command line win over the saved settings.
    """
    try:
        settings = json.loads(settings_json)
    except json.JSONDecodeError:
        return
    if not isinstance(settings, dict):
        return
    config.features.load_saved(
        settings.get("disabled_features", []), settings.get("disabled_tools", [])
    )
    if settings.get("trust_level") in TRUST_LEVELS and not config.was_explicitly_set("--trust"):
        agent.trust_level = settings["trust_level"]
    if "model" in settings and not config.was_explicitly_set("--model"):
        agent.model = settings["model"]
    if "max_steps" in settings and not config.was_explicitly_set("--max-steps"):
        agent.max_turns = settings["max_steps"]
    args = config.get_args()
    if args:
        if "compression_threshold" in settings and not config.was_explicitly_set(
            "--compression-threshold"
        ):
            args.compression_threshold = settings["compression_threshold"]
        if "url" in settings and not config.was_explicitly_set("--url"):
            args.url = settings["url"]
            client.base_url = settings["url"]
            if settings.get("send_token") is False and not config.was_explicitly_set("--token"):
                client.token = None
    _apply_generation_settings(config, client, settings)


async def async_main() -> None:
    """Async entry point for the ``sensai`` console script."""
    config = Config()
    config.parse_args()

    console = Console()

    if _handle_list_personas(config, console):
        return

    database = setup_database(config)
    client, agent = setup_ai_engine(config)
    embedder = setup_embedder(config)

    profile = await authenticate_user(database, console)
    session = start_session(profile)

    if profile.settings:
        _apply_profile_settings(config, agent, client, profile.settings)
    persona = config.persona or load_profile_settings(profile).get("persona")
    _apply_persona(config, agent, console, persona)

    if config.files:
        # Attached files hang off a message, so the session has to exist first.
        session = ensure_persisted(database, session)
        set_current_session(session)
    await ingest_initial_files(
        database, embedder, session, config.files, console, features=config.features
    )

    app = CLIApp(
        agent=agent,
        database=database,
        session=session,
        client=client,
        config=config,
        profile_name=profile.name,
        embedder=embedder,
    )
    await app.run()


def main() -> None:
    """Entry point for the ``sensai`` console script."""
    asyncio.run(async_main())
