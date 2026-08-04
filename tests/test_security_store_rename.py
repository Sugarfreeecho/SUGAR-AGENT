from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from security.store import SecurityStore, security_state_dir  # noqa: E402


def _roots(base: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return base / "MyAgent" / "security", base / "SugarAgent" / "security"
    return base / "myagent" / "security", base / "sugaragent" / "security"


def _point_state_home(monkeypatch: pytest.MonkeyPatch, base: Path) -> None:
    monkeypatch.delenv("MYAGENT_SECURITY_HOME", raising=False)
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(base))
    else:
        monkeypatch.setenv("XDG_STATE_HOME", str(base))


def test_security_state_dir_uses_sugaragent_path(monkeypatch, tmp_path):
    _point_state_home(monkeypatch, tmp_path)
    _, current = _roots(tmp_path)
    assert security_state_dir() == current.resolve()


def test_legacy_security_database_is_migrated_to_new_path(monkeypatch, tmp_path):
    _point_state_home(monkeypatch, tmp_path)
    legacy, current = _roots(tmp_path)
    legacy.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(legacy / "security.sqlite3"))
    try:
        db.execute("CREATE TABLE demo(key TEXT PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO demo(key, value) VALUES('mcp_demo', 'trusted')")
        db.commit()
    finally:
        db.close()

    store = SecurityStore()
    assert store.path.parent == current.resolve()

    migrated = sqlite3.connect(str(store.path))
    try:
        row = migrated.execute("SELECT value FROM demo WHERE key='mcp_demo'").fetchone()
    finally:
        migrated.close()
    assert row is not None and row[0] == "trusted"

    # The legacy database is kept intact as a backup.
    assert (legacy / "security.sqlite3").is_file()


def test_existing_new_store_is_not_overwritten(monkeypatch, tmp_path):
    _point_state_home(monkeypatch, tmp_path)
    legacy, current = _roots(tmp_path)
    legacy.mkdir(parents=True, exist_ok=True)
    current.mkdir(parents=True, exist_ok=True)

    old_db = sqlite3.connect(str(legacy / "security.sqlite3"))
    try:
        old_db.execute("CREATE TABLE demo(key TEXT PRIMARY KEY, value TEXT)")
        old_db.execute("INSERT INTO demo(key, value) VALUES('old', 'legacy')")
        old_db.commit()
    finally:
        old_db.close()

    new_db = sqlite3.connect(str(current / "security.sqlite3"))
    try:
        new_db.execute("CREATE TABLE demo(key TEXT PRIMARY KEY, value TEXT)")
        new_db.execute("INSERT INTO demo(key, value) VALUES('new', 'current')")
        new_db.commit()
    finally:
        new_db.close()

    store = SecurityStore()
    check = sqlite3.connect(str(store.path))
    try:
        rows = dict(check.execute("SELECT key, value FROM demo").fetchall())
    finally:
        check.close()
    assert rows == {"new": "current"}
