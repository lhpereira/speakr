"""Entry point: `speakr-mcp` or `python -m speakr_mcp`. Speaks MCP over stdio."""

import os
import sys

from .client import SpeakrClient, SpeakrError, fetch_token_scopes
from .config import ConfigError, Settings, effective_scopes
from .server import build_server


def main() -> None:
    # stdout carries the protocol, so everything for people goes to stderr.
    try:
        settings = Settings.from_env(os.environ)
        token_scopes = fetch_token_scopes(settings.url, settings.token)
    except (ConfigError, SpeakrError) as exc:
        sys.exit(f"speakr-mcp: {exc}")

    if token_scopes is None:
        print(
            f"speakr-mcp: could not read the token's scopes from {settings.url}; "
            "offering the configured tools, and Speakr will refuse what the token lacks.",
            file=sys.stderr,
        )
    scopes = effective_scopes(settings.scopes, token_scopes)
    if not scopes:
        sys.exit(
            f"speakr-mcp: the token's scopes {token_scopes} and SPEAKR_MCP_SCOPES {sorted(settings.scopes)} "
            "have nothing in common, so there are no tools to offer."
        )

    build_server(SpeakrClient(settings.url, settings.token), scopes).run("stdio")


if __name__ == "__main__":
    main()
