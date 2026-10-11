"""Copy real UI history and timestamped execution updates into the replay workdir.

Reads the source session only. No projection rebuild, model call or tool execution.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from app.workspace_paths import configured_workspace_root
SID = "77dc386c-fe09-4863-a50d-1a3233060de2"
SOURCE = configured_workspace_root(ROOT) / "sessions" / SID
MANIFEST = json.loads((ROOT / ".git/archived-stream-replay-work.json").read_text(encoding="utf-8"))


def hydrate(row):
    row = dict(row)
    for key, value in list(row.items()):
        if not key.endswith("_ref") or not isinstance(value, dict) or not value.get("blob_ref"):
            continue
        target = key[:-4]
        if target in row:
            continue
        path = (SOURCE / value["blob_ref"]).resolve()
        if not path.is_relative_to(SOURCE.resolve()):
            raise ValueError("Blob outside source session")
        data = path.read_bytes()
        if value.get("sha256") and hashlib.sha256(data).hexdigest() != value["sha256"]:
            raise ValueError("Blob checksum mismatch")
        row[target] = data.decode("utf-8")
    return row


def merge(prior, update, seq):
    result = dict(prior, **update, last_runtime_seq=seq)
    for delta, target in (("text_delta", "content"), ("name_delta", "tool"),
                          ("arguments_delta", "arguments_raw"), ("output_delta", "output")):
        if delta in update:
            result[target] = str(prior.get(target) or "") + str(update[delta] or "")
        result.pop(delta, None)
    return result


def main():
    journal = SOURCE / "events.jsonl"
    before_hash = hashlib.sha256(journal.read_bytes()).hexdigest()
    events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line]
    index = json.loads((SOURCE / "snapshots/ui_projection_index.json").read_text(encoding="utf-8"))
    rows = []
    for name in index["row_files"]:
        path = SOURCE / "snapshots" / name
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    metadata = json.loads((SOURCE / "metadata.json").read_text(encoding="utf-8"))
    segments = []
    for iteration in (37, 41):
        updates = [event for event in events if event["type"] == "execution_recorded"
                   and event["payload"].get("kind") == "reasoning"
                   and event["payload"].get("react_iter") == iteration
                   and event["payload"].get("run_id") == "bfbfd431-b574-4223-a18b-df3a32f69861"]
        first = next(event for event in updates if event["payload"].get("text_delta"))
        first_seq = first["seq"]
        start = datetime.fromisoformat(first["timestamp"].replace("Z", "+00:00"))
        updates = [event for event in updates if event["seq"] >= first_seq]
        history = [hydrate(row) for row in rows if int(row.get("runtime_seq") or 0) < first_seq]
        records = {}
        context = None
        for event in events:
            if event["seq"] >= first_seq:
                break
            if event["type"] == "execution_recorded":
                update = hydrate(event["payload"])
                key = update["execution_id"]
                records[key] = merge(records.get(key, {}), update, event["seq"])
            elif event["type"] == "context_tokens":
                context = event["payload"]
        packets = []
        for event in updates:
            offset = (datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")) - start).total_seconds() * 1000
            packets.append({"at_ms": round(offset, 3), "timestamp": event["timestamp"],
                            "seq": event["seq"], "update": hydrate(event["payload"])})
        exact_text = "".join(str(event["payload"].get("text_delta") or "") for event in updates)
        full = next((event["payload"].get("content") for event in reversed(updates)
                     if "content" in event["payload"]), None)
        if full is not None and full != exact_text:
            raise ValueError("Delta text does not match durable completed text")
        segments.append({"id": str(iteration), "iteration": iteration, "first_seq": first_seq,
                         "run_id": first["payload"]["run_id"],
                         "process_group_id": first["payload"]["process_group_id"],
                         "execution_id": first["payload"]["execution_id"],
                         "started_at": first["timestamp"], "ended_at": updates[-1]["timestamp"],
                         "duration_ms": packets[-1]["at_ms"],
                         "context_tokens": int((context or {}).get("input_tokens") or 0),
                         "history": history, "history_records": list(records.values()),
                         "history_types": dict(Counter(row["type"] for row in history)),
                         "history_characters": sum(len(str(row.get("content") or row.get("result") or "")) for row in history),
                         "packets": packets, "delta_count": sum("text_delta" in event["payload"] for event in updates),
                         "text": exact_text, "text_sha256": hashlib.sha256(exact_text.encode()).hexdigest()})
    result = {"session_id": SID, "name": metadata["name"], "journal_sha256": before_hash,
              "timing_source": "durable_server_journal", "segments": segments}
    dest = Path(MANIFEST["work"]) / "real-session-replay.json"
    dest.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    assert hashlib.sha256(journal.read_bytes()).hexdigest() == before_hash
    print(json.dumps({"saved": str(dest), "session": SID, "name": metadata["name"],
                      "segments": [{key: value for key, value in segment.items()
                                    if key not in {"history", "history_records", "packets", "text"}}
                                   for segment in segments]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
