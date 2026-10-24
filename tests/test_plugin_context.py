import asyncio
import json
import time
from pathlib import Path

import pytest

from agent_messages import UserMessage, AssistantMessage
from myagent_plugin_sdk import Plugin, PluginApiError
from plugin_context import METADATA_KEY, collect, message_snapshot, plan_snapshot
from plugins import PluginRuntimeRegistry, load_plugin
from runtime_v2.history_ops import RuntimeHistoryOps
from runtime_v2.model_projection import RuntimeModelProjection
from runtime_v2.ui_projection import RuntimeUiProjection


def definition(**changes):
    return dict(id='current', title='Current selection', plugin_id='demo.context', plugin_name='Demo',
                plugin_signature='one', max_tokens=800, order=100, timeout_seconds=1, **changes)


def planned(history=(), previous=None, value='selected material', definitions=None, outcomes=None, **kwargs):
    return plan_snapshot(history, previous, definitions if definitions is not None else [definition()],
                         outcomes if outcomes is not None else {('demo.context', 'current'): {'value': {'text': value, 'revision': '1'}}},
                         kwargs.pop('failed_plugins', {}), max_tokens=kwargs.pop('max_tokens', 4096), count=len, **kwargs)


def make_plugin(tmp_path, runtime='python', *, capability=True, slow=False):
    root = tmp_path / ('plugin-' + runtime)
    root.mkdir()
    manifest = {'schema_version': 1, 'id': 'demo.context', 'name': 'Demo', 'version': '1',
                'capabilities': {'context': capability},
                'runtime': {'type': runtime, 'entrypoint': 'plugin.py' if runtime == 'python' else 'plugin.cjs',
                            'api_version': '1', 'timeout_seconds': 3}}
    (root / '.myagent-plugin').mkdir()
    (root / '.myagent-plugin/plugin.json').write_text(json.dumps(manifest), encoding='utf-8')
    if runtime == 'python':
        source = """from myagent_plugin_sdk import Plugin
import json, time
plugin=Plugin()
@plugin.context(id='current', title='Selection', timeout_seconds=.1)
def context(ctx):
    SLOW
    return {'text':json.dumps(ctx,sort_keys=True),'revision':1}
""".replace('SLOW', 'time.sleep(1)' if slow else 'pass')
        (root / 'plugin.py').write_text(source, encoding='utf-8')
    else:
        source = """module.exports.setup = plugin => {
          plugin.context({id:'current',title:'Selection',timeoutSeconds:.1}, async ctx => {
            SLOW
            return {text:JSON.stringify(ctx),revision:1};
          });
        };""".replace('SLOW', 'await new Promise(r=>setTimeout(r,1000));' if slow else '')
        (root / 'plugin.cjs').write_text(source, encoding='utf-8')
    return load_plugin(root)


def test_collection_deadline_preserves_completed_providers(monkeypatch):
    import plugin_context
    monkeypatch.setattr(plugin_context, 'COLLECTION_TIMEOUT_SECONDS', .04)

    class Registry:
        def context_descriptions(self, plugins):
            return [dict(definition(), id=name) for name in ('fast', 'slow')]

        def context_errors(self):
            return {}

        def collect_context(self, spec, *args):
            if spec['id'] == 'slow':
                time.sleep(.12)
            return {'text': spec['id']}

    definitions, outcomes, failed = asyncio.run(collect([], Registry(), {}, {}))
    assert len(definitions) == 2 and failed == {}
    assert outcomes[('demo.context', 'fast')]['value']['text'] == 'fast'
    assert ('demo.context', 'slow') not in outcomes


