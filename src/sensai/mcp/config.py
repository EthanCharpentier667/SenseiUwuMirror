"""Parsing and validation of HTTP MCP server configurations."""

import json
from typing import Any, Self
from urllib.parse import urlparse

from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata
from pydantic import ValidationError


class OAuthConfig:
    """Validated OAuth metadata and optional preregistered credentials."""

    def __init__(
        self, metadata: OAuthClientMetadata, client_info: OAuthClientInformationFull | None = None
    ) -> None:
        """Store provider settings without exposing credentials in representation."""
        self.metadata = metadata
        self.client_info = client_info

    @classmethod
    def from_dict(cls, value: object) -> Self:
        """Validate OAuth JSON options before beginning authorization."""
        options = _validate_oauth_options(value)
        try:
            metadata = _build_oauth_metadata(options)
            client_info = _build_oauth_client_info(options, metadata)
        except ValidationError:
            raise ValueError(
                "Invalid OAuth metadata or token endpoint authentication method."
            ) from None
        return cls(metadata, client_info)


def _validate_oauth_options(value: object) -> dict[str, Any]:
    """Check option types, required credentials and authorization issuer."""
    if not isinstance(value, dict):
        raise TypeError('MCP "oauth" must be an object.')
    for key in ("redirectUri", "scope", "clientId", "clientSecret", "issuer"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError(f'OAuth "{key}" must be a non-empty string.')
    if "clientSecret" in value and "clientId" not in value:
        raise ValueError('OAuth "clientSecret" requires "clientId".')
    if "clientId" in value and "issuer" not in value:
        raise ValueError('A preregistered OAuth client requires its authorization "issuer" URL.')
    if "issuer" in value:
        validate_http_url(value["issuer"])
    return value


def _build_oauth_metadata(options: dict[str, Any]) -> OAuthClientMetadata:
    """Build SDK metadata using validated options and connection defaults."""
    redirect_uri = validate_http_url(options.get("redirectUri", "http://localhost:8080/callback"))
    default_method = "client_secret_post" if "clientSecret" in options else "none"
    return OAuthClientMetadata.model_validate(
        {
            "client_name": "Sensai CLI",
            "redirect_uris": [redirect_uri],
            "scope": options.get("scope"),
            "token_endpoint_auth_method": options.get("tokenEndpointAuthMethod", default_method),
        }
    )


def _build_oauth_client_info(
    options: dict[str, Any], metadata: OAuthClientMetadata
) -> OAuthClientInformationFull | None:
    """Build preregistered credentials when a client ID is provided."""
    if "clientId" not in options:
        return None
    return OAuthClientInformationFull.model_validate(
        {
            **metadata.model_dump(),
            "client_id": options["clientId"],
            "client_secret": options.get("clientSecret"),
            "issuer": options["issuer"],
        }
    )


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


class MCPServerConfig:
    """Validated connection settings independent of the CLI."""

    def __init__(
        self, url: str, headers: dict[str, str] | None = None, oauth: OAuthConfig | None = None
    ) -> None:
        """Store connection settings with independent headers for each instance."""
        self.url = url
        self.headers = dict(headers) if headers is not None else {}
        self.oauth = oauth
        if oauth is not None and any(key.lower() == "authorization" for key in self.headers):
            raise ValueError("Choose OAuth or an Authorization header for this MCP connection.")

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
            oauth=OAuthConfig.from_dict(config["oauth"]) if "oauth" in config else None,
        )
