import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'app'))


def test_dropped_records_survive_repeated_full_queue_and_concurrent_emitters(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import queue
    import ui_loading_diagnostics as d
    records = queue.Queue(maxsize=1)
    records.put({})
    monkeypatch.setattr(d, '_queue', records)
    monkeypatch.setattr(d, '_writer_started', True)
    monkeypatch.setattr(d, '_dropped', 0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: d.emit_event({'event': 'test'}), range(40)))
    records.get_nowait()
    d.emit_event({'event': 'last'})
    assert records.get_nowait()['dropped_records'] == 40
    assert d._dropped == 0


def test_frontend_loading_diagnostics():
    result = subprocess.run(['node','--test',str(ROOT/'tests/js/loading_diagnostics_runtime.cjs')],
                            cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=15)
    assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.parametrize('mode',['success','exception','cancelled','disconnect'])
def test_request_lifecycle_records_early_cancellation_and_echoes_ids(monkeypatch,mode):
    import ui_loading_diagnostics as d
    rows,sent=[],[]
    monkeypatch.setattr(d,'emit_event',rows.append)

    async def app(scope,receive,send):
        scope['state']['ui_loading_trace']['phase']='execution_recovery'
        if mode=='exception':raise ValueError('SECRET')
        if mode=='cancelled':raise asyncio.CancelledError()
        if mode=='disconnect':await receive()
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'payload'})

    async def receive():return {'type':'http.disconnect'}
    async def send(message):sent.append(message)
    scope={'type':'http','path':'/sessions/session/history_snapshot',
           'headers':[(b'x-request-id',b'request-1'),(b'x-ui-load-id',b'load-1')]}
    async def run():
        work=d.LoadingDiagnosticsMiddleware(app)(scope,receive,send)
        if mode=='exception':
            with pytest.raises(ValueError):await work
        elif mode=='cancelled':
            with pytest.raises(asyncio.CancelledError):await work
        else:await work
    asyncio.run(run())
    assert [row['event'] for row in rows]==['server_start','server_end']
    assert rows[-1]['request_id']=='request-1' and rows[-1]['load_id']=='load-1'
    assert rows[-1]['phase']=='execution_recovery'
    assert rows[-1]['status']=={'success':'success','exception':'exception','cancelled':'cancelled','disconnect':'disconnected'}[mode]
    assert rows[-1]['elapsed_ms']>=0
    assert 'SECRET' not in json.dumps(rows)
    if sent:assert (b'x-request-id',b'request-1') in sent[0]['headers']


def test_collector_accepts_only_bounded_diagnostic_metadata(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import ui_loading_diagnostics as d
    app=FastAPI();d.register_loading_diagnostics(app)
    rows=[];monkeypatch.setattr(d,'emit_event',rows.append)
    with TestClient(app) as client:
        result=client.post('/api/ui-loading-diagnostics',json={'records':[{
            'event':'request_end','session_id':'session','request_id':'rid','load_id':'lid',
            'reason':'timeout','phase':'body','elapsed_ms':30004,'error_name':'AbortError',
            'message':'SECRET','body':'SECRET','url':'SECRET','headers':{'Authorization':'SECRET'},
        }]})
        assert result.status_code==200
        assert rows[-1]['reason']=='timeout' and rows[-1]['phase']=='body'
        assert 'SECRET' not in json.dumps(rows)
        assert client.post('/api/ui-loading-diagnostics',content=b'x'*32769).status_code==413
        assert client.post('/api/ui-loading-diagnostics',json={'records':[{}]*33}).status_code==400
        assert client.post('/api/ui-loading-diagnostics',json=[]).status_code==400
        assert client.post('/api/ui-loading-diagnostics',json={'records':[{'event':[]},
            {'event':'request_end','phase':{},'status':[],'reason':['invalid']}]}).status_code==200


def test_loop_monitor_records_stalls_without_logging_healthy_ticks(monkeypatch):
    import ui_loading_diagnostics as d
    rows = []
    ticks = iter([0.0, 2.01, 2.01, 5.01, 5.01])
    monkeypatch.setattr(d, 'emit_event', rows.append)
    monkeypatch.setattr(d.time, 'perf_counter', lambda: next(ticks))
    waits = []

    async def sleep(interval):
        waits.append(interval)
        if len(waits) == 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(d.asyncio, 'sleep', sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(d.monitor_event_loop())
    assert len(rows) == 1
    assert rows[0]['event'] == 'server_loop_lag'
    assert rows[0]['lag_ms'] == 1000
    assert rows[0]['interval_ms'] == 2000
    assert rows[0]['expected_at'].endswith('+00:00')


def test_monitor_survives_production_lifespan_override_and_stops_cleanly(monkeypatch):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import ui_loading_diagnostics as d
    order = []

    async def monitor():
        order.append('monitor_start')
        try:
            await asyncio.Future()
        finally:
            order.append('monitor_stop')

    @asynccontextmanager
    async def production_lifespan(_app):
        order.append('startup')
        yield
        order.append('shutdown')

    app = FastAPI()
    d.register_loading_diagnostics(app)
    app.router.lifespan_context = production_lifespan
    monkeypatch.setattr(d, 'monitor_event_loop', monitor)
    with TestClient(app) as client:
        assert client.post('/api/ui-loading-diagnostics', json={'records':[]}).status_code == 200
        assert order == ['startup', 'monitor_start']
    assert order == ['startup', 'monitor_start', 'shutdown', 'monitor_stop']