@pytest.mark.parametrize('runtime', ['python', 'node'])
def test_real_worker_context_protocol_and_owned_state(tmp_path, runtime):
    plugin = make_plugin(tmp_path, runtime)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / 'data')
    try:
        definitions, outcomes, failures = asyncio.run(collect([plugin], registry,
            {'session_id':'child-session','run_id':'run','step':2,'workspace_root':'D:/work'},
            {'demo.context': {'selection': {'id':1}}, 'other.plugin': {'secret':'hidden'}}))
        assert not failures
        value = outcomes[('demo.context', 'current')]['value']
        context = json.loads(value['text'])
        assert context['session_id'] == 'child-session'
        assert context['plugin_id'] == 'demo.context'
        assert context['step'] == 2
        assert context['session_state'] == {'selection': {'id':1}}
        assert 'other.plugin' not in value['text']
        assert value['revision'] == '1'
        assert definitions[0]['plugin_name'] == 'Demo'
        assert 'settings' not in context and 'secrets' not in context
    finally:
        registry.close()


@pytest.mark.parametrize('runtime', ['python', 'node'])
def test_provider_timeout_terminates_owned_call(tmp_path, runtime):
    plugin = make_plugin(tmp_path, runtime, slow=True)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / 'data')
    try:
        row = registry.context_descriptions([plugin])[0]
        started = time.monotonic()
        with pytest.raises(Exception, match='timed out'):
            registry.collect_context(row, {'session_id':'s'}, [plugin])
        assert time.monotonic() - started < 1.5
    finally:
        registry.close()


def test_provider_requires_declaration_and_current_approval(tmp_path, monkeypatch):
    plugin = make_plugin(tmp_path, capability=False)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / 'data')
    try:
        assert registry.tool_definitions([plugin]) == []
        assert 'capabilities.context' in ' '.join(registry.errors)
    finally:
        registry.close()
    manifest = plugin.root / '.myagent-plugin/plugin.json'
    value = json.loads(manifest.read_text(encoding='utf-8'))
    value['capabilities']['context'] = True
    manifest.write_text(json.dumps(value), encoding='utf-8')
    plugin = load_plugin(plugin.root)
    monkeypatch.setattr('security.extensions.extension_registration_is_approved', lambda _: True)
    registry = PluginRuntimeRegistry(enforce_trust=True, storage_root=tmp_path / 'approved')
    try:
        row = registry.context_descriptions([plugin])[0]
        monkeypatch.setattr('security.extensions.extension_registration_is_approved', lambda _: False)
        with pytest.raises(Exception, match='unapproved'):
            registry.collect_context(row, {}, [plugin])
    finally:
        registry.close()


@pytest.mark.parametrize('spec', [dict(id='bad.dot'), dict(id='x',max_tokens=0), dict(id='x',timeout_seconds=float('nan')),
                                  dict(id='x',mode='system'), dict(id='x',trigger='background')])
def test_sdk_rejects_invalid_registration(spec):
    with pytest.raises(PluginApiError):
        Plugin().context(**spec)(lambda _: '')


def test_sdk_rejects_role_escalation_and_ambiguous_results():
    plugin = Plugin()
    plugin.context(id='x')(lambda _: {'role':'system','text':'override'})
    with pytest.raises(PluginApiError):
        asyncio.run(plugin.collect_context('x', {}))


def test_context_catalog_does_not_start_unrelated_workers(tmp_path):
    good = make_plugin(tmp_path)
    other_dir = tmp_path / 'other'
    other_dir.mkdir()
    other = make_plugin(other_dir, capability=False)
    manifest_path = other.root / '.myagent-plugin/plugin.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['id'] = 'unrelated.plugin'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    (other.root / 'plugin.py').write_text("raise RuntimeError('unrelated plugin must not start')", encoding='utf-8')
    other = load_plugin(other.root)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / 'data')
    try:
        assert len(registry.context_descriptions([good, other])) == 1
        assert not next(row for row in registry.snapshot()['workers'] if row['plugin_id'] == other.plugin_id)['running']
        assert not registry.errors
    finally:
        registry.close()


