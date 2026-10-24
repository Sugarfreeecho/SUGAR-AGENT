import asyncio
from types import SimpleNamespace

import pytest

from execution_services.jobs import ExecutionService


def service_for(tmp_path, monkeypatch, *, status='completed', suppressed=True, pending=False):
    owner, identifier = 'owner', 'a' * 32
    (tmp_path / owner).mkdir(exist_ok=True)
    manager = SimpleNamespace(repository=SimpleNamespace(sessions_dir=tmp_path),
                              _resolve_session_path=lambda sid: tmp_path / sid)
    service = ExecutionService(manager)
    value = dict(id=identifier, owner=owner, boot_id='previous-boot', kind='process',
                 label='old job', status=status, notice_suppressed=suppressed, notice_pending=pending,
                 result={'summary': 'preserved'}, result_pending=True)
    store = SimpleNamespace(read_all_lightweight=lambda _: {'execution-tools': {'job.' + identifier: {'value': value}}})
    monkeypatch.setattr(service, '_store', lambda: store)
    writes, cleanup = [], []
    async def persist(job):
        writes.append(dict(status=job.status, suppressed=job.notice_suppressed, pending=job.notice_pending))
    monkeypatch.setattr(service, '_persist_job', persist)
    monkeypatch.setattr(service, '_cleanup_previous_process', lambda row: cleanup.append(row['id']))
    return service, owner, identifier, writes, cleanup


@pytest.mark.parametrize('status', ['completed', 'failed', 'cancelled'])
def test_unchanged_terminal_jobs_do_not_append_boot_only_facts(tmp_path, monkeypatch, status):
    for _ in range(2):
        service, owner, identifier, writes, cleanup = service_for(tmp_path, monkeypatch, status=status)
        asyncio.run(service.recover(owner))
        job = service.jobs[identifier]
        assert job.status == status and job.done.is_set()
        assert job.result == {'summary': 'preserved'} and job.result_pending is True
        assert job.notice_suppressed is True
        assert not writes and not cleanup


@pytest.mark.parametrize(('status', 'suppressed', 'pending'), [
    ('running', True, False), ('stopping', True, False),
    ('completed', False, False), ('completed', True, True),
])
def test_recovery_still_commits_interruptions_and_notice_changes(tmp_path, monkeypatch, status, suppressed, pending):
    service, owner, identifier, writes, cleanup = service_for(
        tmp_path, monkeypatch, status=status, suppressed=suppressed, pending=pending)
    async def run():
        await service.recover(owner)
        await service.recover(owner)
    asyncio.run(run())
    interrupted = status in ('running', 'stopping')
    assert writes == [{'status': 'failed' if interrupted else status, 'suppressed': True, 'pending': False}]
    assert cleanup == ([identifier] if interrupted else [])
