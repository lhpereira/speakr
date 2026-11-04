import json
from collections.abc import Callable

import httpx
import pytest
from mcp import Client

from speakr_mcp.client import SpeakrClient
from speakr_mcp.config import DEFAULT_SCOPES, KNOWN_SCOPES
from speakr_mcp.server import build_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeSpeakr:
    """Answers API requests from a table and remembers them."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response] | httpx.Response] = {}

    def on(self, method: str, path: str, body=None, status: int = 200, headers=None):
        self.routes[(method, f"/api/v1/{path}")] = httpx.Response(status, json=body, headers=headers)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.routes.get((request.method, request.url.path))
        if answer is None:
            return httpx.Response(404, json={"error": f"no route {request.method} {request.url.path}"})
        return answer(request) if callable(answer) else answer

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    @property
    def last_json(self):
        return json.loads(self.last.content)


@pytest.fixture
def speakr():
    return FakeSpeakr()


@pytest.fixture
def api(speakr):
    return SpeakrClient("https://speakr.test", "secret-token", transport=httpx.MockTransport(speakr))


@pytest.fixture
def connect(api):
    """A real MCP client connected in memory to a server with these scopes."""

    def _connect(scopes=DEFAULT_SCOPES):
        return Client(build_server(api, frozenset(scopes)))

    return _connect


@pytest.fixture
def all_scopes():
    return KNOWN_SCOPES


async def call(client: Client, tool: str, **arguments):
    """The tool's JSON result. Fails if the call reported an error."""
    result = await client.call_tool(tool, arguments)
    text = result.content[0].text
    assert not result.is_error, text
    return json.loads(text)


async def call_error(client: Client, tool: str, **arguments) -> str:
    """The message of a call that must fail."""
    result = await client.call_tool(tool, arguments)
    assert result.is_error, result.content
    return result.content[0].text
