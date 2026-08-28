"""Game Arena - Gomoku plugin with quick handlers (blocking handled host-side)."""
from __future__ import annotations
import time
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from myagent_plugin_sdk import (
    Plugin,
    current_tool_context,
    deferred_result,
    with_host_actions,
)

plugin = Plugin()

try:
    from engine.gomoku import GomokuGame
    from storage import load_game, save_game, list_games, game_path, migrate_legacy_games
    from render import render_ascii, render_svg
except ImportError:
    from .engine.gomoku import GomokuGame
    from .storage import load_game, save_game, list_games, game_path, migrate_legacy_games
    from .render import render_ascii, render_svg

_engine = GomokuGame()
_pending_waits: Dict[str, Dict[str, Any]] = {}


@plugin.on_activate
def _migrate_legacy_storage(context: Dict[str, Any]) -> None:
    migrate_legacy_games(
        str(context.get("workspace_root") or ""),
        str(context.get("plugin_data_dir") or ""),
    )
    _restore_pending_waits(context)

def _now_ts() -> int:
    return int(time.time())

def _gen_id() -> str:
    return "g_" + uuid.uuid4().hex[:6]

def _current_session_id() -> str:
    return str(current_tool_context().session_id or "").strip()


def _default_board_size() -> int:
    raw = current_tool_context().settings.get("default_board_size", 15)
    try:
        size = int(raw)
    except (TypeError, ValueError):
        size = 15
    return size if 9 <= size <= 19 else 15

def _board_ascii(board, win_line=None) -> str:
    return render_ascii(board, win_line)

def _game_view_payload(state: Dict[str,Any]) -> Dict[str,Any]:
    board = state.get("board") or []
    win_line = state.get("win_line")
    ascii_board = _board_ascii(board, win_line)
    # Only return what LLM needs; board/board_svg/players are frontend-only and waste tokens
    payload = {
        "game_id": state.get("id"),
        "board_size": state.get("board_size"),
        "board_ascii": ascii_board,
        "turn": state.get("turn"),
        "status": state.get("status"),
        "winner": state.get("winner"),
        "last_move": state.get("last_move"),
        "move_count": len(state.get("history") or []),
        "history": state.get("history"),
    }
    if win_line:
        payload["win_line"] = win_line
    return payload


def _game_event_data(view: Dict[str, Any]) -> Dict[str, Any]:
    """Keep durable UI events compact and free of board/history token bulk."""

    data = {
        key: view.get(key)
        for key in (
            "game_id",
            "status",
            "turn",
            "winner",
            "last_move",
            "move_count",
        )
        if view.get(key) is not None
    }
    message = str(view.get("msg") or "").strip()
    if message:
        data["message"] = message[:1000]
    return data


def _with_game_event(view: Dict[str, Any]) -> Dict[str, Any]:
    return with_host_actions(
        view,
        [
            {
                "service": "session_state.set_latest",
                "namespace": "current-game",
                "value": _game_event_data(view),
            },
            {
                "service": "session_events.append",
                "event_name": "game_updated",
                "data": _game_event_data(view),
            }
        ],
    )


def _begin_wait(view: Dict[str, Any]) -> Dict[str, Any]:
    """Create an opaque deferred lease; polling remains a short Worker RPC."""

    token = uuid.uuid4().hex
    _pending_waits[token] = {
        "initial": dict(view),
        "game_id": str(view.get("game_id") or ""),
        "wait_reason": str(view.get("wait_reason") or ""),
        "history_length": len(view.get("history") or []),
        "session_id": _current_session_id(),
        "expires_at": time.time() + 300,
    }
    _persist_pending_waits()
    return deferred_result(
        token,
        _with_game_event(view),
        poll_after_ms=1000,
        timeout_seconds=300,
    )


def _pending_waits_path(plugin_data_dir: str = "") -> Path:
    raw = str(plugin_data_dir or current_tool_context().plugin_data_dir or "").strip()
    if not raw:
        raise RuntimeError("Game Arena requires host-provided plugin_data_dir")
    root = Path(raw).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root / "deferred-waits.json"


