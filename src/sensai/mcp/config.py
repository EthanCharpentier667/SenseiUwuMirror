"""Parsing and validation of HTTP MCP server configurations."""

import json
from dataclasses import dataclass, field
from typing import Self
from urllib.parse import urlparse


def validate_http_url(value: object) -> str:
    """Return an absolute HTTP URL or raise an actionable validation error."""
    if not isinstance(value, str):
        raise TypeError('The MCP configuration requires a string "url".')
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("The MCP URL must be an absolute HTTP or HTTPS URL.")
    return value


def _validate_headers(value: object) -> dict[str, str]:
    """Validate header names and values without coercing their types."""
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(header, str) for key, header in value.items()
    ):
        raise ValueError('MCP "headers" must be an object with string values.')
    return dict(value)


@dataclass(slots=True)
class MCPServerConfig:
    """Validated connection settings independent of the CLI."""

    url: str
    headers: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, raw_json: str) -> Self:
        """Parse the supported HTTP configuration and centralize JSON errors."""
        try:
            config = json.loads(raw_json)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid MCP JSON at line {error.lineno}, column {error.colno}: {error.msg}"
            ) from None
        if not isinstance(config, dict) or config.get("type") != "http":
            raise ValueError('The MCP configuration must be an object with "type": "http".')
        return cls(
            url=validate_http_url(config.get("url")),
            headers=_validate_headers(config.get("headers", {})),
        )
