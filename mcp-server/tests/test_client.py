import httpx
import pytest

from speakr_mcp.client import SpeakrClient, SpeakrError, fetch_token_scopes

pytestmark = pytest.mark.anyio


async def test_sends_the_token_in_the_header(speakr, api):
    speakr.on("GET", "stats", {})
    await api.get("stats")
    assert speakr.last.headers["authorization"] == "Bearer secret-token"
    assert "secret-token" not in str(speakr.last.url)


async def test_query_values_are_sent_as_the_api_reads_them(speakr, api):
    speakr.on("GET", "recordings", {})
    await api.get("recordings", inbox=True, starred=False, recording_ids=[1, 2], q=None)
    assert dict(speakr.last.url.params) == {"inbox": "true", "starred": "false", "recording_ids": "1,2"}


async def test_no_content_is_a_success(speakr, api):
    speakr.routes[("DELETE", "/api/v1/shares/1")] = httpx.Response(204)
    assert await api.request("DELETE", "shares/1") == {"success": True}


@pytest.mark.parametrize(
    ("status", "body", "headers", "expected"),
    [
        (401, {"error": "Authentication required"}, None, "SPEAKR_API_TOKEN"),
        (404, {"error": "Recording not found"}, None, "Recording not found"),
        (429, {"error": "Rate limit reached", "code": "token_rate_limit_exceeded"}, {"Retry-After": "17"}, "in 17 seconds"),
        (
            403,
            {"error": "No", "code": "insufficient_scope", "required_scopes": ["write"], "token_scopes": ["read"]},
            None,
            "needs ['write'], the token has ['read']",
        ),
    ],
)
async def test_errors_tell_the_model_what_to_do(speakr, api, status, body, headers, expected):
    speakr.on("GET", "stats", body, status=status, headers=headers)
    with pytest.raises(SpeakrError, match=expected.replace("[", r"\[").replace("]", r"\]")) as caught:
        await api.get("stats")
    assert caught.value.status == status


async def test_a_redirect_is_not_followed(speakr, api):
    speakr.routes[("POST", "/api/v1/recordings/upload")] = httpx.Response(
        301, headers={"Location": "https://other.test/api/v1/recordings/upload"}
    )
    with pytest.raises(SpeakrError, match="https://other.test"):
        await api.request("POST", "recordings/upload")
    assert len(speakr.requests) == 1


async def test_a_page_instead_of_json_is_reported(speakr, api):
    speakr.routes[("GET", "/api/v1/stats")] = httpx.Response(200, text="<html>proxy login</html>")
    with pytest.raises(SpeakrError, match="other than JSON"):
        await api.get("stats")


async def test_a_gateway_error_page_is_reported(speakr, api):
    speakr.routes[("GET", "/api/v1/stats")] = httpx.Response(502, text="Bad gateway")
    with pytest.raises(SpeakrError, match="502: Bad gateway"):
        await api.get("stats")


@pytest.mark.parametrize(
    ("failure", "expected"),
    [(httpx.ConnectError("refused"), "Cannot reach Speakr"), (httpx.ReadTimeout("slow"), "may still have taken effect")],
)
async def test_network_failures_become_tool_errors(failure, expected):
    def fail(request):
        raise failure

    api = SpeakrClient("https://speakr.test", "t", transport=httpx.MockTransport(fail))
    with pytest.raises(SpeakrError, match=expected):
        await api.get("stats")


def _answer(monkeypatch, response):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: response)


def test_token_scopes_are_read(monkeypatch):
    _answer(monkeypatch, httpx.Response(200, json={"scopes": ["read"]}))
    assert fetch_token_scopes("https://speakr.test", "t") == ["read"]


def test_a_refused_token_stops_the_start(monkeypatch):
    _answer(monkeypatch, httpx.Response(401, json={"error": "Invalid token"}))
    with pytest.raises(SpeakrError, match="SPEAKR_API_TOKEN"):
        fetch_token_scopes("https://speakr.test", "t")


def test_an_older_speakr_is_not_an_error(monkeypatch):
    _answer(monkeypatch, httpx.Response(404, json={"error": "Not found"}))
    assert fetch_token_scopes("https://speakr.test", "t") is None


def test_speakr_being_down_is_not_an_error(monkeypatch):
    def refuse(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "get", refuse)
    assert fetch_token_scopes("https://speakr.test", "t") is None