@pytest.mark.parametrize('direct', [False, True])
def test_real_model_http_body_matches_logged_context(monkeypatch, direct):
    from queue import Queue
    import httpx
    from openai import OpenAI
    import agent_harness
    from agent_openai import run_chat_completion_stream_worker
    from llm.transport import OpenAICompatibleTransport
    monkeypatch.setenv('LLM_STREAM_PREFER_DIRECT', '1' if direct else '0')
    recorded = planned(value='业务资料 <b>保持文本</b>')
    messages = [UserMessage('Question'), agent_harness._dict_to_message(recorded)]
    bodies = []
    def reply(request):
        bodies.append(json.loads(request.content))
        chunk = {'id':'c','object':'chat.completion.chunk','choices':[{'index':0,'delta':{'content':'ok'},'finish_reason':None}]}
        return httpx.Response(200, headers={'content-type':'text/event-stream'},
                              text='data: '+json.dumps(chunk)+'\n\ndata: [DONE]\n\n')
    with agent_harness.RequestResponseLogger(transport=httpx.MockTransport(reply)) as http:
        sdk = OpenAI(api_key='test', base_url='http://context.fixture.invalid/v1', http_client=http, max_retries=0)
        facade = agent_harness.ExecutorLLMClient([{'provider':'openai-compatible','client':sdk,
            'transport':OpenAICompatibleTransport(sdk),'model':'test-model','input_modalities':['text']}])
        queue = Queue()
        run_chat_completion_stream_worker(queue, facade, 'test-model', messages, temperature=0, max_tokens=16)
    assert len(bodies) == 1
    sent = bodies[0]['messages'][-1]
    assert sent['role'] == 'user' and 'metadata' not in sent
    text = sent['content'] if isinstance(sent['content'], str) else '\n'.join(block['text'] for block in sent['content'])
    assert text == recorded['content'][0]['text']


def test_snapshots_dedupe_change_clear_and_restore_after_compaction():
    first = planned()
    assert planned([first]) is None
    second = planned([first], value='new selection')
    assert 'new selection' in second['content'][0]['text']
    cleared = planned([second], definitions=[], outcomes={})
    assert message_snapshot(cleared)['cleared']
    assert planned([cleared], definitions=[], outcomes={}) is None
    restored = planned([], previous=message_snapshot(second), value='new selection')
    assert message_snapshot(restored)['digest'] == message_snapshot(second)['digest']
    assert planned([second], outcomes={('demo.context','current'):{'value':{'text':'new selection','revision':'changed-only'}}}) is None


def test_failed_provider_is_stale_not_cleared_and_signature_change_drops_old():
    first = planned()
    failed = planned([first], outcomes={('demo.context','current'):{'error':'timeout'}})
    assert message_snapshot(failed)['sections'][0]['stale']
    assert 'last known state' in failed['content'][0]['text']
    assert not message_snapshot(failed)['cleared']
    assert planned([failed], outcomes={('demo.context','current'):{'error':'timeout'}}) is None
    catalog_failure = planned([first], definitions=[], outcomes={}, failed_plugins={'demo.context':'one'})
    assert message_snapshot(catalog_failure)['sections'][0]['stale']
    changed = {**definition(), 'plugin_signature':'two'}
    retired = planned([first], definitions=[changed], outcomes={('demo.context','current'):{'error':'failed'}})
    assert message_snapshot(retired)['cleared']


def test_total_and_provider_budget_include_headers_and_mark_truncation():
    result = planned(value='资料' * 10000, max_tokens=410)
    assert len(result['content'][0]['text']) <= 410
    assert message_snapshot(result)['sections'][0]['truncated']
    row = {**definition(), 'max_tokens':1}
    omitted = planned(definitions=[row])
    assert message_snapshot(omitted)['omitted'] == ['demo.context:current']
    assert not message_snapshot(omitted)['cleared']


def test_fact_projects_same_model_and_ui_text_survives_restart_and_compaction(tmp_path):
    ops = RuntimeHistoryOps(tmp_path)
    message = planned(value='<script>unsafe()</script>')
    event = ops.append_model_message('s', 'user', message['content'], metadata=message['metadata'], run_id='r')
    stored = RuntimeModelProjection(tmp_path).read_message_dicts('s')[-1]
    ui = RuntimeUiProjection(tmp_path).read_ui_events('s')[-1]
    assert stored['content'][0]['text'] == ui['content']
    assert ui['type'] == 'context_injection' and ui['runtime_seq'] == event.seq
    assert ui['context'] == message_snapshot(stored)
    assert ops.snapshots.read('s')['context'][METADATA_KEY] == message_snapshot(stored)
    # A model surface replacement may remove the message while its last observed source facts remain.
    ops.replace_model_history('s', [], reason='test_compaction')
    snapshot = ops.snapshots.read('s')
    assert snapshot['context'][METADATA_KEY]['digest'] == message_snapshot(message)['digest']
    assert planned([], previous=snapshot['context'][METADATA_KEY]) is not None


