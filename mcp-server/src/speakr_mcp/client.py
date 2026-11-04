"""A small client for Speakr's REST API v1."""

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

DEFAULT_TIMEOUT = 60.0
# Chat, Inquire and uploads wait for a model or a large transfer. Gunicorn's
# own limit in the standard image is 600 seconds.
LONG_TIMEOUT = 600.0


class SpeakrError(ToolError):
    """A failed request, worded for the model that made it.

    It is a ToolError because the SDK replaces the message of any other
    exception with a generic one, and the model needs the reason to recover.
    """

    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _query_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return value


def _error_from(response: httpx.Response) -> SpeakrError:
    status = response.status_code
    if 300 <= status < 400:
        target = response.headers.get("location", "another address")
        return SpeakrError(
            f"Speakr redirected the request to {target}. Set SPEAKR_URL to the final address.", status
        )
    try:
        body = response.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return SpeakrError(f"Speakr answered {status}: {response.text[:200]}", status)

    code = body.get("code")
    message = str(body.get("error") or body.get("message") or f"Speakr answered {status}")
    if status == 401:
        message += " The token in SPEAKR_API_TOKEN is missing, expired or revoked."
    elif code == "insufficient_scope":
        message += f" (needs {body.get('required_scopes')}, the token has {body.get('token_scopes')})"
    elif status == 429:
        message += f" Try again in {response.headers.get('retry-after', 'a few')} seconds."
    return SpeakrError(message, status, code)


class SpeakrClient:
    def __init__(self, base_url: str, token: str, transport: httpx.AsyncBaseTransport | None = None):
        # Redirects are not followed: a redirected POST loses its body, and a
        # redirect to another host must not receive the token.
        self._http = httpx.AsyncClient(
            base_url=f"{base_url}/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=DEFAULT_TIMEOUT,
            transport=transport,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        query = {k: _query_value(v) for k, v in (params or {}).items() if v is not None}
        try:
            response = await self._http.request(
                method, path.lstrip("/"), params=query, json=json, data=data, files=files, timeout=timeout
            )
        except httpx.TimeoutException as exc:
            raise SpeakrError(
                f"Speakr did not answer within {timeout:.0f} seconds. The request may still have taken effect."
            ) from exc
        except httpx.TransportError as exc:
            raise SpeakrError(f"Cannot reach Speakr at {self._http.base_url}: {exc}") from exc

        if not response.is_success:
            raise _error_from(response)
        if response.status_code == 204 or not response.content:
            return {"success": True}
        try:
            return response.json()
        except ValueError as exc:
            raise SpeakrError(f"Speakr answered with something other than JSON: {response.text[:200]}") from exc

    async def get(self, path: str, **params: Any) -> Any:
        return await self.request("GET", path, params=params)


def fetch_token_scopes(base_url: str, token: str) -> list[str] | None:
    """The scopes of the token, or None when Speakr cannot say right now.

    Raises SpeakrError for a token Speakr refuses, because then no tool would work.
    """
    try:
        response = httpx.get(
            f"{base_url}/api/v1/tokens/current",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
    except httpx.HTTPError:
        return None
    if response.status_code == 401:
        raise _error_from(response)
    if not response.is_success:
        return None
    try:
        return response.json().get("scopes")
    except (ValueError, AttributeError):
        return None
