"""Extension projection suffix, recovery and publication contracts."""
import copy
import json
import os

from app.runtime_v2 import SessionEventLog, SessionExtensionStateStore, RuntimeProjector


def seed(tmp_path):
    (tmp_path / "s").mkdir()
    store = SessionExtensionStateStore(tmp_path)
    store.set_latest("s", "execution-tools", "job.one", {"status": "alpha"})
    return store


def test_warm_and_journal_suffix_updates_do_not_reparse_history(tmp_path, monkeypatch):
    store = seed(tmp_path)
    published = store.snapshots.read_for_update("s")
    before = copy.deepcopy(published)
    def fail(_sid):
        raise AssertionError("warm extension operation reparsed full history")
    monkeypatch.setattr(store.event_log, "read_all", fail)
    assert store.get("s", "execution-tools", "job.one")["revision"] == 1
    store.event_log.append("s", "execution_recorded", {"execution_id": "e", "text_delta": "hello"})
    result = store.set_latest("s", "execution-tools", "job.one", {"status": "bravo"})
    assert result["revision"] == 2
    assert published == before  # Incremental projection must preserve COW.
    projected = RuntimeProjector().project(SessionEventLog(tmp_path).read_all("s"))
    assert projected["extensions"]["execution-tools"]["job.one"] == result
    assert projected["executions"]["e"]["content"] == "hello"


def test_external_append_suffix_is_read_from_the_file(tmp_path, monkeypatch):
    store = seed(tmp_path)
    record = store.event_log.read_all("s")[-1].to_dict()
    record["seq"] = 2
    record["payload"].update(revision=2, value={"status": "bravo"})
    with store.event_log.event_path("s").open("ab") as stream:
        stream.write((json.dumps(record)+"\n").encode())
    monkeypatch.setattr(store.event_log, "read_all", lambda _: (_ for _ in ()).throw(AssertionError("full replay")))
    assert store.get("s", "execution-tools", "job.one")["value"] == {"status": "bravo"}


def test_replacement_with_preserved_size_mtime_seq_rebuilds(tmp_path):
    store = seed(tmp_path)
    path = store.event_log.event_path("s")
    prior = path.stat()
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(path.read_bytes().replace(b'alpha', b'bravo'))
    os.utime(replacement, ns=(prior.st_atime_ns, prior.st_mtime_ns))
    os.replace(replacement, path)
    assert path.stat().st_size == prior.st_size
    assert path.stat().st_mtime_ns == prior.st_mtime_ns
    assert path.stat().st_ino != prior.st_ino
    assert store.get("s", "execution-tools", "job.one")["value"] == {"status": "bravo"}


def test_truncation_recovers_prior_revision(tmp_path):
    store = seed(tmp_path)
    path = store.event_log.event_path("s")
    first = path.read_bytes()
    store.set_latest("s", "execution-tools", "job.one", {"status": "bravo"})
    path.write_bytes(first)
    assert store.get("s", "execution-tools", "job.one")["revision"] == 1
    assert store.set_latest("s", "execution-tools", "job.one", {"status": "charlie"})["revision"] == 2


def test_projector_version_mismatch_uses_facts(tmp_path):
    store = seed(tmp_path)
    snapshot = copy.deepcopy(store.snapshots.read_for_update("s"))
    snapshot["_projection"]["projector_version"] = -1
    snapshot["extensions"]["execution-tools"]["job.one"]["value"] = {"status": "stale"}
    store.snapshots.write("s", snapshot)
    assert store.get("s", "execution-tools", "job.one")["value"] == {"status": "alpha"}


def test_namespace_copy_and_noop_mutation_do_not_modify_published_state(tmp_path, monkeypatch):
    store = seed(tmp_path)
    before = store.event_log.next_seq("s")
    result = store.get("s", "execution-tools", "job.one")
    result["value"]["status"] = "caller"
    event, response = store.mutate("s", "execution-tools", "job.one", lambda value: ("", value, value))
    response["status"] = "caller"
    assert event is None
    assert store.event_log.next_seq("s") == before
    assert store.get("s", "execution-tools", "job.one")["value"] == {"status": "alpha"}


def test_legacy_stamp_without_identity_rebuilds_safely(tmp_path):
    store = seed(tmp_path)
    snapshot = copy.deepcopy(store.snapshots.read_for_update("s"))
    snapshot["_event_log"].pop("identity")
    store.snapshots.write("s", snapshot)
    result = store.set_latest("s", "execution-tools", "job.one", {"status": "bravo"})
    assert result["revision"] == 2
    assert store.snapshots.read_for_update("s")["_event_log"]["identity"]
