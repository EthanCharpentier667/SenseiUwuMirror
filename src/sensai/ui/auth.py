"""Authentication wizard and UI commands for managing the active profile."""

from prompt_toolkit import PromptSession
from rich.console import Console

from sensai.core.state import get_saved_credentials, save_credentials
from sensai.data.database.database import Database
from sensai.data.profile.manager import create_new_profile, login
from sensai.data.profile.profile import Profile


def _attempt_auto_login(database: Database, console: Console) -> Profile | None:
    saved_user, saved_pwd = get_saved_credentials()
    if not (saved_user and saved_pwd):
        return None

    console.print(f"[dim]Attempting auto-login for '{saved_user}'...[/dim]")
    profile = login(saved_user, saved_pwd, database)
    if profile:
        console.print(f"[bold green]✓ Welcome back, {profile.name}![/bold green]")
        return profile

    console.print("[yellow]Auto-login failed. Credentials might be invalid.[/yellow]")
    return None


async def _handle_create_profile(
    database: Database, console: Console, session: PromptSession[str], username: str, password: str
) -> Profile | None:
    console.print("[yellow]Login failed. User not found or incorrect password.[/yellow]")
    choice = await session.prompt_async("Create a new profile with these credentials? [y/N]: ")
    if choice.strip().lower() in {"y", "yes", "o", "oui"}:
        try:
            profile = create_new_profile(database, username, password)
        except Exception as e:  # noqa: BLE001
            console.print(f"[bold red]Failed to create profile: {e}[/bold red]")
        else:
            console.print(f"[bold green]✓ Profile '{profile.name}' created![/bold green]")
            save_credentials(username, password)
            return profile
    return None


async def authenticate_user(database: Database, console: Console) -> Profile:
    """Run the authentication wizard to connect or create a profile.

    Args:
        database (Database): The active database connection.
        console (Console): The rich console for output.

    Returns:
        Profile: The authenticated or newly created profile.
    """
    profile = _attempt_auto_login(database, console)
    if profile:
        return profile

    console.print("\n[bold cyan]--- Sensai Authentication ---[/bold cyan]")
    session: PromptSession[str] = PromptSession()

    while True:
        username = await session.prompt_async("Username: ")
        if not username.strip():
            continue

        password = await session.prompt_async("Password: ", is_password=True)
        if not password:
            continue

        profile = login(username, password, database)
        if profile:
            console.print(f"[bold green]✓ Successfully logged in as {profile.name}.[/bold green]")
            save_credentials(username, password)
            return profile

        new_profile = await _handle_create_profile(database, console, session, username, password)
        if new_profile:
            return new_profile