def _persist_pending_waits(plugin_data_dir: str = "") -> None:
    path = _pending_waits_path(plugin_data_dir)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"version": 1, "waits": _pending_waits}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _restore_pending_waits(context: Dict[str, Any]) -> None:
    path = _pending_waits_path(str(context.get("plugin_data_dir") or ""))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raw = {}
    waits = raw.get("waits") if isinstance(raw, dict) else None
    now = time.time()
    _pending_waits.clear()
    if isinstance(waits, dict):
        for token, value in waits.items():
            try:
                expires_at = float((value or {}).get("expires_at") or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            if (
                isinstance(value, dict)
                and str(token).strip()
                and expires_at > now
            ):
                _pending_waits[str(token)] = dict(value)
    _persist_pending_waits(str(context.get("plugin_data_dir") or ""))


def _finish_wait(token: str) -> None:
    _pending_waits.pop(str(token or ""), None)
    _persist_pending_waits()


def _validated_wait(token: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pending = _pending_waits.get(str(token or ""))
    if pending is None:
        return None
    owner = str(pending.get("session_id") or "")
    caller = str(context.get("session_id") or "")
    if owner and caller and owner != caller:
        return None
    if float(pending.get("expires_at") or 0) <= time.time():
        _finish_wait(token)
        return None
    return pending


@plugin.on_deferred_poll
def poll_wait(token: str, context: Dict[str, Any]) -> Dict[str, Any]:
    pending = _validated_wait(token, context)
    if pending is None:
        return {"ok": False, "error": "unknown or unauthorized deferred result"}
    initial = dict(pending["initial"])
    state = load_game(str(pending.get("game_id") or ""))
    if state is None:
        _finish_wait(token)
        return {"ok": False, "error": "game no longer exists"}

    wait_reason = str(pending.get("wait_reason") or "")
    if wait_reason == "join":
        if state.get("status") != "waiting" and (state.get("players") or {}).get("white"):
            _finish_wait(token)
            initial.update(_game_view_payload(state))
            initial.update({
                "status": state.get("status"),
                "players": state.get("players"),
                "turn": state.get("turn"),
                "msg": f"白方已加入房间 {state.get('id')}，游戏开始，轮到黑方落子。当前回合: {state.get('turn')}",
                "opponent_joined": True,
                "wait_for_opponent": False,
            })
            return _with_game_event(initial)
    elif wait_reason == "place":
        current_history = len(state.get("history") or [])
        if current_history > int(pending.get("history_length") or 0) or state.get("status") == "finished":
            _finish_wait(token)
            initial.update(_game_view_payload(state))
            initial["wait_for_opponent"] = False
            initial["opponent_moved"] = True
            if state.get("status") == "finished":
                initial["msg"] = f"对手已落子，游戏结束 winner={state.get('winner')}"
            else:
                last_move = state.get("last_move")
                initial["msg"] = (
                    f"对手已落子({last_move[0]},{last_move[1]})，轮到你落子。当前回合: {state.get('turn')}"
                    if last_move
                    else f"对手已落子，轮到你落子。当前回合: {state.get('turn')}"
                )
            return _with_game_event(initial)

    return deferred_result(
        token,
        initial,
        poll_after_ms=1000,
        timeout_seconds=300,
    )


@plugin.on_deferred_cancel
def cancel_wait(token: str, reason: str, context: Dict[str, Any]) -> Dict[str, Any]:
    pending = _validated_wait(token, context)
    if pending is None:
        return {"ok": False, "error": "unknown or unauthorized deferred result"}
    _finish_wait(token)
    result = dict(pending["initial"])
    result.pop("_host_actions", None)
    result["wait_for_opponent"] = False
    if reason == "timeout":
        result["timeout"] = True
        result["msg"] = (
            str(result.get("msg") or "")
            + " [等待对手超时(5分钟)，可用 gomoku_view 查看当前状态]"
        )
    else:
        result["cancelled"] = True
        result["msg"] = str(result.get("msg") or "") + " [等待已取消]"
    return result


def _http_json(payload: Dict[str, Any], status: int = 200) -> Dict[str, Any]:
    return {"status": status, "json": payload}


def _query(request: Dict[str, Any], name: str, default: str = "") -> str:
    query = request.get("query") if isinstance(request.get("query"), dict) else {}
    value = query.get(name, default)
    if isinstance(value, list):
        value = value[-1] if value else default
    return str(value if value is not None else default)


@plugin.on_http_request
def handle_http(request: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    method = str(request.get("method") or "GET").upper()
    path = "/" + str(request.get("path") or "").strip("/")
    if method == "GET" and path == "/games":
        status = _query(request, "status").strip() or None
        try:
            limit = max(1, min(100, int(_query(request, "limit", "20"))))
        except (TypeError, ValueError):
            limit = 20
        summary = []
        for state in list_games(status=status, limit=limit):
            summary.append({
                "game_id": state.get("id"),
                "board_size": state.get("board_size"),
                "status": state.get("status"),
                "turn": state.get("turn"),
                "winner": state.get("winner"),
                "players": state.get("players"),
                "move_count": len(state.get("history") or []),
                "updated_at": state.get("updated_at"),
                "created_at": state.get("created_at"),
            })
        return _http_json({"ok": True, "games": summary, "count": len(summary)})

    if method == "GET" and path == "/state":
        game_id = _query(request, "game_id")
        state = load_game(game_id)
        if state is None:
            return _http_json(
                {"ok": False, "error": f"game {game_id} not found"},
                404,
            )
        state["board_ascii"] = render_ascii(
            state.get("board") or [],
            state.get("win_line"),
        )
        state["board_svg"] = render_svg(
            state.get("board") or [],
            state.get("win_line"),
            state.get("last_move"),
        )
        return _http_json({"ok": True, "game": state})

    if method == "GET" and path == "/replay":
        game_id = _query(request, "game_id")
        state = load_game(game_id)
        if state is None:
            return _http_json(
                {"ok": False, "error": f"game {game_id} not found"},
                404,
            )
        history = state.get("history") or []
        size = int(state.get("board_size") or 15)
        try:
            move_no = max(0, min(len(history), int(_query(request, "move_no", "0"))))
        except (TypeError, ValueError):
            move_no = 0
        board = _engine.create_board(size)
        for move in history[:move_no]:
            try:
                board[int(move["y"])][int(move["x"])] = (
                    1 if move.get("color") == "black" else 2
                )
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        last = history[move_no - 1] if move_no else None
        last_move = [last.get("x"), last.get("y")] if last else None
        win_line = state.get("win_line") if move_no == len(history) else None
        return _http_json({
            "ok": True,
            "game_id": game_id,
            "move_no": move_no,
            "total": len(history),
            "board": board,
            "board_ascii": render_ascii(board, win_line),
            "board_svg": render_svg(board, win_line, last_move),
            "last_move": last_move,
            "history": history,
        })

    if method == "POST" and path == "/start":
        data = request.get("json") if isinstance(request.get("json"), dict) else {}
        session_a = str(data.get("session_a") or data.get("sessionA") or "").strip()
        session_b = str(data.get("session_b") or data.get("sessionB") or "").strip()
        if not session_a or not session_b or session_a == session_b:
            return _http_json(
                {"ok": False, "error": "two different sessions are required"},
                400,
            )
        try:
            board_size = int(data.get("board_size") or _default_board_size())
        except (TypeError, ValueError):
            board_size = _default_board_size()
        if board_size < 9 or board_size > 19:
            board_size = _default_board_size()
        game_id = "".join(
            char
            for char in str(data.get("game_id") or "")
            if char.isalnum() or char in "-_"
        ) or _gen_id()
        if load_game(game_id) is not None:
            return _http_json(
                {"ok": False, "error": f"game {game_id} already exists"},
                409,
            )
        prompt_a = f"""你正在参与五子棋对战 Game Arena
游戏ID: {game_id}  棋盘: {board_size}x{board_size}  你执黑(●) 先行
请立即调用 gomoku_create(game_id=\"{game_id}\", board_size={board_size})。
宿主会通过延迟结果等待白方加入；返回后继续用 gomoku_place 落子，目标五子连珠获胜。"""
        prompt_b = f"""你正在参与五子棋对战 Game Arena
游戏ID: {game_id}  棋盘: {board_size}x{board_size}  你执白(○)
请立即调用 gomoku_join(game_id=\"{game_id}\")。
宿主会通过延迟结果等待黑方落子；返回后继续用 gomoku_place 回应，目标五子连珠获胜。"""
        return {
            "status": 202,
            "json": {
                "ok": True,
                "game_id": game_id,
                "board_size": board_size,
                "session_a": session_a,
                "session_b": session_b,
            },
            "_host_actions": [
                {
                    "service": "sessions.run_many",
                    "sessions": [
                        {"session_id": session_a, "prompt": prompt_a},
                        {"session_id": session_b, "prompt": prompt_b},
                    ],
                }
            ],
        }
    return _http_json({"ok": False, "error": "not found"}, 404)

@plugin.tool(
    name="gomoku_create",
    description="Create a Gomoku game room (black first). Returns waiting status; host will block until white joins (5min).",
    effect="workspace_write",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string", "description": "Optional custom game id, auto-generated if empty"},
            "board_size": {"type": "integer", "description": "Board size 9-19; uses the plugin setting when omitted", "minimum": 9, "maximum": 19},
        },
        "additionalProperties": False,
    },
)
def gomoku_create(game_id: str = "", board_size: int | None = None) -> Dict[str,Any]:
    sid = _current_session_id()
    size = int(board_size) if board_size is not None and str(board_size).strip() else _default_board_size()
    if size < 9 or size > 19:
        return {"ok": False, "error": "board_size must be 9-19"}
    gid = str(game_id or "").strip() or _gen_id()
    # sanitize
    gid = "".join(c for c in gid if c.isalnum() or c in "-_") or _gen_id()
    if load_game(gid) is not None:
        return {"ok": False, "error": f"game_id {gid} already exists"}
    board = _engine.create_board(size)
    now = _now_ts()
    state = {
        "id": gid,
        "board_size": size,
        "board": board,
        "players": {"black": sid or "unknown", "white": ""},
        "player_names": {"black": sid[:8] if sid else "black", "white": ""},
        "turn": "black",
        "status": "waiting",
        "winner": None,
        "win_line": None,
        "history": [],
        "last_move": None,
        "created_at": now,
        "updated_at": now,
    }
    save_game(state)
    view = _game_view_payload(state)
    view.update({
        "ok": True,
        "color": "black",
        "msg": f"房间 {gid} 创建成功，你执黑(●) {size}x{size}，等待白方加入（最长5分钟）...",
        "wait_for_opponent": True,
        "wait_reason": "join",
    })
    return _begin_wait(view)

@plugin.tool(
    name="gomoku_join",
    description="Join a waiting Gomoku game as white. Host will block until black places first stone (5min).",
    effect="workspace_write",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string", "description": "Game id to join"},
        },
        "required": ["game_id"],
        "additionalProperties": False,
    },
)
def gomoku_join(game_id: str) -> Dict[str,Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if state.get("status") != "waiting":
        return {"ok": False, "error": f"game {gid} not waiting (status={state.get('status')})"}
    if state.get("players", {}).get("black") == sid:
        return {"ok": False, "error": "cannot join your own game"}
    if state.get("players", {}).get("white"):
        return {"ok": False, "error": "game already has white player"}
    state["players"]["white"] = sid or "unknown"
    state["player_names"]["white"] = sid[:8] if sid else "white"
    state["status"] = "playing"
    state["updated_at"] = _now_ts()
    save_game(state)
    view = _game_view_payload(state)
    view.update({
        "ok": True,
        "color": "white",
        "msg": f"已加入房间 {gid}，你执白(○) {state.get('board_size')}x{state.get('board_size')}，等待黑方落子（最长5分钟）...",
        "wait_for_opponent": True,
        "wait_reason": "place",
    })
    return _begin_wait(view)

@plugin.tool(
    name="gomoku_place",
    description="Place a stone at (x,y). Host will block until opponent moves if game not finished (5min).",
    effect="workspace_write",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string"},
            "x": {"type": "integer", "minimum": 0, "maximum": 18},
            "y": {"type": "integer", "minimum": 0, "maximum": 18},
        },
        "required": ["game_id","x","y"],
        "additionalProperties": False,
    },
)
def gomoku_place(game_id: str, x: int, y: int) -> Dict[str,Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if state.get("status") == "waiting":
        return {"ok": False, "error": "game waiting for white to join, cannot place yet"}
    if state.get("status") == "finished":
        return {"ok": False, "error": f"game already finished, winner={state.get('winner')}", **_game_view_payload(state)}
    size = int(state.get("board_size") or 15)
    try:
        xi = int(x); yi = int(y)
    except Exception:
        return {"ok": False, "error": "x,y must be integers"}
    if not (0 <= xi < size and 0 <= yi < size):
        return {"ok": False, "error": f"x,y out of range 0-{size-1}"}
    players = state.get("players") or {}
    turn = state.get("turn")
    # determine my color
    my_color = None
    if players.get("black") == sid:
        my_color = "black"
    elif players.get("white") == sid:
        my_color = "white"
    else:
        # allow if sid empty (fallback) but need to infer by turn for testing
        # if sid unknown, allow if turn matches and no strict check
        if sid and sid != "unknown":
            return {"ok": False, "error": "you are not a player of this game"}
        my_color = turn
    if turn != my_color:
        return {"ok": False, "error": f"not your turn, current turn={turn}", **_game_view_payload(state)}
    board = state.get("board")
    if board[yi][xi] != 0:
        return {"ok": False, "error": f"cell ({xi},{yi}) already occupied", **_game_view_payload(state)}
    color_int = 1 if my_color=="black" else 2
    board[yi][xi] = color_int
    move_no = len(state.get("history") or []) + 1
    state["history"].append({"x": xi, "y": yi, "color": my_color, "move_no": move_no, "ts": _now_ts(), "session_id": sid})
    state["last_move"] = [xi, yi]
    # check win
    won, line = _engine.check_win(board, xi, yi, color_int)
    if won:
        state["winner"] = my_color
        state["win_line"] = line
        state["status"] = "finished"
        state["updated_at"] = _now_ts()
        save_game(state)
        view = _game_view_payload(state)
        view.update({"ok": True, "msg": f"落子({xi},{yi})获胜！{my_color} 五连珠！", "wait_for_opponent": False})
        return _with_game_event(view)
    if _engine.is_draw(board):
        state["winner"] = "draw"
        state["status"] = "finished"
        state["updated_at"] = _now_ts()
        save_game(state)
        view = _game_view_payload(state)
        view.update({"ok": True, "msg": f"落子({xi},{yi})平局，棋盘已满", "wait_for_opponent": False})
        return _with_game_event(view)
    # switch turn
    state["turn"] = "white" if turn=="black" else "black"
    state["updated_at"] = _now_ts()
    save_game(state)
    view = _game_view_payload(state)
    # host will block waiting for opponent
    view.update({
        "ok": True,
        "msg": f"已落子({xi},{yi})，等待对手落子（最长5分钟）...",
        "wait_for_opponent": True,
        "wait_reason": "place",
        "my_color": my_color,
    })
    return _begin_wait(view)

@plugin.tool(
    name="gomoku_view",
    description="View board, turn, history, winner (non-blocking).",
    effect="read",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string"},
        },
        "required": ["game_id"],
        "additionalProperties": False,
    },
)
def gomoku_view(game_id: str) -> Dict[str,Any]:
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    view = _game_view_payload(state)
    view["ok"] = True
    return view

