import asyncio
import importlib.util
import os
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_host(plugin):
    spec = importlib.util.spec_from_file_location('efficiency_' + plugin, ROOT / 'plugins' / plugin / 'host.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('pattern', ['**/*.py', '**/.config/plugins*.json', '**/a/*.txt', '**/a/', '**/[ab]/*.txt', '**/missing/file'])
def test_recursive_glob_matches_pathlib_and_prunes_excluded_tree(tmp_path, monkeypatch, pattern):
    import tool_glob

    for name in ['root.py', 'a/one.txt', 'b/two.txt', 'a/sub/deep.py', '.config/plugins-a.json',
                 'b/.config/plugins-b.json', 'TempOutput/a/hidden.txt', 'b/TempOutput/x.py']:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x')
    expected = [p for p in tmp_path.glob(pattern) if 'tempoutput' not in {s.lower() for s in p.relative_to(tmp_path).parts}]
    scanned = []
    original = tool_glob.os.scandir

    def scan(path):
        scanned.append(Path(path))
        return original(path)

    monkeypatch.setattr(tool_glob.os, 'scandir', scan)
    assert list(tool_glob.recursive_glob(tmp_path, pattern)) == expected
    assert all('tempoutput' not in {s.lower() for s in p.relative_to(tmp_path).parts} for p in scanned)


def test_recursive_glob_preserves_directory_link_rules(tmp_path):
    from tool_glob import recursive_glob

    target = tmp_path / 'real'
    target.mkdir()
    (target / 'x.txt').write_text('x')
    try:
        (tmp_path / 'link').symlink_to(target, target_is_directory=True)
        (tmp_path / 'broken').symlink_to(tmp_path / 'absent')
    except OSError:
        pytest.skip('directory links are not available')
    for pattern in ['**/*.txt', '**/link/*.txt', '**/broken', '**/bro*']:
        assert list(recursive_glob(tmp_path, pattern)) == list(tmp_path.glob(pattern))


def test_recursive_glob_reports_unexpected_disk_errors(tmp_path, monkeypatch):
    import errno
    import tool_glob

    def failed(_path):
        raise OSError(errno.EIO, 'disk failure')

    monkeypatch.setattr(tool_glob.os, 'scandir', failed)
    with pytest.raises(OSError, match='disk failure'):
        list(tool_glob.recursive_glob(tmp_path, '**/*.py'))


async def entered(event):
    async def poll():
        while not event.is_set():
            await asyncio.sleep(.001)
    await asyncio.wait_for(poll(), 5)


class Todo:
    def __init__(self):
        self._by_session = {'s': [{'text': 'old'}]}

    def update_for_session(self, sid, items):
        self._by_session[sid] = list(items)
        return 'updated'


@pytest.mark.parametrize('finish', ['success', 'fail', 'cancel'])
def test_todo_disk_worker_keeps_loop_live_and_publishes_only_committed_items(monkeypatch, finish):
    host = load_host('session-todo')
    import session_todo_extension

    start, release = threading.Event(), threading.Event()
    owner = threading.get_ident()
    manager = Todo()
    published = []
    state = {'_todo_rounds_since_update': 7}

    def write(*args, **kwargs):
        assert threading.get_ident() != owner
        start.set()
        assert release.wait(5)
        if finish == 'fail':
            raise OSError('failed')
        return {'revision': 2}

    async def publish(event):
        assert threading.get_ident() == owner
        published.append(event)

    services = {'session_plan_store': manager, 'session_manager': object()}
    context = SimpleNamespace(session_id='s', run_id='r', state=state, service=services.__getitem__, publish=publish)
    monkeypatch.setattr(session_todo_extension, 'write_todo_extension', write)

    async def run():
        task = asyncio.create_task(host._invoke_update_todo(context, {'items': [{'text': 'new'}]}))
        try:
            await entered(start)
            assert manager._by_session['s'] == [{'text': 'old'}]
            assert state['_todo_rounds_since_update'] == 7 and not published
            if finish == 'cancel':
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                assert not task.done()
            release.set()
            if finish == 'success':
                assert (await task).content == 'updated'
            else:
                with pytest.raises(asyncio.CancelledError if finish == 'cancel' else OSError):
                    await task
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
    assert manager._by_session['s'] == [{'text': 'old' if finish == 'fail' else 'new'}]
    assert state['_todo_rounds_since_update'] == (7 if finish == 'fail' else 0)
    assert bool(published) == (finish == 'success')


@pytest.mark.parametrize('tool_name', ['create_goal', 'get_goal', 'update_goal'])
def test_goal_operations_run_off_the_owner_loop(monkeypatch, tool_name):
    import agent_goal

    host = load_host('agent-goal')
    owner = threading.get_ident()
    start, release = threading.Event(), threading.Event()

    def operation(*args, **kwargs):
        assert threading.get_ident() != owner
        start.set()
        assert release.wait(5)
        return {'status': 'active'}

    manager = SimpleNamespace(create=operation, get=operation, update_status=operation)
    monkeypatch.setattr(agent_goal, 'manager_for', lambda _: manager)
    published = []

    async def publish(event):
        assert threading.get_ident() == owner
        published.append(event)

    services = {'session_manager': object(), 'tool_name': tool_name}
    context = SimpleNamespace(session_id='s', run_id='r', state={}, service=services.__getitem__, publish=publish)

    async def run():
        task = asyncio.create_task(host._invoke_goal(context, {'objective': 'test', 'status': 'blocked'}))
        try:
            await entered(start)
            assert not published
            release.set()
            await task
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
    assert len(published) == 1


def test_set_latest_uses_one_transaction_and_preserves_concurrent_revisions(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from runtime_v2 import SessionExtensionStateStore

    (tmp_path / 's').mkdir()
    store = SessionExtensionStateStore(tmp_path)
    original = store.event_log.session_transaction
    calls = []

    @contextmanager
    def transaction(sid):
        calls.append(sid)
        with original(sid):
            yield

    monkeypatch.setattr(store.event_log, 'session_transaction', transaction)
    assert store.set_latest('s', 'p', 'n', {'value': 0})['revision'] == 1
    assert calls == ['s']
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda i: store.set_latest('s', 'p', 'n', {'value': i}), range(12)))
    assert sorted(r['revision'] for r in rows) == list(range(2, 14))
    facts = store.event_log.read_all('s')
    assert [e.payload['revision'] for e in facts] == list(range(1, 14))


