"""The real server process, over stdio, against a real Speakr. See docker-compose.yml."""

import json
import os
import struct
import sys
import time
import wave

import anyio
import pytest
from mcp import Client, StdioServerParameters

URL = os.environ.get("SPEAKR_MCP_E2E_URL")

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not URL, reason="needs the stack in tests/e2e/docker-compose.yml"),
]


@pytest.fixture(scope="module")
def seed():
    with open(os.environ["SPEAKR_MCP_E2E_SEED"], encoding="utf-8") as f:
        return json.load(f)


def server_env(token):
    return {
        "SPEAKR_URL": URL,
        "SPEAKR_API_TOKEN": token,
        "PATH": os.environ["PATH"],
        "PYTHONPATH": os.environ["PYTHONPATH"],
    }


def server(token, scopes=None):
    env = server_env(token)
    if scopes:
        env["SPEAKR_MCP_SCOPES"] = scopes
    return Client(StdioServerParameters(command=sys.executable, args=["-m", "speakr_mcp"], env=env))


async def call(client, tool, **arguments):
    result = await client.call_tool(tool, arguments)
    text = result.content[0].text
    assert not result.is_error, f"{tool}: {text}"
    return json.loads(text)


async def error(client, tool, **arguments):
    result = await client.call_tool(tool, arguments)
    assert result.is_error, result.content
    return result.content[0].text


async def names(client):
    return {tool.name for tool in (await client.list_tools()).tools}


async def wait_until_done(client, recording_id):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        status = await call(client, "get_recording_status", recording_id=recording_id)
        if status["status"] in ("COMPLETED", "FAILED"):
            return status
        await anyio.sleep(1)
    pytest.fail(f"recording {recording_id} still {status['status']}")


def write_wav(path, seconds=2):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"".join(struct.pack("<h", (i % 100) * 200) for i in range(16000 * seconds)))


async def test_connection_info_describes_the_instance(seed):
    async with server(seed["tokens"]["full"]) as client:
        info = await call(client, "get_connection_info")
    assert info["token"]["scopes"] == ["full"]
    assert "features" in info["instance"]


async def test_full_token_still_gets_no_delete_tools_by_default(seed):
    async with server(seed["tokens"]["full"]) as client:
        tools = await names(client)
    assert "delete_recording" not in tools
    assert "create_share_link" not in tools
    assert "get_transcript" in tools


async def test_tools_follow_the_real_scopes_of_the_token(seed):
    async with server(seed["tokens"]["read_only"]) as client:
        tools = await names(client)
    assert "get_transcript" in tools
    assert "update_recording" not in tools
    async with server(seed["tokens"]["upload_only"]) as client:
        assert await names(client) == {"get_connection_info", "upload_recording"}


async def test_reading_a_recording(seed):
    recording_id = seed["recording_id"]
    async with server(seed["tokens"]["read_only"]) as client:
        listed = await call(client, "list_recordings", q="orçamento")
        assert [r["id"] for r in listed["recordings"]] == [recording_id]
        details = await call(client, "get_recording", recording_id=recording_id)
        assert details["participants"] == "Dana, Omar"
        assert "transcription" not in details
        assert "orçamento" in (await call(client, "get_summary", recording_id=recording_id))["summary"]
        assert (await call(client, "get_notes", recording_id=recording_id))["has_notes"]
        for tool in ("get_stats", "get_current_user", "list_tags", "list_folders", "list_speakers",
                     "get_transcription_options"):
            await call(client, tool)
        await call(client, "get_recording_events", recording_id=recording_id)
        assert await call(client, "get_recording_speakers", recording_id=recording_id)


async def test_a_long_transcript_with_overlaps_reads_each_segment_once(seed):
    indexes, offset, pages = [], 0, 0
    async with server(seed["tokens"]["read_only"]) as client:
        while offset is not None:
            page = await call(client, "get_transcript", recording_id=seed["recording_id"], offset=offset, max_chars=4000)
            indexes += [segment["index"] for segment in page["segments"]]
            offset = page["next_offset"]
            pages += 1
    assert pages > 3
    assert indexes == list(range(seed["segments"]))


async def test_transcript_formats_and_time_window(seed):
    recording_id = seed["recording_id"]
    async with server(seed["tokens"]["read_only"]) as client:
        window = await call(client, "get_transcript", recording_id=recording_id, start_seconds=100, end_seconds=110)
        assert 2 <= window["total_segments"] <= 4
        for format in ("text", "srt", "vtt"):
            page = await call(client, "get_transcript", recording_id=recording_id, format=format, max_chars=1000)
            assert page["content"] and page["next_offset"] == 1000


async def test_search_finds_the_spoken_words_with_time(seed):
    async with server(seed["tokens"]["read_only"]) as client:
        found = await call(client, "search_recordings", q="ação coletiva", fields=["transcript"], limit=3)
    hit = found["results"][0]
    assert hit["recording_id"] == seed["recording_id"]
    assert hit["field"] == "transcript"
    assert hit["start_time"] is not None