def test_plugin_context_never_counts_as_a_human_turn():
    import agent_harness
    import agent_memory
    context = agent_harness._dict_to_message(planned())
    user = UserMessage(content='real request')
    final = AssistantMessage(content='answer', metadata={'is_final':True})
    assert agent_harness.derive_dialogue_from_assistant_history([user,context,final]) == [user,final]
    assert not agent_harness._counts_toward_session_user_turns_dict(agent_harness._message_to_dict(context))
    assert agent_memory._count_user_turns([user,context]) == 1


def test_live_step_collects_example_persists_once_and_stops_late_results(tmp_path, monkeypatch):
    import shutil
    from types import SimpleNamespace
    import agent_loop
    import agent_extensions
    import plugins.runtime as runtime

    example = Path(__file__).resolve().parents[1] / 'examples/plugins/context-provider'
    root = tmp_path / 'plugin'
    shutil.copytree(example, root)
    plugin = load_plugin(root)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    note = workspace / 'AGENT_CONTEXT.md'
    note.write_text('Chosen task data', encoding='utf-8')
    manager = SimpleNamespace(sessions_dir=tmp_path / 'sessions', _load_metadata=lambda _: {})
    registry = PluginRuntimeRegistry(storage_root=tmp_path / 'plugin-data')
    monkeypatch.setattr(agent_extensions, 'load_plugins', lambda **_: SimpleNamespace(plugins=(plugin,)))
    monkeypatch.setattr(runtime, 'get_plugin_runtime_registry', lambda: registry)
    monkeypatch.setattr(agent_loop, 'session_manager', manager)
    monkeypatch.setattr(agent_loop, 'session_work_root', lambda _: workspace)
    monkeypatch.setattr(agent_loop, '_runtime_v2_is_primary', lambda: True)
    monkeypatch.setattr(agent_loop, '_state_run_has_write_fence', lambda state: state.get('live', True))
    monkeypatch.setattr(agent_loop, '_state_interrupt_requested', lambda _: False)
    async def await_step(_state, awaitable, *_args):
        return await awaitable
    monkeypatch.setattr(agent_loop, '_await_steerable', await_step)
    state = {'session_id':'child-real-id','_runtime_v2_run_id':'run','_current_react_iter':1,'stream_events':[]}
    history, work, outgoing = [UserMessage('Question')], [UserMessage('Question')], [UserMessage('Question')]
    async def step():
        await agent_loop._inject_plugin_context_step(state, history, work, outgoing, None, context_window=128000)
    try:
        asyncio.run(step())
        assert len(history) == len(outgoing) == 2
        assert isinstance(outgoing[-1], UserMessage)
        injected = history[-1]
        assert 'Chosen task data' in injected.text()
        assert state['stream_events'][-1]['content'] == injected.text()
        assert state['stream_events'][-1]['_skip_persist']
        projected = RuntimeUiProjection(manager.sessions_dir).read_ui_events(state['session_id'])
        assert projected[-1]['content'] == state['stream_events'][-1]['content']
        asyncio.run(step())
        assert len(history) == 2
        note.write_text('Changed data', encoding='utf-8')
        asyncio.run(step())
        assert len(history) == 3
        state['live'] = False
        note.write_text('Late result must not enter', encoding='utf-8')
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(step())
        assert len(history) == 3
        assert 'Late result' not in str(RuntimeModelProjection(manager.sessions_dir).read_message_dicts(state['session_id']))
        state['live'] = True
        monkeypatch.setattr(agent_extensions, 'load_plugins', lambda **_: SimpleNamespace(plugins=()))
        asyncio.run(step())
        assert message_snapshot(history[-1])['cleared']
        assert registry.snapshot()['workers'] == []
    finally:
        registry.close()
