"""Paging of transcripts, so that a long recording fits a tool result.

MCP clients cap the size of a tool result, and a two-hour recording is over any
such cap. The API's own window (`max_segments`, `next_start`) is not used for
paging: it selects by time overlap, so continuing from `next_start` returns
overlapping segments again, and `next_start` is null when the next segment has
no time. Paging by position has neither problem.
"""

from typing import Any

# Roughly what a segment's keys and punctuation add to its text in JSON.
SEGMENT_OVERHEAD = 70


def page_segments(segments: list[dict[str, Any]], offset: int, max_chars: int) -> dict[str, Any]:
    """Segments from offset, up to max_chars. Always at least one, so paging ends."""
    page: list[dict[str, Any]] = []
    used = 0
    for segment in segments[offset:]:
        text = segment.get("text") or ""
        cost = len(text) + SEGMENT_OVERHEAD
        if page and used + cost > max_chars:
            break
        used += cost
        page.append({
            "index": segment.get("index"),
            "speaker": segment.get("speaker"),
            "start": segment.get("start_time"),
            "end": segment.get("end_time"),
            "text": text,
        })
    following = offset + len(page)
    return {
        "segments": page,
        "total_segments": len(segments),
        "next_offset": following if following < len(segments) else None,
    }


def page_text(text: str, offset: int, max_chars: int) -> dict[str, Any]:
    """Characters from offset, up to max_chars."""
    following = offset + max_chars
    return {
        "content": text[offset:following],
        "total_chars": len(text),
        "next_offset": following if following < len(text) else None,
    }
