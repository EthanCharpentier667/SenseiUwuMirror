"""Streaming thought extractor for ReAct planning responses."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    ChunkCallback = Callable[[str], Awaitable[None]]

UNICODE_HEX_LENGTH = 4
ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    '"': '"',
    "\\": "\\",
    "/": "/",
}


class StreamingThoughtExtractor:
    r"""Extracts and streams thoughts from an Ollama planning response in real time.

    Handles:
    - The JSON field ``"thought": "..."`` defined in ``ReActController.schema()``.
    - Escaped characters inside the JSON string (\", \n, \t, \uXXXX).
    - Optional ``<think>...</think>`` reasoning tags emitted by thinking models.
    """

    _SEEKING = 0
    _IN_THINK_TAG = 1
    _IN_JSON_THOUGHT = 2
    _DONE = 3

    def __init__(self, on_chunk: ChunkCallback | None) -> None:
        """Initialize the extractor.

        Args:
            on_chunk: Async callback receiving each piece of thought text.
        """
        self.on_chunk = on_chunk
        self.has_emitted_thought: bool = False
        self._state = self._SEEKING
        self._search_buffer: str = ""
        self._tag_buffer: str = ""
        self._escape: bool = False
        self._unicode_buffer: str | None = None

    async def _emit(self, text: str) -> None:
        """Send a chunk of thought text to the callback.

        Args:
            text: Thought string fragment to deliver.
        """
        if not text:
            return
        self.has_emitted_thought = True
        if self.on_chunk is not None:
            await self.on_chunk(text)

    def _process_seeking(self, char: str) -> None:
        self._search_buffer += char
        if "<think>" in self._search_buffer:
            self._state = self._IN_THINK_TAG
            self._search_buffer = ""
            self._tag_buffer = ""
        elif re.search(r'"thought"\s*:\s*"', self._search_buffer):
            self._state = self._IN_JSON_THOUGHT
            self._search_buffer = ""

    def _process_think_tag(self, char: str, emitted: list[str]) -> None:
        self._tag_buffer += char
        if "</think>" in self._tag_buffer:
            content, _, _ = self._tag_buffer.partition("</think>")
            if content:
                emitted.append(content)
            self._tag_buffer = ""
            self._state = self._SEEKING
        else:
            target = "</think>"
            is_prefix = any(self._tag_buffer.endswith(target[:k]) for k in range(1, len(target)))
            if not is_prefix:
                emitted.append(self._tag_buffer)
                self._tag_buffer = ""

    def _handle_unicode_escape(self, char: str, emitted: list[str]) -> None:
        if self._unicode_buffer is None:
            return
        self._unicode_buffer += char
        if len(self._unicode_buffer) == UNICODE_HEX_LENGTH:
            try:
                emitted.append(chr(int(self._unicode_buffer, 16)))
            except ValueError:
                emitted.append(f"\\u{self._unicode_buffer}")
            self._unicode_buffer = None

    def _process_json_thought(self, char: str, emitted: list[str]) -> None:
        if self._unicode_buffer is not None:
            self._handle_unicode_escape(char, emitted)
            return

        if self._escape:
            self._escape = False
            if char in ESCAPES:
                emitted.append(ESCAPES[char])
            elif char == "u":
                self._unicode_buffer = ""
            else:
                emitted.append(f"\\{char}")
            return

        if char == "\\":
            self._escape = True
            return

        if char == '"':
            self._state = self._DONE
            return

        emitted.append(char)

    async def feed(self, chunk: str) -> None:
        """Process an incoming stream chunk from Ollama.

        Args:
            chunk: Text fragment received from the streaming HTTP response.
        """
        if not chunk or self._state == self._DONE:
            return

        emitted_parts: list[str] = []

        for char in chunk:
            if self._state == self._DONE:
                break
            if self._state == self._SEEKING:
                self._process_seeking(char)
            elif self._state == self._IN_THINK_TAG:
                self._process_think_tag(char, emitted_parts)
            elif self._state == self._IN_JSON_THOUGHT:
                self._process_json_thought(char, emitted_parts)

        if emitted_parts:
            await self._emit("".join(emitted_parts))