@pytest.mark.parametrize('contents', [b'', b'a\r\nb\rc\n', b'x' * 3001 + b'\nlast', '中文🙂\n'.encode() * 350, b'bad\xff\nvalid\n'])
def test_sparse_text_range_matches_virtual_lines_and_reuses_offsets(tmp_path, contents):
    import agent_tools
    from tool_text_range import read_range

    path = tmp_path / 'input.txt'
    path.write_bytes(contents)
    expected = agent_tools._virtualize_text_lines(path.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True))
    for start, end in [(1, 2), (2, 4), (127, 135), (300, 315), (1000, 1100)]:
        total, rows, stable = read_range(path, start, end)
        assert stable
        assert total == len(expected)
        assert rows == expected[start - 1:end]


def test_sparse_range_invalidates_rewrites_even_when_mtime_is_restored(tmp_path):
    from tool_text_range import read_range

    path = tmp_path / 'input.txt'
    path.write_text('a\nb\nc\n')
    old = path.stat()
    assert read_range(path, 1, 2)[:2] == (3, ['a\n', 'b\n'])
    path.write_text('abcde\n')
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    assert read_range(path, 1, 2)[:2] == (1, ['abcde\n'])
    replacement = tmp_path / 'replacement'
    replacement.write_text('d\ne\nf\n')
    os.utime(replacement, ns=(old.st_atime_ns, old.st_mtime_ns))
    os.replace(replacement, path)
    assert read_range(path, 2, 3)[:2] == (3, ['e\n', 'f\n'])


def test_sparse_range_seeks_near_the_requested_region(tmp_path, monkeypatch):
    import tool_text_range

    path = tmp_path / 'large.txt'
    path.write_text('line\n' * 20000)
    tool_text_range.read_range(path, 1, 10)
    original = Path.open
    lines = []

    class Stream:
        def __init__(self, source):
            self.source = source

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.source.close()

        def __getattr__(self, name):
            return getattr(self.source, name)

        def readline(self):
            lines.append(1)
            return self.source.readline()

    monkeypatch.setattr(Path, 'open', lambda *a, **kw: Stream(original(*a, **kw)))
    assert tool_text_range.read_range(path, 19000, 19010)[:2] == (20000, ['line\n'] * 11)
    assert len(lines) < 150


def test_history_index_matches_streaming_and_detects_append_rewrite_replace_and_partial_tail(tmp_path, monkeypatch):
    import json
    import history_context as history
    import history_search_index as index

    sid = '12345678-1234-1234-1234-123456789012'
    directory = tmp_path / sid
    directory.mkdir()
    path = directory / 'events.jsonl'

    def row(seq, text):
        return json.dumps({'seq': seq, 'type': 'model_user', 'payload': {'content': text}}, ensure_ascii=False) + '\n'

    def render(value):
        return str(value['seq']), history._clean_event_text(value)

    monkeypatch.setattr(index, 'schedule', lambda *args: None)
    path.write_text(row(1, 'needle same') + row(2, 'needle same') + row(3, 'Straße 用户 needle other'), encoding='utf-8')

    def compare():
        for terms in [['needle'], ['strasse'], ['用户'], ['absent']]:
            expected = []
            seen = set()
            for value, _ in history._matching_jsonl(path, terms):
                ref, content = render(value)
                key = ' '.join(content.split()).casefold()
                if all(t in content.casefold() for t in terms) and key not in seen:
                    expected.append((ref, content))
                    seen.add(key)
                if len(expected) >= 2:
                    break
            assert index.search(path, terms, render, limit=2, seen=set()) == expected

    index._build(path, render)
    compare()
    with path.open('a', encoding='utf-8') as stream:
        stream.write(row(4, 'needle appended'))
    compare()
    # Rewrite an indexed prefix and append in the same inode: growth cannot
    # authorize reuse without verifying the old prefix hash.
    path.write_text(row(1, 'needle new!') + row(5, 'needle replacement') * 10, encoding='utf-8')
    compare()
    stamp = path.stat()
    text = path.read_text(encoding='utf-8').replace('new!', 'next')
    path.write_text(text, encoding='utf-8')
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    compare()
    replacement = directory / 'replacement'
    replacement.write_text(row(7, 'needle replaced'), encoding='utf-8')
    os.replace(replacement, path)
    compare()
    with path.open('ab') as stream:
        stream.write(b'{"partial":')
    assert index.search(path, ['needle'], render, limit=2, seen=set()) is None


