"""Archive load must exercise real sessions accepted by all production readers."""
import importlib.util
import json
import logging
from pathlib import Path
import uuid

import pytest


@pytest.fixture
def benchmark_module():
    path = Path(__file__).resolve().parents[1]/'scripts/benchmark_agent_interround.py'
    spec = importlib.util.spec_from_file_location('archive_benchmark_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_fixture_is_recognized_by_session_and_observability_readers(tmp_path, benchmark_module, caplog):
    from agent_harness import SessionManager
    from runtime_observability import _observability_paths

    root = tmp_path/'sessions'
    manager = SessionManager(root, tmp_path/'index.json')
    with caplog.at_level(logging.WARNING):
        session_ids = benchmark_module.seed_archived_sessions(manager, tmp_path, 3, 2)
        recognized = manager.list_sessions(include_archived=True)
    assert len(session_ids) == len(set(session_ids)) == 3
    assert all(str(uuid.UUID(sid)) == sid for sid in session_ids)
    archived = [row for row in recognized if row.get('archived')]
    assert {row['id'] for row in archived} == set(session_ids)
    assert {path.parent.name for path in _observability_paths(root)} == set(session_ids)
    for sid in session_ids:
        data = json.loads((root/sid/'runtime_observability.json').read_text(encoding='utf8'))
        assert data['session_id'] == sid and data['runs'][0]['status'] == 'finished'
        assert len(list((root/sid/'files/node_modules').iterdir())) == 2
    assert 'Skipping invalid session directory name' not in caplog.text


def test_archive_fixture_rejects_manager_outside_its_scratch_root(tmp_path, benchmark_module):
    class OtherManager:
        sessions_dir = tmp_path/'production-sessions'

        def get_or_create_session(self, **kwargs):
            pytest.fail('Must reject foreign root before writing anything')

    with pytest.raises(AssertionError):
        benchmark_module.seed_archived_sessions(OtherManager(), tmp_path/'scratch', 1, 1)
