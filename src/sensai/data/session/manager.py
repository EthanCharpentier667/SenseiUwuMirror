"""Manager for handling chat sessions, messages, and documents."""

from typing import Any

from sensai.client import OllamaClient, Response
from sensai.data.database.database import Database
from sensai.data.profile.manager import get_current_profile

from .message import Message, create_message
from .session import Session, add_session_usage, create_session, get_session, set_session_summary

HISTORY_CONTEXT_NOTE = (
    "Everything above, the conversation summary (if present) and the message history, "
    "already reflects what has been learned in this session, including the results of "
    "any earlier tool call. Treat the summary as authoritative for anything before it; "
    "the messages are only what happened since. Do not repeat a tool call for "
    "information already retrieved there. Use this context to answer the newest user "
    "message below."
)


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


def _profile_context_message(session: Session) -> dict[str, Any] | None:
    """A system message carrying the current profile's preferences and instructions.

    Only produced when the currently active profile (``ProfileManager.current_profile``)
    is the one the session belongs to, so a stale or mismatched current profile can't leak
    another user's preferences into this session.
    """
    profile = get_current_profile()
    if profile is None or profile.id != session.profile_id:
        return None

    lines = []
    if profile.preferences:
        lines.append(f"User preferences: {profile.preferences}")
    if profile.instructions:
        lines.append(f"Instructions (YOU MUST FOLLOW): {profile.instructions}")
    if not lines:
        return None
    return {"role": "system", "content": "\n".join(lines)}


def _context_prefix(session: Session) -> list[dict[str, Any]]:
    """Synthetic framing messages a ``build_messages()`` payload prepends ahead of history.

    These reflect live state (the owning profile's preferences/instructions, the session's
    running summary) recomputed fresh on every call. They're never persisted as messages in
    their own right, doing so would freeze a snapshot that goes stale the moment that state
    changes (e.g. via ``add_preference``), and would duplicate on every turn.
    """
    prefix: list[dict[str, Any]] = []
    profile_message = _profile_context_message(session)
    if profile_message is not None:
        prefix.append(profile_message)
    if session.summary:
        prefix.append(
            {"role": "system", "content": f"Conversation summary so far: {session.summary}"}
        )
    return prefix


def _history_context_suffix(session: Session) -> list[dict[str, Any]]:
    """A system message pre-empting the model from treating history as still pending.

    Placed right after the summary/history and before the new prompt, so "above" in its
    text is accurate. Without it, a model can mistake earlier turns (e.g. a tool call and
    its result) for part of the current, unresolved request, and repeat the tool call
    instead of reusing what it already retrieved. Only emitted when there's actually
    history to misread, as an empty session has nothing to be confused about.
    """
    if not session.summary and not _sendable_messages(session):
        return []
    return [{"role": "system", "content": HISTORY_CONTEXT_NOTE}]


def _history_prefix_length(session: Session) -> int:
    """The number of leading entries a ``build_messages()`` payload spends on known state.

    That's the synthetic context prefix, the still-unsummarized history messages, and the
    history-context note that everything before the new prompt for this turn.
    """
    return (
        len(_context_prefix(session))
        + len(_sendable_messages(session))
        + len(_history_context_suffix(session))
    )


def update_session(
    db: Database,
    session: Session,
    response: Response,
    sent_prefix_length: int | None = None,
) -> Session | None:
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
        sent_prefix_length (int, optional): The exact number of leading entries in
            ``response.messages`` that were already-known state when the request was
            actually sent, i.e. ``len(build_messages(session, prompt)) - 1`` at the time
            of that call. Passing this avoids recomputing the prefix from ``session``'s
            (and the current profile's) live state, which may have changed since the
            request went out. Defaults to recomputing it from ``session``'s current state.

    Returns:
        Session | None: The updated session if successful, otherwise None.
    """
    if session.id is None:
        return None
    prefix_length = (
        sent_prefix_length if sent_prefix_length is not None else _history_prefix_length(session)
    )
    new_messages = response.messages[prefix_length:]
    for message in new_messages:
        if message.role != "tool" and len(message.content.strip()) > 0:
            create_message(db, session.id, message.content, message.role, message.response_time)
    add_session_usage(
        db, session.id, response.prompt_eval_count, response.eval_count, response.token_used
    )
    return get_session(db, session.id)


def build_messages(session: Session, prompt: str) -> list[dict[str, Any]]:
    """Build the API-ready message list for a new prompt, prefixed with a session's history.

    Messages already folded into ``session.summary`` are replaced by a single system
    message carrying that summary, followed by whatever history hasn't been folded in yet.
    The owning profile's preferences and instructions, if any, are prefixed before all of that.

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
    return [
        *_context_prefix(session),
        *history,
        *_history_context_suffix(session),
        {"role": "user", "content": prompt},
    ]


async def compress_session(
    db: Database, session: Session, client: OllamaClient, model: str = "llama3.2"
) -> Session:
    """Fold a session's unsummarized history into its running summary via the LLM.

    Args:
        db (Database): The database to write to.
        session (Session): The session to compress.
        client (OllamaClient): The preconfigured client to summarize with.
        model (str): The model to summarize with. Callers should pass the model the
            session's own turns are using (e.g. ``response.model``) so the summary is
            produced by the same model the user configured, rather than silently falling
            back to the default.

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
    prompt = (
        f"Previous summary:\n{session.summary or '(none yet)'}\n\n"
        f"New conversation to fold in:\n{transcript}\n\n"
        "Rewrite this as a single, concise, updated summary of the whole conversation, "
        "preserving important facts, decisions and context needed to continue it."
    )
    response = await client.chat(
        messages=[{"role": "user", "content": prompt}], model=model, stream=False
    )

    last_folded_id = to_fold[-1].id
    if last_folded_id is None:
        raise ValueError("Cannot compress a session whose messages have no ID.")
    set_session_summary(db, session.id, response.response, last_folded_id)
    compressed = get_session(db, session.id)
    if compressed is None:
        raise ValueError(f"Failed to reload session {session.id} after compression.")
    return compressed


async def maybe_compress_session(
    db: Database,
    session: Session,
    response: Response,
    threshold: int,
    client: OllamaClient,
) -> Session:
    """Compress a session's history once its last prompt exceeded a token threshold.

    Args:
        db (Database): The database to write to.
        session (Session): The session to potentially compress.
        response (Response): The response of the turn just completed; its
            ``prompt_eval_count`` reflects the size of the prompt that was just sent,
            history and all.
        threshold (int): The prompt token count above which compression triggers.
            Callers get the default from ``Config.compression_threshold``.
        client (OllamaClient): The preconfigured client to summarize with.

    Returns:
        Session: The session, compressed if the threshold was exceeded.
    """
    if response.prompt_eval_count <= threshold:
        return session
    print(  # noqa: T201
        f"Prompt token count {response.prompt_eval_count} exceeded threshold {threshold}; "
        "compressing session history."
    )
    return await compress_session(db, session, client, model=response.model)


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