def test_job_output_empty_poll_does_not_write_but_consumption_does(monkeypatch):
    from execution_services.jobs import ExecutionService, Job

    service = ExecutionService()
    job = Job('one', 's', 'process', 'label')
    service.jobs[job.id] = job
    service._recovered.add('s')
    writes = []

    async def persist(value):
        writes.append(value.output.cursor)

    monkeypatch.setattr(service, '_persist_job', persist)

    async def run():
        assert (await service.output('s', 'one'))['text'] == ''
        assert not writes
        job.output.append(b'hello')
        assert (await service.output('s', 'one', offset=0))['text'] == 'hello'
        assert not writes
        assert (await service.output('s', 'one'))['text'] == 'hello'
        assert writes == [5]
        await service.output('s', 'one')
        assert writes == [5]
        job.result_pending, job.result, job.notice_pending = True, {'ok': True}, True
        job.done.set()
        assert (await service.output('s', 'one'))['result'] == {'ok': True}
        assert writes == [5, 5]
        await service.output('s', 'one')
        assert writes == [5, 5]

    asyncio.run(run())


def test_todo_concurrent_updates_commit_in_order(monkeypatch):
    import session_todo_extension

    host = load_host('session-todo')
    manager = Todo()
    first_started, release = threading.Event(), threading.Event()
    written = []

    def write(_manager, sid, items, **kwargs):
        value = items[0]['text']
        written.append(value)
        if value == 'first':
            first_started.set()
            assert release.wait(5)
        return {'revision': len(written)}

    async def publish(event):
        pass

    monkeypatch.setattr(session_todo_extension, 'write_todo_extension', write)
    services = {'session_plan_store': manager, 'session_manager': object()}
    context = SimpleNamespace(session_id='s', run_id='r', state={}, service=services.__getitem__, publish=publish)

    async def run():
        first = asyncio.create_task(host._invoke_update_todo(context, {'items': [{'text': 'first'}]}))
        await entered(first_started)
        second = asyncio.create_task(host._invoke_update_todo(context, {'items': [{'text': 'second'}]}))
        try:
            await asyncio.sleep(.02)
            assert written == ['first']
            release.set()
            await asyncio.gather(first, second)
        finally:
            release.set()
            await asyncio.gather(first, second, return_exceptions=True)

    asyncio.run(run())
    assert written == ['first', 'second']
    assert manager._by_session['s'] == [{'text': 'second'}]


def test_history_global_precomputation_starts_after_foreground_scan_and_corrupt_cache_falls_back(tmp_path, monkeypatch):
    import json
    import uuid
    import history_context as history
    import history_search_index as index

    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    for sid in ids:
        directory = tmp_path / sid
        directory.mkdir()
        (directory / 'events.jsonl').write_text(json.dumps({
            'seq': 1, 'type': 'model_user', 'payload': {'content': 'unique-' + sid},
        }) + '\n', encoding='utf-8')
    manager = SimpleNamespace(sessions_dir=tmp_path, _normalize_session_id=lambda sid: sid,
                              _resolve_session_path=lambda sid: tmp_path / sid)
    scanned, scheduled = [], []
    original = history._matching_jsonl

    def scan(path, terms):
        assert not scheduled
        scanned.append(path)
        yield from original(path, terms)

    monkeypatch.setattr(history, '_matching_jsonl', scan)
    monkeypatch.setattr(index, 'schedule', lambda path, render: scheduled.append(path))
    assert history.history_context(manager, ids[0], scope='global', query='absent')['results'] == []
    assert len(scanned) == 2 and set(scanned) == set(scheduled)
    # A damaged derived database cannot prevent semantic access to the facts.
    scheduled.clear()
    path = tmp_path / ids[0] / 'events.jsonl'
    index._db_path(path).parent.mkdir()
    index._db_path(path).write_bytes(b'broken sqlite cache')
    assert history.history_context(manager, ids[0], query='unique')['results'][0]['content'] == '用户：unique-' + ids[0]
    index._build(path, lambda row: (str(row['seq']), history._clean_event_text(row)))
    assert not index._db_path(path).exists()
