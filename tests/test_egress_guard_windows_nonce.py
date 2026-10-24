"""Compile the real Windows helper; test exclusive claims beyond MAX_PATH."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows native helper integration')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def helper(tmp_path_factory):
    compiler = Path(os.environ.get('WINDIR', r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not compiler.is_file():
        pytest.skip('Windows C# compiler unavailable')
    output = tmp_path_factory.mktemp('nonce-helper')/'helper.exe'
    result = subprocess.run([str(compiler),'/nologo','/optimize+','/target:exe',f'/out:{output}',
                             '/reference:System.Web.Extensions.dll',
                             str(ROOT/'app/native/windows/SugarAgentEgressHelper.cs')],
                            capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    return output


def prepared(helper, temporary, monkeypatch):
    from security import egress_guard as guard
    from security.models import CapabilityRequest, SecurityDecision, DecisionOutcome, PermissionMode, PERMISSION_PRESETS
    monkeypatch.setenv('SUGAR_AGENT_EGRESS_HELPER',str(helper))
    monkeypatch.setenv('EGRESS_HELPER_ENABLED','1')
    monkeypatch.setattr(guard,'_HEALTH_CACHE',None)
    request = CapabilityRequest.create(action='process.exec',resource='echo nonce-ok',effect='workspace_write',
                                       arguments={'command':'echo nonce-ok'},metadata={'egress_intent':'read'})
    active = {'session_id':str(uuid.uuid4()),'context':PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL],
              'request':request,'decision':SecurityDecision(DecisionOutcome.ALLOW,'local test','test',request.digest(4))}
    env = dict(os.environ,TEMP=str(temporary),TMP=str(temporary))
    launch = guard.prepare_egress_launch(['cmd.exe','/d','/c','echo nonce-ok'],env,command='echo nonce-ok',active_context=active)
    assert launch.ticket_id
    payload = json.loads(base64.urlsafe_b64decode(launch.argv[launch.argv.index('--ticket')+1]))['payload']
    marker = temporary/'sugaragent-egress-nonces'/hashlib.sha256(active['session_id'].encode()).hexdigest()[:24]/(hashlib.sha256(payload['nonce'].encode()).hexdigest()+'.used')
    return launch, marker


def invoke(launch):
    return subprocess.run(launch.argv,env=launch.env,capture_output=True,text=True,encoding='utf-8',timeout=15)


def test_long_marker_first_claim_succeeds_and_replay_is_rejected(helper,tmp_path,monkeypatch):
    temporary = tmp_path/('t'*max(1,175-len(str(tmp_path))-1))
    temporary.mkdir()
    launch, marker = prepared(helper,temporary,monkeypatch)
    assert len(str(marker)) > 260 and len(str(marker.parent)) < 248
    first = invoke(launch)
    assert first.returncode == 0 and 'nonce-ok' in first.stdout, first.stderr
    # This host also requires the extended spelling for Python's stat call.
    assert Path('\\\\?\\'+str(marker)).is_file()
    replay = invoke(launch)
    assert replay.returncode == 69 and 'already used' in replay.stderr
    assert 'nonce-ok' not in replay.stdout


def test_invalid_signature_never_claims_marker_or_launches_command(helper,tmp_path,monkeypatch):
    launch, marker = prepared(helper,tmp_path,monkeypatch)
    env = dict(launch.env,SUGAR_AGENT_EGRESS_COMMAND_DIGEST='incorrect')
    result = subprocess.run(launch.argv,env=env,capture_output=True,text=True,timeout=15)
    assert result.returncode == 69 and 'command digest mismatch' in result.stderr
    assert not marker.exists() and 'nonce-ok' not in result.stdout


def test_io_failure_remains_closed_and_is_not_reported_as_replay(helper,tmp_path,monkeypatch):
    temporary = tmp_path/'not-a-directory'
    temporary.write_text('occupied',encoding='utf8')
    launch, marker = prepared(helper,temporary,monkeypatch)
    result = invoke(launch)
    assert result.returncode == 69 and result.stderr
    assert 'already used' not in result.stderr and 'nonce-ok' not in result.stdout
