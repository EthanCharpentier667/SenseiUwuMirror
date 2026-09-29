"""Orchestration and setup functions for Sensai components."""

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.data.database.database import Database
from sensai.data.profile.manager import add_instruction, add_preference, create_new_profile, login
from sensai.data.profile.profile import Profile
from sensai.data.session.manager import create_new_session
from sensai.data.session.session import Session
from sensai.tools.registry import get_all_tools
from sensai.ui.cli import CLIHandler


def setup_database(config: Config) -> Database:
    """Initialize and return the database connection."""
    database = Database(config.db_path, config.db_name)
    database.initialize()
    return database


def setup_ai_engine(config: Config) -> tuple[OllamaClient, Agent]:
    """Initialize and return the Ollama client and Agent."""
    client = OllamaClient(
        base_url=config.url,
        token=config.token,
        timeout=config.timeout,
    )
    ui_handler = CLIHandler()
    agent = Agent(
        model=config.model,
        tools=get_all_tools(),
        human_in_the_loop=True,
        ui_handler=ui_handler,
        client=client,
    )
    return client, agent


def ensure_dev_profile(database: Database) -> Profile:
    """Create or load the default development profile."""
    profile_name = "Ethan"
    profile_secret_not_secret = "667"  # noqa: S105

    profile = login(profile_name, profile_secret_not_secret, database)
    if profile is None:
        profile = create_new_profile(database, profile_name, profile_secret_not_secret)
        add_preference(database, "User prefer French language.")
        add_instruction(database, 'replace all the ponctuation by "uwu"')

    if profile.id is None:
        msg = "Failed to create the default profile; no ID was returned."
        raise ValueError(msg)

    return profile


def get_or_create_session(database: Database, profile: Profile) -> Session:
    """Create or load a test session for the profile."""
    if profile.id is None:
        msg = "Profile ID cannot be None when creating a session."
        raise ValueError(msg)

    session: Session | None = create_new_session(database, profile.id, "test_session")
    if session is None:
        msg = "Failed to create the default session."
        raise ValueError(msg)
    return session
