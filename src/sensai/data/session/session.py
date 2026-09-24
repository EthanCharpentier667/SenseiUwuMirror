"""Session for handling chat sessions data, including messages and documents."""

from typing import TYPE_CHECKING, cast

from peewee import SQL, CharField, DateTimeField, ForeignKeyField, IntegerField, TextField

from sensai.data.database.base_model import BaseModel
from sensai.data.profile.profile import Profile

from .message import Message, get_messages_by_session

if TYPE_CHECKING:
    from sensai.data.database.database import Database


class Session(BaseModel):
    """A chat session, mirroring the `session` table, with its messages."""

    profile = ForeignKeyField(Profile, on_delete="CASCADE")
    profile_id: int
    name = CharField(null=True)
    prompt_eval_count = IntegerField(default=0)
    eval_count = IntegerField(default=0)
    token_used = IntegerField(default=0)
    summary = TextField(null=True)
    summarized_message = ForeignKeyField(Message, null=True, on_delete="SET NULL")
    summarized_message_id: int | None
    created_at = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    messages: list[Message]

    def __init__(
        self, *args: object, messages: list[Message] | None = None, **kwargs: object
    ) -> None:
        """Initialize a session, defaulting `messages` to an empty list like the fetch helpers do.

        Args:
            *args: Positional arguments to pass to the parent constructor.
            messages (list[Message] | None): The list of messages for the session. Default is None.
            **kwargs: Keyword arguments to pass to the parent constructor.
        """
        super().__init__(*args, **kwargs)
        self.messages = messages if messages is not None else []


def _with_messages(db: "Database", session: Session) -> Session:
    session.messages = get_messages_by_session(db, cast("int", session.id))
    return session


def create_session(db: "Database", profile_id: int, name: str | None = None) -> Session:
    """Create a new session for the given profile.

    Args:
        db (Database): The database to write to.
        profile_id (int): The ID of the profile the session belongs to.
        name (str, optional): A display name for the session. Default is None.

    Returns:
        Session: The newly created session, including its assigned ID.
    """
    with db.database.bind_ctx([Session]):
        session = Session.create(profile=profile_id, name=name)
    return _with_messages(db, session)


def get_session(db: "Database", session_id: int) -> Session | None:
    """Retrieve a session by its ID.

    Args:
        db (Database): The database to read from.
        session_id (int): The unique identifier for the session.

    Returns:
        Session | None: The session if found, otherwise None.
    """
    with db.database.bind_ctx([Session]):
        session = Session.get_or_none(Session.id == session_id)
    return _with_messages(db, session) if session is not None else None


def rename_session(db: "Database", session_id: int, name: str) -> None:
    """Update a session's name.

    Args:
        db (Database): The database to write to.
        session_id (int): The unique identifier for the session.
        name (str): The new name for the session.
    """
    with db.database.bind_ctx([Session]):
        Session.update(name=name).where(Session.id == session_id).execute()


def set_session_summary(
    db: "Database", session_id: int, summary: str, summarized_message_id: int
) -> None:
    """Persist a session's rolling summary and how much history it covers.

    Args:
        db (Database): The database to write to.
        session_id (int): The unique identifier for the session.
        summary (str): The updated summary text, replacing any previous one.
        summarized_message_id (int): The ID of the latest message folded into the summary;
            messages with a lower or equal ID are omitted from future prompts.
    """
    with db.database.bind_ctx([Session]):
        Session.update(summary=summary, summarized_message=summarized_message_id).where(
            Session.id == session_id
        ).execute()


def add_session_usage(
    db: "Database", session_id: int, prompt_eval_count: int, eval_count: int, token_used: int
) -> None:
    """Accumulate token usage onto a session's running totals.

    Args:
        db (Database): The database to write to.
        session_id (int): The unique identifier for the session.
        prompt_eval_count (int): The prompt evaluation count to add.
        eval_count (int): The evaluation count to add.
        token_used (int): The number of tokens used to add.
    """
    with db.database.bind_ctx([Session]):
        Session.update(
            prompt_eval_count=Session.prompt_eval_count + prompt_eval_count,
            eval_count=Session.eval_count + eval_count,
            token_used=Session.token_used + token_used,
        ).where(Session.id == session_id).execute()
