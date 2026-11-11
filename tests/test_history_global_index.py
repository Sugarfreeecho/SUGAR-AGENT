import json

from history_global_index import _build, gc, indexed_paths, search


def _render(event):
    content = (event.get("payload") or {}).get("content") or ""
    return str(event.get("seq") or 0), str(content)


def _write(path, rows, mode="w"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_build_and_search_by_trigram(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [
        {"seq": 1, "type": "assistant_final_committed", "payload": {"content": "alpha needle"}},
        {"seq": 2, "type": "assistant_final_committed", "payload": {"content": "beta"}},
    ])
    _build(root, path, _render)

    rows = search(root, ["alpha"], limit=10)

    assert rows is not None
    assert rows[0][0] == str(path)
    assert rows[0][3] == "1"
    assert str(path) in indexed_paths(root)


def test_append_keeps_earlier_rows_and_adds_new_ones(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [{"seq": 1, "type": "assistant_final_committed", "payload": {"content": "first needle"}}])
    _build(root, path, _render)
    _write(path, [{"seq": 2, "type": "assistant_final_committed", "payload": {"content": "second needle"}}], mode="a")
    _build(root, path, _render)

    assert search(root, ["first"], limit=10)[0][3] == "1"
    assert search(root, ["second"], limit=10)[0][3] == "2"


def test_compacted_snapshot_files_are_left_to_the_raw_scan(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [
        {"seq": 1, "type": "runtime_snapshot_compacted", "payload": {"ui_events": [
            {"type": "user", "content": "retained question"},
        ]}},
    ])
    _build(root, path, _render)

    assert indexed_paths(root) == set()
    assert search(root, ["retained"], limit=10) in (None, [])


def test_snapshot_rows_are_indexed_when_a_ui_renderer_is_given(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [
        {"seq": 4, "type": "runtime_snapshot_compacted", "payload": {"ui_events": [
            {"type": "user", "content": "retained question"},
            {"type": "final", "content": "retained answer"},
        ]}},
    ])
    _build(root, path, _render, lambda row: str(row.get("content") or ""))

    rows = search(root, ["retained answer"], limit=10)

    assert rows is not None
    assert rows[0][3] == "4:1"
    assert str(path) in indexed_paths(root)


def test_two_character_terms_scan_the_folded_column(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [{"seq": 1, "type": "assistant_final_committed", "payload": {"content": "ab"}}])
    _build(root, path, _render)

    rows = search(root, ["ab"], limit=10)

    assert rows is not None
    assert rows[0][3] == "1"


def test_gc_forgets_deleted_sources(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [{"seq": 1, "type": "assistant_final_committed", "payload": {"content": "gone soon"}}])
    _build(root, path, _render)
    path.unlink()

    assert gc(root) == 1
    assert indexed_paths(root) == set()


def test_tail_rewrite_forces_a_full_rebuild(tmp_path):
    root = tmp_path / "sessions"
    path = root / "s1" / "events.jsonl"
    _write(path, [{"seq": 1, "type": "assistant_final_committed", "payload": {"content": "old tail needle"}}])
    _build(root, path, _render)

    # Rewrite the whole file and grow it: only a boundary check can spot this.
    _write(path, [
        {"seq": 1, "type": "assistant_final_committed", "payload": {"content": "new head"}},
        {"seq": 2, "type": "assistant_final_committed", "payload": {"content": "new tail needle"}},
    ])
    _build(root, path, _render)

    assert search(root, ["old"], limit=5) == []
    assert search(root, ["new tail"], limit=5)[0][3] == "2"
