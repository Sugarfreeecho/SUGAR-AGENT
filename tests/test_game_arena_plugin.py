import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
PLUGIN_ROOT = ROOT / "plugins" / "game-arena"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _tree_fingerprint(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_game_arena_uses_host_storage_and_does_not_modify_plugin_source(tmp_path):
    from myagent_plugin_sdk import parse_deferred_result
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(PLUGIN_ROOT)
    storage_root = tmp_path / "plugin-storage"
    workspace_root = tmp_path / "workspace"
    before = _tree_fingerprint(PLUGIN_ROOT)
    registry = PluginRuntimeRegistry(
        storage_root=storage_root,
        workspace_root=workspace_root,
    )
    definitions = registry.tool_definitions([plugin])
    create_name = next(
        item["function"]["name"]
        for item in definitions
        if item["function"]["name"].endswith("__gomoku_create")
    )

    result = registry.invoke(
        create_name,
        {"game_id": "host_storage", "board_size": 9},
        [plugin],
        context={"session_id": "player-black"},
    )
    state_response = registry.handle_http(
        "game-arena",
        {
            "method": "GET",
            "path": "/state",
            "query": {"game_id": "host_storage"},
            "headers": {},
            "body_base64": "",
        },
        [plugin],
    )
    start_response = registry.handle_http(
        "game-arena",
        {
            "method": "POST",
            "path": "/start",
            "query": {},
            "headers": {"content-type": "application/json"},
            "json": {
                "session_a": "session-a",
                "session_b": "session-b",
                "board_size": 9,
                "game_id": "web_start",
            },
            "body_base64": "",
        },
        [plugin],
    )
    registry.close()

    game_path = (
        storage_root.resolve()
        / "game-arena"
        / "data"
        / "games"
        / "host_storage.json"
    )
    assert result["ok"] is True
    assert result["game_id"] == "host_storage"
    assert result["_host_actions"] == [
        {
            "service": "session_state.set_latest",
            "namespace": "current-game",
            "value": {
                "game_id": "host_storage",
                "status": "waiting",
                "turn": "black",
                "move_count": 0,
                "message": result["msg"],
            },
        },
        {
            "service": "session_events.append",
            "event_name": "game_updated",
            "data": {
                "game_id": "host_storage",
                "status": "waiting",
                "turn": "black",
                "move_count": 0,
                "message": result["msg"],
            },
        }
    ]
    deferred_token = parse_deferred_result(result).token
    assert game_path.is_file()
    stored = json.loads(game_path.read_text(encoding="utf-8"))
    assert stored["players"]["black"] == "player-black"
    assert state_response["status"] == 200
    assert state_response["json"]["game"]["board_svg"].startswith("<svg")
    assert state_response["json"]["game"]["board_ascii"]
    assert start_response["status"] == 202
    assert start_response["json"]["game_id"] == "web_start"
    assert start_response["_host_actions"][0]["service"] == "sessions.run_many"
    pending_state = json.loads(
        (
            storage_root
            / "game-arena"
            / "data"
            / "deferred-waits.json"
        ).read_text(encoding="utf-8")
    )
    assert deferred_token not in pending_state["waits"]
    assert _tree_fingerprint(PLUGIN_ROOT) == before
    assert not list((PLUGIN_ROOT / "engine").glob("_gomoku_*.py"))


def test_game_arena_web_start_uses_one_time_host_session_grant():
    source = (PLUGIN_ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert "/api/extensions/session-run-grant" in source
    assert "X-Plugin-Session-Run-Grant" in source
    assert "plugin_id:'game-arena'" in source


def test_game_arena_links_to_canonical_execution_dashboard_page():
    source = (PLUGIN_ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'href="/plugins/execution-dashboard"' in source
    assert 'href="/execution-dashboard"' not in source


def test_game_arena_uses_host_validated_default_board_size_setting(tmp_path):
    from plugins import PluginRuntimeRegistry, PluginSettingsStore, load_plugin

    plugin = load_plugin(PLUGIN_ROOT)
    storage_root = tmp_path / "plugin-storage"
    PluginSettingsStore(storage_root / "_host" / "settings.json").update(
        plugin, {"default_board_size": 9}
    )
    registry = PluginRuntimeRegistry(storage_root=storage_root)
    function_name = next(
        item["function"]["name"]
        for item in registry.tool_definitions([plugin])
        if item["function"]["name"].endswith("__gomoku_create")
    )

    result = registry.invoke(
        function_name,
        {"game_id": "configured_size"},
        [plugin],
        context={"session_id": "black"},
    )
    registry.close()

    assert result["board_size"] == 9


def test_game_arena_copies_legacy_games_into_host_storage(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    workspace_root = tmp_path / "workspace"
    legacy_games = workspace_root / ".myagent" / "game-arena" / "games"
    legacy_games.mkdir(parents=True)
    legacy_payload = {
        "id": "legacy_game",
        "board_size": 9,
        "board": [[0] * 9 for _ in range(9)],
        "status": "waiting",
        "updated_at": 1,
    }
    (legacy_games / "legacy_game.json").write_text(
        json.dumps(legacy_payload),
        encoding="utf-8",
    )
    storage_root = tmp_path / "plugin-storage"
    plugin = load_plugin(PLUGIN_ROOT)
    registry = PluginRuntimeRegistry(
        storage_root=storage_root,
        workspace_root=workspace_root,
    )

    registry.tool_definitions([plugin])
    registry.close()

    migrated = (
        storage_root.resolve()
        / "game-arena"
        / "data"
        / "games"
        / "legacy_game.json"
    )
    assert json.loads(migrated.read_text(encoding="utf-8")) == legacy_payload
    assert (legacy_games / "legacy_game.json").is_file()


def test_game_arena_deferred_turns_use_short_plugin_polls(tmp_path):
    from myagent_plugin_sdk import parse_deferred_result
    from plugins import PluginRuntimeError, PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(PLUGIN_ROOT)
    registry = PluginRuntimeRegistry(
        storage_root=tmp_path / "plugin-storage",
        workspace_root=tmp_path / "workspace",
    )
    definitions = registry.tool_definitions([plugin])
    names = {
        item["function"]["name"].rsplit("__", 1)[-1]: item["function"]["name"]
        for item in definitions
    }
    black_context = {"session_id": "black-player"}
    white_context = {"session_id": "white-player"}

    created = registry.invoke(
        names["gomoku_create"],
        {"game_id": "deferred_game", "board_size": 9},
        [plugin],
        context=black_context,
    )
    create_token = parse_deferred_result(created).token
    joined = registry.invoke(
        names["gomoku_join"],
        {"game_id": "deferred_game"},
        [plugin],
        context=white_context,
    )
    join_token = parse_deferred_result(joined).token

    create_final = registry.poll_deferred(
        names["gomoku_create"],
        create_token,
        [plugin],
        context=black_context,
    )
    black_move = registry.invoke(
        names["gomoku_place"],
        {"game_id": "deferred_game", "x": 0, "y": 0},
        [plugin],
        context=black_context,
    )
    black_token = parse_deferred_result(black_move).token
    join_final = registry.poll_deferred(
        names["gomoku_join"],
        join_token,
        [plugin],
        context=white_context,
    )
    with pytest.raises(
        PluginRuntimeError,
        match="not authorized for this session_id",
    ):
        registry.poll_deferred(
            names["gomoku_place"],
            black_token,
            [plugin],
            context=white_context,
        )
    white_move = registry.invoke(
        names["gomoku_place"],
        {"game_id": "deferred_game", "x": 1, "y": 0},
        [plugin],
        context=white_context,
    )
    white_token = parse_deferred_result(white_move).token
    black_final = registry.poll_deferred(
        names["gomoku_place"],
        black_token,
        [plugin],
        context=black_context,
    )
    cancelled = registry.cancel_deferred(
        names["gomoku_place"],
        white_token,
        "cancelled",
        [plugin],
        context=white_context,
    )
    registry.close()

    assert create_final["opponent_joined"] is True
    assert [item["service"] for item in create_final["_host_actions"]] == [
        "session_state.set_latest",
        "session_events.append",
    ]
    assert create_final["_host_actions"][1]["event_name"] == "game_updated"
    assert join_final["opponent_moved"] is True
    assert black_final["opponent_moved"] is True
    assert black_final["last_move"] == [1, 0]
    assert cancelled["cancelled"] is True
    assert "_host_actions" not in cancelled


def test_game_arena_deferred_wait_survives_worker_restart(tmp_path):
    from myagent_plugin_sdk import parse_deferred_result
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(PLUGIN_ROOT)
    storage_root = tmp_path / "plugin-storage"
    black_context = {"session_id": "black-restart"}
    white_context = {"session_id": "white-restart"}
    first = PluginRuntimeRegistry(storage_root=storage_root)
    names = {
        item["function"]["name"].rsplit("__", 1)[-1]: item["function"]["name"]
        for item in first.tool_definitions([plugin])
    }
    created = first.invoke(
        names["gomoku_create"],
        {"game_id": "restart_game", "board_size": 9},
        [plugin],
        context=black_context,
    )
    token = parse_deferred_result(created).token
    first.close(preserve_deferred=True)

    second = PluginRuntimeRegistry(storage_root=storage_root)
    still_pending = second.poll_deferred(
        names["gomoku_create"],
        token,
        [plugin],
        context=black_context,
    )
    second.invoke(
        names["gomoku_join"],
        {"game_id": "restart_game"},
        [plugin],
        context=white_context,
    )
    completed = second.poll_deferred(
        names["gomoku_create"],
        token,
        [plugin],
        context=black_context,
    )
    second.close()

    assert parse_deferred_result(still_pending).token == token
    assert completed["opponent_joined"] is True
    waits = json.loads(
        (
            storage_root
            / "game-arena"
            / "data"
            / "deferred-waits.json"
        ).read_text(encoding="utf-8")
    )
    assert token not in waits["waits"]


def test_game_arena_replay_reports_state_at_selected_move(tmp_path):
    from plugins import PluginRuntimeRegistry, load_plugin

    plugin = load_plugin(PLUGIN_ROOT)
    registry = PluginRuntimeRegistry(storage_root=tmp_path / "plugin-storage")
    names = {
        item["function"]["name"].rsplit("__", 1)[-1]: item["function"]["name"]
        for item in registry.tool_definitions([plugin])
    }
    registry.invoke(
        names["gomoku_create"],
        {"game_id": "replay_state", "board_size": 9},
        [plugin],
        context={"session_id": "black-replay"},
    )
    registry.invoke(
        names["gomoku_join"],
        {"game_id": "replay_state"},
        [plugin],
        context={"session_id": "white-replay"},
    )
    registry.invoke(
        names["gomoku_place"],
        {"game_id": "replay_state", "x": 4, "y": 4},
        [plugin],
        context={"session_id": "black-replay"},
    )

    at_start = registry.handle_http(
        "game-arena",
        {
            "method": "GET",
            "path": "/replay",
            "query": {"game_id": "replay_state", "move_no": "0"},
            "headers": {},
            "body_base64": "",
        },
        [plugin],
    )["json"]
    after_black = registry.handle_http(
        "game-arena",
        {
            "method": "GET",
            "path": "/replay",
            "query": {"game_id": "replay_state", "move_no": "1"},
            "headers": {},
            "body_base64": "",
        },
        [plugin],
    )["json"]
    registry.close()

    assert at_start["status"] == "playing"
    assert at_start["turn"] == "black"
    assert at_start["winner"] is None
    assert after_black["status"] == "playing"
    assert after_black["turn"] == "white"
    assert after_black["winner"] is None


def test_game_arena_frontend_interaction_contracts():
    source = (PLUGIN_ROOT / "web" / "index.html").read_text(encoding="utf-8")

    assert 'grid-template-areas:"board" "black" "white"' in source
    assert 'id="sessionSearchA"' in source
    assert 'id="swapSessions"' in source
    assert 'aria-live="polite"' in source
    assert "if(cache.inFlight) return" in source
    assert "appendUniqueEvents(cache,events)" in source
    assert "回放中" in source
    assert "updateReplayControls" in source
    assert "tr.classList.toggle('selected',selected)" in source
    assert 'id="blackPlayerName"' in source
    assert 'id="whitePlayerName"' in source
    assert 'id="latestBlack"' in source
    assert 'id="latestWhite"' in source
    assert "scrollTraceToLatest" in source
    assert "container.dataset.autoFollow" in source
    assert "grid-auto-rows:max-content" in source
    assert 'id="rematchBtn"' in source
    assert 'id="swapRematchBtn"' in source
    assert "async function startMatch" in source
    assert "overflow-wrap:anywhere" in source
    assert "session.run_active||session.stream_active" in source
    assert "option.dataset.busy=String(busy)" in source
    assert "REMATCH_IDLE_SAMPLES_REQUIRED=2" in source
    assert "MAX_BUSY_RETRIES=20" in source
    assert "j.error==='session_busy'" in source
    assert "{waitForBusy:true}" in source
    assert "missingIds.map(async id" in source
    assert "双方会话已空闲，可以开始下一局" in source


def test_core_no_longer_generates_game_arena_python_sources():
    source = "\n".join(
        (APP_DIR / name).read_text(encoding="utf-8")
        for name in ("webui.py", "agent_loop.py")
    )

    assert "_gomoku_tmp.py" not in source
    assert "_gomoku_tmp2.py" not in source
    assert "_gomoku_block.py" not in source
    assert "game_arena_blocking_wait" not in source
    assert "plugin_game-arena__" not in (APP_DIR / "agent_loop.py").read_text(
        encoding="utf-8"
    )
