import asyncio
import json
import threading
from queue import Queue

import httpx
from openai import OpenAI
import pytest

from agent_request_timing import (
    RequestPreparationTrace, request_timing_scope, send_path_scope,
    send_path_stage, mark_send_path,
)


@pytest.mark.parametrize('direct',[False,True])
def test_real_sdk_and_direct_stream_have_thread_route_build_and_send_points(monkeypatch,direct):
    from agent_harness import RequestResponseLogger,ExecutorLLMClient
    from agent_messages import UserMessage
    from agent_openai import run_chat_completion_stream_worker
    from llm.transport import OpenAICompatibleTransport
    monkeypatch.setenv('LLM_STREAM_PREFER_DIRECT','1' if direct else '0')
    content='data: '+json.dumps({'id':'c','object':'chat.completion.chunk','choices':[{'index':0,'delta':{'content':'ok'},'finish_reason':None}]})+'\n\ndata: [DONE]\n\n'
    bodies=[]
    def handle(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200,headers={'content-type':'text/event-stream'},text=content)
    trace=RequestPreparationTrace('s','r',2,previous_tool_iter=1)
    with RequestResponseLogger(transport=httpx.MockTransport(handle)) as http:
        sdk=OpenAI(api_key='test',base_url='http://benchmark.invalid/v1',http_client=http,max_retries=0)
        facade=ExecutorLLMClient([{'provider':'openai-compatible','client':sdk,'transport':OpenAICompatibleTransport(sdk),'model':'test-model','input_modalities':['text']}])
        q=Queue()
        with request_timing_scope(trace):
            run_chat_completion_stream_worker(q,facade,'test-model',[UserMessage(content='hello')],temperature=0,max_tokens=16)
    rows=[]
    while not q.empty(): rows.append(q.get())
    assert next(row[1] for row in rows if row[0]=='turn').content=='ok'
    assert len(bodies)==1 and bodies[0]['messages'][0]['content']=='hello'
    paths=trace.snapshot()['send_paths']
    primary=next(path for path in paths if path['role']=='primary')
    points=primary['points'];names=[p['name'] for p in points]
    expected=['thread_scheduled','path_entered','stream_route_started','stream_route_completed','stream_object_created','stream_iteration_entered','facade_entered','candidate_prepare_started','candidate_prepare_completed','provider_stream_entered','http_request_build_started','http_request_build_completed','http_client_send_called','http_send_entered','path_exited']
    assert [names.index(n) for n in expected]==sorted(names.index(n) for n in expected)
    assert points[0]['thread']!=points[1]['thread']
    assert all(p['thread']==points[1]['thread'] for p in points[1:])
    assert trace.snapshot()['http_send_observed']
    assert primary['dropped_points']==0


def test_request_worker_path_is_present_for_nonstream_http_and_preserves_body():
    from agent_harness import RequestResponseLogger
    from agent_request_executor import run_request_worker
    trace=RequestPreparationTrace('s','nonstream',1)
    with RequestResponseLogger(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'ok':True}))) as http:
        async def run():
            with request_timing_scope(trace):
                return await run_request_worker(lambda:http.post('http://benchmark.invalid/local',json={'message':'hello'}),trace=trace)
        assert asyncio.run(run()).json()=={'ok':True}
    names=[p['name'] for p in trace.snapshot()['send_paths'][0]['points']]
    assert names==['path_entered','http_request_build_started','http_request_build_completed','http_client_send_called','http_send_entered','http_transport_delegate_entered','path_exited']


def test_send_path_failure_boundaries_are_bounded_and_snapshot_is_detached():
    trace=RequestPreparationTrace('s','r',1)
    with request_timing_scope(trace):
        with send_path_scope('primary'):
            with pytest.raises(ValueError,match='failed'):
                with send_path_stage('build'):
                    raise ValueError('failed')
            for _ in range(120):mark_send_path('extra')
        for _ in range(20):
            with send_path_scope('retry'):pass
    snap=trace.snapshot()
    assert len(snap['send_paths'])==16 and snap['dropped_send_paths']==5
    first=snap['send_paths'][0]
    assert len(first['points'])==96 and first['dropped_points']>0
    names=[p['name'] for p in first['points']]
    assert 'build_failed' in names and 'build_completed' not in names and 'http_send_entered' not in names
    first['points'][0]['name']='mutated'
    assert trace.snapshot()['send_paths'][0]['points'][0]['name']=='path_entered'
    assert not trace.snapshot()['http_send_observed']
