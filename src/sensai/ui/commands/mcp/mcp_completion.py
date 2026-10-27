"""Autocomplete JSON configurations for MCP connections."""

import json
import shlex
from collections.abc import Iterable
from io import StringIO

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document


def _json_argument(text: str) -> str | None:
    """Read the three complete shell arguments before the unfinished JSON."""
    stream = StringIO(text + "\n")
    lexer = shlex.shlex(stream, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        if lexer.get_token() != "/mcp" or lexer.get_token() != "add-json":
            return None
        name = lexer.get_token()
    except ValueError:
        return None
    if not name or not name.strip() or stream.tell() > len(text):
        return None
    return text[stream.tell() :].lstrip()


class MCPConfigCompleter(Completer):  # type: ignore[misc,unused-ignore]
    """Suggest shell-quoted JSON configurations after the MCP server name."""

    def get_completions(
        self, document: Document, _complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        """Complete an empty JSON argument or the beginning of a suggested template."""
        if document.text_after_cursor.strip():
            return
        raw_json = _json_argument(document.text_before_cursor)
        if raw_json is None:
            return

        prefix = raw_json[1:] if raw_json.startswith(("'", '"')) else raw_json
        base = {"url": "https://example.com/mcp"}
        templates = [
            ("HTTP", base),
            ("HTTP + Bearer token", {**base, "headers": {"Authorization": "Bearer YOUR_TOKEN"}}),
            (
                "HTTP + OAuth",
                {**base, "oauth": {"redirectUri": "https://your-callback.example/callback"}},
            ),
        ]
        for label, config in templates:
            json_text = json.dumps(config)
            if json_text.startswith(prefix):
                yield Completion(
                    shlex.quote(json_text),
                    start_position=-len(raw_json),
                    display=label,
                    display_meta="Customize the server URL, callback URL and any token.",
                )
