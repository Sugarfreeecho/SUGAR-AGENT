import json

from history_search_index import _build, gc, search


def _render(row):
    content = str((row.get("payload") or {}).get("content") or "")
    return str(row.get("seq") or 0), content


def _write(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )


def test_empty_projection_is_not_trusted_as_a_negative_answer(tmp_path):
    path = tmp_path / "events.jsonl"
    _write(path, [{"seq": 1, "type": "run_heartbeat", "payload": {"counter": 3}}])
    _build(path, lambda row: ("1", ""))

    assert search(path, ["heartbeat"], _render, limit=5, seen=set()) is None


def test_compacted_snapshot_forces_raw_scan(tmp_path):
    path = tmp_path / "events.jsonl"
    _write(
        path,
        [
            {"seq": 1, "type": "assistant_final_committed", "payload": {"content": "plain answer"}},
            {
                "seq": 2,
                "type": "runtime_snapshot_compacted",
                "payload": {"ui_events": [{"type": "user", "content": "retained question"}]},
            },
        ],
    )
    _build(path, _render)

    assert search(path, ["plain answer"], _render, limit=5, seen=set()) is None


def test_warm_index_answers_matching_rows(tmp_path):
    path = tmp_path / "events.jsonl"
    _write(
        path,
        [
            {"seq": 1, "type": "assistant_final_committed", "payload": {"content": "first answer"}},
            {"seq": 2, "type": "assistant_final_committed", "payload": {"content": "second answer"}},
        ],
    )
    _build(path, _render)

    found = search(path, ["second"], _render, limit=5, seen=set())

    assert found == [("2", "second answer")]


def test_gc_removes_only_projections_without_a_source(tmp_path):
    orphan_dir = tmp_path / "orphan" / ".history-search"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "events.jsonl.sqlite3").write_bytes(b"stale")
    live = tmp_path / "live" / "events.jsonl"
    _write(live, [{"seq": 1, "type": "assistant_final_committed", "payload": {"content": "x"}}])
    _build(live, _render)

    assert gc(tmp_path) == 1
    assert not (orphan_dir / "events.jsonl.sqlite3").exists()
    assert (live.parent / ".history-search" / "events.jsonl.sqlite3").is_file()
