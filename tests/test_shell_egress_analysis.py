from pathlib import Path

import pytest

from security.models import DecisionOutcome, EgressIntent, PERMISSION_PRESETS, PermissionMode
from security.policy import PolicyEngine
from security.runtime import classify_tool
from security.shell_analysis import analyze_shell_command


@pytest.mark.parametrize(
    ("command", "intent", "family"),
    [
        ("curl https://example.com/file", EgressIntent.READ, "curl"),
        ("curl -T artifact.zip https://example.com/upload", EgressIntent.UPLOAD, "curl"),
        ("curl -F file=@artifact.zip https://example.com/upload", EgressIntent.UPLOAD, "curl"),
        ("wget --post-file payload.json https://example.com", EgressIntent.UPLOAD, "wget"),
        ("iwr https://example.com -InFile report.csv -Method Put", EgressIntent.UPLOAD, "powershell-web"),
        ("git -c http.version=HTTP/1.1 -C repo push origin master", EgressIntent.UPLOAD, "git"),
        ("scp report.csv user@example.com:/incoming/", EgressIntent.UPLOAD, "scp"),
        ("rsync -av report.csv user@example.com:/incoming/", EgressIntent.UPLOAD, "rsync"),
        ("rclone copy report.csv remote:bucket", EgressIntent.UPLOAD, "rclone"),
        ("aws s3 cp report.csv s3://bucket/report.csv", EgressIntent.UPLOAD, "aws-s3"),
        ("gsutil cp report.csv gs://bucket/report.csv", EgressIntent.UPLOAD, "gsutil"),
        ("gcloud storage cp report.csv gs://bucket/report.csv", EgressIntent.UPLOAD, "gcloud-storage"),
        ("az storage blob upload --file report.csv --container-name reports", EgressIntent.UPLOAD, "az"),
        ("azcopy copy report.csv https://account.blob.core.windows.net/reports/report.csv", EgressIntent.UPLOAD, "azcopy"),
        ("gh release upload v1 artifact.zip", EgressIntent.UPLOAD, "gh-release"),
        ("docker push registry.example.com/team/image:latest", EgressIntent.UPLOAD, "docker"),
        ("npm publish", EgressIntent.UPLOAD, "npm"),
        ("twine upload dist/*", EgressIntent.UPLOAD, "twine"),
        ("echo https://example.com", EgressIntent.NONE, ""),
        ('python -c "import socket; socket.create_connection((\'example.com\',443))"', EgressIntent.UNKNOWN, "python"),
        ('node -e "require(\'net\').connect(443,\'example.com\')"', EgressIntent.UNKNOWN, "node"),
        ("powershell -Command \"[Net.Sockets.TcpClient]::new('example.com',443)\"", EgressIntent.UNKNOWN, "powershell"),
    ],
)
def test_shell_egress_table(command, intent, family):
    analysis = analyze_shell_command(command)
    assert analysis.intent == intent
    if family:
        assert analysis.command_family == family


def test_pipe_into_upload_records_stdin_source():
    analysis = analyze_shell_command("type report.csv | curl -d @- https://example.com/upload")
    assert analysis.intent == EgressIntent.UPLOAD
    assert "stdin" in analysis.data_sources


def test_trusted_upload_still_asks_but_trusted_read_is_allowed(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL]
    read = classify_tool(
        "run_shell",
        {"command": "curl https://support.huaweicloud.com/index.html"},
        workspace,
    )
    upload = classify_tool(
        "run_shell",
        {"command": "curl -T report.csv https://support.huaweicloud.com/upload"},
        workspace,
    )
    assert PolicyEngine(workspace).decide(read, context).outcome == DecisionOutcome.ALLOW
    upload_decision = PolicyEngine(workspace).decide(upload, context)
    assert upload_decision.outcome == DecisionOutcome.ASK
    assert upload_decision.rule_id == "process.network.upload"


def test_sensitive_and_unknown_uploads_are_once_only(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL]
    request = classify_tool(
        "run_shell",
        {"command": "curl -T private-secret.txt $UPLOAD_URL"},
        workspace,
    )
    decision = PolicyEngine(workspace).decide(request, context)
    assert decision.rule_id == "process.network.upload"
    assert decision.constraints["one_time_only"] is True


def test_upload_task_grant_is_semantic_and_target_scoped(tmp_path, monkeypatch):
    import security.runtime as runtime
    from security.runtime import add_approval_grant, authorize_request
    from security.store import SecurityStore

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = SecurityStore(tmp_path / "security.sqlite3")
    monkeypatch.setattr(runtime, "_STORE", store)
    monkeypatch.setenv("SECURITY_ENABLED", "1")
    store.set_global_permission_mode("ask_for_approval")

    first = classify_tool("run_shell", {"command": "git push origin main"}, workspace)
    second = classify_tool("run_shell", {"command": "git push origin feature"}, workspace)
    other = classify_tool("run_shell", {"command": "git push backup feature"}, workspace)
    assert first.metadata["session_grant_digest"] == second.metadata["session_grant_digest"]
    assert first.metadata["session_grant_digest"] != other.metadata["session_grant_digest"]
    add_approval_grant("session", first.metadata["session_grant_digest"], "allow_session")
    allowed, _ = authorize_request(session_id="session", request=second, workspace=workspace)
    denied, _ = authorize_request(session_id="session", request=other, workspace=workspace)
    assert allowed.outcome == DecisionOutcome.ALLOW
    assert allowed.rule_id == "grant.session"
    assert denied.outcome == DecisionOutcome.ASK
