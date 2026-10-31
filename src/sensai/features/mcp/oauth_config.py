"""Parsing and validation of OAuth configuration for MCP connections."""

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
    if "redirectUri" not in value:
        raise ValueError(
            'OAuth requires "redirectUri": choose the callback URL for your environment.'
        )
    if "clientSecret" in value and "clientId" not in value:
        raise ValueError('OAuth "clientSecret" requires "clientId".')
    if "clientId" in value and "issuer" not in value:
        raise ValueError('A preregistered OAuth client requires its authorization "issuer" URL.')
    if "issuer" in value:
        validate_http_url(value["issuer"])
    return value


def _build_oauth_metadata(options: dict[str, Any]) -> OAuthClientMetadata:
    """Build SDK metadata using validated options and connection defaults."""
    redirect_uri = validate_http_url(options["redirectUri"])
    default_method = "client_secret_post" if "clientSecret" in options else "none"
    return OAuthClientMetadata.model_validate(
        {
            "client_name": "SensaiUwu CLI",
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
