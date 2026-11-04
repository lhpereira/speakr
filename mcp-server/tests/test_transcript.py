from speakr_mcp.transcript import page_segments, page_text


def segments(count, text="palavra " * 10):
    return [
        {"index": i, "speaker": "Dana", "speaker_label": "SPEAKER_00", "speaker_id": 1, "text": text,
         "sentence": text, "start_time": float(i), "end_time": i + 1.0}
        for i in range(count)
    ]


def read_all(items, max_chars):
    seen, offset = [], 0
    while offset is not None:
        page = page_segments(items, offset, max_chars)
        seen += [segment["index"] for segment in page["segments"]]
        offset = page["next_offset"]
    return seen


def test_every_segment_is_read_exactly_once():
    assert read_all(segments(500), 2000) == list(range(500))


def test_overlapping_segments_are_not_repeated():
    # Continuing the API's window from next_start would return these again.
    items = segments(20)
    for item in items:
        item["end_time"] = item["start_time"] + 5
    assert read_all(items, 1000) == list(range(20))


def test_segments_without_times_do_not_end_the_reading_early():
    items = segments(20)
    for item in items[5:]:
        item["start_time"] = item["end_time"] = None
    assert read_all(items, 1000) == list(range(20))


def test_a_segment_larger_than_the_page_still_advances():
    assert read_all(segments(3, "x" * 5000), 1000) == [0, 1, 2]


def test_a_page_keeps_to_its_size():
    page = page_segments(segments(100), 0, 2000)
    assert 1 < len(page["segments"]) < 100
    assert sum(len(s["text"]) for s in page["segments"]) <= 2000


def test_a_page_drops_the_duplicate_fields():
    assert set(page_segments(segments(1), 0, 1000)["segments"][0]) == {"index", "speaker", "start", "end", "text"}


def test_the_last_page_has_no_next_offset():
    assert page_segments(segments(2), 0, 100000)["next_offset"] is None


def test_an_offset_past_the_end_is_empty():
    page = page_segments(segments(2), 9, 1000)
    assert page["segments"] == []
    assert page["next_offset"] is None


def test_text_pages_join_up_to_the_whole_text():
    text = "ação " * 1000
    parts, offset = [], 0
    while offset is not None:
        page = page_text(text, offset, 1500)
        parts.append(page["content"])
        offset = page["next_offset"]
    assert "".join(parts) == text
    assert len(parts) == 4