async def test_a_tool_left_out_cannot_be_called_anyway(seed):
    async with server(seed["tokens"]["read_only"]) as client:
        await error(client, "update_recording", recording_id=seed["recording_id"], title="alterado")
    async with server(seed["tokens"]["full"]) as client:
        details = await call(client, "get_recording", recording_id=seed["recording_id"])
    assert details["title"] == "Aula de orçamento"


async def test_editing_tags_and_speakers(seed):
    recording_id = seed["recording_id"]
    async with server(seed["tokens"]["full"]) as client:
        await call(client, "update_recording", recording_id=recording_id, is_highlighted=True, participants="Dana")
        details = await call(client, "get_recording", recording_id=recording_id)
        assert details["is_highlighted"] is True
        assert details["participants"] == "Dana"
        assert details["title"] == "Aula de orçamento"

        created = await call(client, "create_tag", name="e2e-tag", color="#10B981")
        tag_id = created.get("id") or created["tag"]["id"]
        await call(client, "update_tag", tag_id=tag_id, name="e2e-tag-2")
        await call(client, "add_recording_tags", recording_id=recording_id, tag_ids=[tag_id])
        assert [t["name"] for t in (await call(client, "get_recording", recording_id=recording_id))["tags"]] == ["e2e-tag-2"]
        await call(client, "remove_recording_tag", recording_id=recording_id, tag_id=tag_id)
        assert (await call(client, "get_recording", recording_id=recording_id))["tags"] == []

        speaker = await call(client, "create_speaker", name="Dana Lee", email="dana@example.org", aliases=["D."])
        speaker_id = speaker.get("id") or speaker["speaker"]["id"]
        await call(client, "update_speaker", speaker_id=speaker_id, email="")
        assert (await call(client, "list_speakers"))["speakers"][0]["email"] is None

        await call(client, "assign_speakers", recording_id=recording_id, speaker_map={"SPEAKER_00": "Dana Lee"})
        page = await call(client, "get_transcript", recording_id=recording_id, max_chars=1000)
        assert page["segments"][0]["speaker"] == "Dana Lee"


async def test_folders_tool_explains_when_they_are_off(seed):
    async with server(seed["tokens"]["full"]) as client:
        assert "not enabled" in await error(client, "create_folder", name="x")


async def test_upload_transcribe_and_ask(seed, tmp_path):
    audio = tmp_path / "reuniao.wav"
    write_wav(audio)
    async with server(seed["tokens"]["full"]) as client:
        uploaded = await call(client, "upload_recording", file_path=str(audio), title="Reunião e2e", language="pt")
        recording_id = uploaded["id"]
        status = await wait_until_done(client, recording_id)
        assert status["status"] == "COMPLETED", status

        page = await call(client, "get_transcript", recording_id=recording_id)
        assert "orçamento foi aprovado" in page["segments"][1]["text"]

        answer = await call(client, "chat_with_recording", recording_id=recording_id, message="O que foi aprovado?")
        assert answer["response"]

        await call(client, "summarize_recording", recording_id=recording_id, custom_prompt="Só as decisões")
        assert (await wait_until_done(client, recording_id))["status"] == "COMPLETED"
        assert (await call(client, "get_summary", recording_id=recording_id))["summary"]

        await call(client, "regenerate_title", recording_id=recording_id)
        await call(client, "transcribe_recording", recording_id=recording_id, language="pt")
        assert (await wait_until_done(client, recording_id))["status"] == "COMPLETED"


async def test_an_unreadable_upload_is_explained(seed, tmp_path):
    fake = tmp_path / "falso.mp3"
    fake.write_text("isto não é áudio", encoding="utf-8")
    async with server(seed["tokens"]["full"]) as client:
        assert "could not be read as audio" in await error(client, "upload_recording", file_path=str(fake))


async def test_inquire_explains_when_it_is_off(seed):
    async with server(seed["tokens"]["full"]) as client:
        assert "turned off" in await error(client, "inquire", question="O que decidimos?")


async def test_share_and_delete_when_asked_for(seed, tmp_path):
    audio = tmp_path / "descartavel.wav"
    write_wav(audio)
    token = seed["tokens"]["full"]
    async with server(token, scopes="read,upload,share,delete") as client:
        recording_id = (await call(client, "upload_recording", file_path=str(audio)))["id"]
        await wait_until_done(client, recording_id)

        # Speakr refuses public links without HTTPS, and this stack has none.
        assert "HTTPS" in await error(client, "create_share_link", recording_id=recording_id)
        assert (await call(client, "list_share_links", recording_id=recording_id)) is not None

        await call(client, "delete_recording_audio", recording_id=recording_id)
        assert (await call(client, "get_recording", recording_id=recording_id))["audio_available"] is False
        await call(client, "delete_recording", recording_id=recording_id)
        assert "not found" in (await error(client, "get_recording", recording_id=recording_id)).lower()


async def test_a_bad_token_stops_the_server_with_a_reason():
    process = await anyio.run_process(
        [sys.executable, "-m", "speakr_mcp"],
        env=server_env("wrong"),
        check=False,
    )
    assert process.returncode != 0
    assert b"SPEAKR_API_TOKEN" in process.stderr
    assert b"wrong" not in process.stderr
