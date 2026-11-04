"""Settings, read from the environment the MCP client starts the server with."""

from collections.abc import Mapping
from dataclasses import dataclass, field

# The API token scopes that have tools here. webhooks and account have none.
KNOWN_SCOPES = frozenset({"read", "write", "upload", "process", "share", "delete"})

# delete and share stay off until asked for, even with a full-access token.
# A transcript is text from whoever spoke in the recording, and a model reading
# it can be misled by it. What such text can do is limited to what these scopes
# allow: nothing here destroys a recording or publishes it to the internet.
DEFAULT_SCOPES = frozenset({"read", "write", "upload", "process"})


class ConfigError(Exception):
    """The server cannot start with these settings."""


@dataclass(frozen=True)
class Settings:
    url: str
    token: str = field(repr=False)
    scopes: frozenset[str] = DEFAULT_SCOPES

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        url = env.get("SPEAKR_URL", "").strip().rstrip("/")
        token = env.get("SPEAKR_API_TOKEN", "").strip()
        if not url:
            raise ConfigError("SPEAKR_URL is not set, for example https://speakr.example.com")
        if not url.startswith(("http://", "https://")):
            raise ConfigError(f"SPEAKR_URL must start with http:// or https://, not {url!r}")
        url = url.removesuffix("/api/v1")
        if not token:
            raise ConfigError("SPEAKR_API_TOKEN is not set. Create a token under Account Settings, API Tokens.")

        raw_scopes = env.get("SPEAKR_MCP_SCOPES", "").strip()
        if not raw_scopes:
            return cls(url=url, token=token)
        scopes = frozenset(s.strip() for s in raw_scopes.split(",") if s.strip())
        unknown = scopes - KNOWN_SCOPES
        if unknown:
            raise ConfigError(
                f"SPEAKR_MCP_SCOPES has unknown scopes {sorted(unknown)}; choose from {sorted(KNOWN_SCOPES)}"
            )
        return cls(url=url, token=token, scopes=scopes)


def effective_scopes(configured: frozenset[str], token_scopes: list[str] | None) -> frozenset[str]:
    """The scopes to offer tools for: what is configured and the token also allows.

    token_scopes is None when the token could not be asked; the API still
    refuses what the token lacks, so the configured scopes are offered.
    """
    if token_scopes is None or "full" in token_scopes:
        return configured
    return configured & frozenset(token_scopes)
