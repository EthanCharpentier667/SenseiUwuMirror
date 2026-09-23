"""Manager for handling chat sessions, messages, and documents."""

from typing import Any

from sensai.data.database.database import Database
from sensai.requester import Response, get_sensei_response

from .message import Message, create_message
from .session import Session, add_session_usage, create_session, get_session, set_session_summary

DEFAULT_COMPRESSION_TOKEN_THRESHOLD = 3000


class SessionManager:
    """Holds the process-wide currently active session."""

    current_session: Session | None = None


def get_current_session() -> Session | None:
    """Retrieve the current active session.

    Returns:
        Session | None: The current session if set, otherwise None.
    """
    return SessionManager.current_session


def set_current_session(session: Session) -> None:
    """Set the current active session.

    Args:
        session (Session): The session to set as current.
    """
    SessionManager.current_session = session


def clear_current_session() -> None:
    """Clear the current active session."""
    SessionManager.current_session = None


def create_new_session(db: Database, profile_id: int, name: str | None = None) -> Session:
    """Create a new session for the given profile and set it as the current session.

    Args:
        db (Database): The database to write to.
        profile_id (int): The ID of the profile the session belongs to.
        name (str, optional): A display name for the session. Default is None.

    Returns:
        Session: The newly created session, including its assigned ID.
    """
    session = create_session(db, profile_id, name)
    set_current_session(session)
    return session


def _sendable_messages(session: Session) -> list[Message]:
    """A session's messages that still need to be sent verbatim to the API.

    Messages folded into ``session.summary`` (their id is at or below
    ``summarized_message_id``) are represented by the summary instead, so they're excluded.
    """
    if session.summarized_message_id is None:
        return session.messages
    return [
        message
        for message in session.messages
        if message.id is not None and message.id > session.summarized_message_id
    ]


def _history_prefix_length(session: Session) -> int:
    """The number of leading entries a ``build_messages()`` payload spends on known state.

    That's the optional summary line plus the still-unsummarized history messages —
    everything before the new prompt for this turn.
    """
    return len(_sendable_messages(session)) + (1 if session.summary else 0)


def update_session(db: Database, session: Session, response: Response) -> Session | None:
    """Persist a response's new messages and usage onto an existing session.

    ``response.messages`` echoes everything sent to the API for this exchange, which
    includes the session's known state (summary plus unsummarized history) when the
    request was built with ``build_messages``. Only the messages past that prefix are
    new to this turn, so only those are persisted here to avoid re-inserting duplicates
    of past messages or turning the summary line into a stored message.

    Args:
        db (Database): The database to write to.
        session (Session): The session to update.
        response (Response): The response to persist.

    Returns:
        Session | None: The updated session if successful, otherwise None.
    """
    if session.id is None:
        return None
    new_messages = response.messages[_history_prefix_length(session) :]
    for message in new_messages:
        add_message_to_current_session(db, message.content, message.role, message.response_time)
    add_session_usage(
        db, session.id, response.prompt_eval_count, response.eval_count, response.token_used
    )
    return get_session(db, session.id)


def build_messages(session: Session, prompt: str) -> list[dict[str, Any]]:
    """Build the API-ready message list for a new prompt, prefixed with a session's history.

    Messages already folded into ``session.summary`` are replaced by a single system
    message carrying that summary, followed by whatever history hasn't been folded in yet.

    Args:
        session (Session): The session whose summary and persisted messages provide context.
        prompt (str): The new user prompt to append after the session's history.

    Returns:
        list[dict[str, Any]]: The conversation history followed by the new prompt, in the
            raw ``{"role": ..., "content": ...}`` shape the Sensei API expects.
    """
    history = [
        {"role": message.role, "content": message.content}
        for message in _sendable_messages(session)
    ]
    if session.summary:
        history = [
            {"role": "system", "content": f"Conversation summary so far: {session.summary}"},
            *history,
        ]
    return [*history, {"role": "user", "content": prompt}]


def compress_session(db: Database, session: Session) -> Session:
    """Fold a session's unsummarized history into its running summary via the LLM.

    Args:
        db (Database): The database to write to.
        session (Session): The session to compress.

    Returns:
        Session: The session refreshed from the database, or unchanged if there was no
            unsummarized history to fold in.

    Raises:
        ValueError: If the session, or its unsummarized messages, have no ID.
    """
    if session.id is None:
        raise ValueError("Session does not have a valid ID.")
    to_fold = _sendable_messages(session)
    if not to_fold:
        return session

    transcript = "\n".join(f"{message.role}: {message.content}" for message in to_fold)
    print(f"Compressing session {session.id} with {len(to_fold)}")  # noqa: T201
    prompt = (
        f"Previous summary:\n{session.summary or '(none yet)'}\n\n"
        f"New conversation to fold in:\n{transcript}\n\n"
        "Rewrite this as a single, concise, updated summary of the whole conversation, "
        "preserving important facts, decisions and context needed to continue it."
    )
    response = get_sensei_response(prompt=prompt, stream=False)

    last_folded_id = to_fold[-1].id
    if last_folded_id is None:
        raise ValueError("Cannot compress a session whose messages have no ID.")
    set_session_summary(db, session.id, response.response, last_folded_id)
    compressed = get_session(db, session.id)
    if compressed is None:
        raise ValueError(f"Failed to reload session {session.id} after compression.")
    return compressed


def maybe_compress_session(
    db: Database,
    session: Session,
    response: Response,
    threshold: int = DEFAULT_COMPRESSION_TOKEN_THRESHOLD,
) -> Session:
    """Compress a session's history once its last prompt exceeded a token threshold.

    Args:
        db (Database): The database to write to.
        session (Session): The session to potentially compress.
        response (Response): The response of the turn just completed; its
            ``prompt_eval_count`` reflects the size of the prompt that was just sent,
            history and all.
        threshold (int): The prompt token count above which compression triggers.
            Default is 3000.

    Returns:
        Session: The session, compressed if the threshold was exceeded.
    """
    if response.prompt_eval_count <= threshold:
        return session
    return compress_session(db, session)


def get_session_by_id(db: Database, session_id: int) -> Session | None:
    """Retrieve a session by its ID.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        Session | None: The session if found, otherwise None.
    """
    return get_session(db, session_id)


def get_current_session_id() -> int | None:
    """Retrieve the ID of the current active session.

    Returns:
        int | None: The ID of the current session if set, otherwise None.
    """
    current_session = get_current_session()
    return current_session.id if current_session else None


def is_current_session(session_id: int) -> bool:
    """Check if the given session ID matches the current active session.

    Args:
        session_id (int): The session ID to check.

    Returns:
        bool: True if the given session ID matches the current session, otherwise False.
    """
    current_session = get_current_session()
    return current_session is not None and current_session.id == session_id


def add_message_to_current_session(
    db: Database, content: str, role: str, response_time: float
) -> None:
    """Add a new message to the current active session.

    Args:
        db (Database): The database to write to.
        content (str): The message content.
        role (str): The role of the message's author (e.g. "user", "assistant", "tool").
        response_time (float): The time the message became available, in seconds since the epoch.

    Raises:
        ValueError: If there is no current active session.
    """
    current_session = get_current_session()
    if current_session is None:
        raise ValueError("No current session is set.")

    current_session_id = current_session.id
    if current_session_id is None:
        raise ValueError("Current session does not have a valid ID.")
    create_message(db, current_session_id, content, role, response_time)