@plugin.tool(
    name="gomoku_list",
    description="List games in lobby (non-blocking).",
    effect="read",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "waiting|playing|finished or empty for all"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "additionalProperties": False,
    },
)
def gomoku_list(status: str = "", limit: int = 20) -> Dict[str,Any]:
    try:
        lim = int(limit) if str(limit).strip() else 20
    except:
        lim = 20
    lim = max(1, min(100, lim))
    st = str(status or "").strip() or None
    items = list_games(status=st, limit=lim)
    # summarize
    summary = []
    for s in items:
        summary.append({
            "game_id": s.get("id"),
            "board_size": s.get("board_size"),
            "status": s.get("status"),
            "turn": s.get("turn"),
            "winner": s.get("winner"),
            "players": s.get("players"),
            "move_count": len(s.get("history") or []),
            "updated_at": s.get("updated_at"),
        })
    return {"ok": True, "games": summary, "count": len(summary)}

@plugin.tool(
    name="gomoku_surrender",
    description="Surrender current game (non-blocking, wakes opponent).",
    effect="workspace_write",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string"},
        },
        "required": ["game_id"],
        "additionalProperties": False,
    },
)
def gomoku_surrender(game_id: str) -> Dict[str,Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if state.get("status") == "finished":
        return {"ok": False, "error": "game already finished", **_game_view_payload(state)}
    players = state.get("players") or {}
    my_color = None
    if players.get("black")==sid:
        my_color="black"
    elif players.get("white")==sid:
        my_color="white"
    else:
        if sid and sid!="unknown":
            return {"ok": False, "error": "you are not a player"}
        my_color = state.get("turn")
    winner = "white" if my_color=="black" else "black"
    state["winner"] = winner
    state["status"] = "finished"
    state["updated_at"] = _now_ts()
    save_game(state)
    view = _game_view_payload(state)
    view.update({"ok": True, "msg": f"{my_color} 认输，{winner} 获胜", "wait_for_opponent": False})
    return _with_game_event(view)

