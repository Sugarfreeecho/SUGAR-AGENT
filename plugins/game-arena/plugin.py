"""Game Arena - Gomoku + Go (Weiqi) plugin with deferred waits."""
from __future__ import annotations
import time
import uuid
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from myagent_plugin_sdk import (
    Plugin,
    current_tool_context,
    deferred_result,
    with_host_actions,
)

plugin = Plugin()

try:
    from engine.gomoku import GomokuGame
    from engine.go import GoGame
    from storage import load_game, save_game, list_games, game_path, migrate_legacy_games
    from render import render_ascii, render_svg, render_ascii_go, render_svg_go
except ImportError:
    from .engine.gomoku import GomokuGame
    from .engine.go import GoGame
    from .storage import load_game, save_game, list_games, game_path, migrate_legacy_games
    from .render import render_ascii, render_svg, render_ascii_go, render_svg_go

_gomoku_engine = GomokuGame()
_go_engine = GoGame()
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

def _default_board_size(game_type: str = "gomoku") -> int:
    raw = current_tool_context().settings.get("default_board_size", 15)
    try:
        size = int(raw)
    except (TypeError, ValueError):
        size = 15
    if game_type == "go":
        # Go standard sizes: 9,13,19 ; default 19 if current default not in those
        if size not in (9,13,19):
            return 19
        return size
    return size if 9 <= size <= 19 else 15

def _normalize_game_type(raw: Any) -> str:
    t = str(raw or "gomoku").strip().lower()
    if t in ("go", "weiqi", "baduk", "igo"):
        return "go"
    return "gomoku"

def _is_go(state: Dict[str, Any]) -> bool:
    return str(state.get("game_type") or "gomoku").lower() == "go"

def _get_engine(game_type: str):
    return _go_engine if _normalize_game_type(game_type) == "go" else _gomoku_engine

def _board_ascii(board, win_line=None) -> str:
    return render_ascii(board, win_line)

def _go_board_hash(board: List[List[int]]) -> str:
    return "".join(str(c) for row in board for c in row)

def _game_view_payload(state: Dict[str,Any]) -> Dict[str,Any]:
    board = state.get("board") or []
    game_type = _normalize_game_type(state.get("game_type"))
    is_go = game_type == "go"
    if is_go:
        ascii_board = render_ascii_go(
            board,
            tuple(state.get("last_move")) if state.get("last_move") else None,
            tuple(state.get("ko")) if state.get("ko") else None,
            state.get("captures"),
            state.get("territory_board"),
        )
    else:
        win_line = state.get("win_line")
        ascii_board = _board_ascii(board, win_line)
    payload = {
        "game_id": state.get("id"),
        "game_type": game_type,
        "board_size": state.get("board_size"),
        "board_ascii": ascii_board,
        "turn": state.get("turn"),
        "status": state.get("status"),
        "winner": state.get("winner"),
        "last_move": state.get("last_move"),
        "move_count": len(state.get("history") or []),
        "history": state.get("history"),
    }
    if not is_go and state.get("win_line"):
        payload["win_line"] = state.get("win_line")
    if is_go:
        payload["captures"] = state.get("captures") or {"black":0,"white":0}
        payload["ko"] = state.get("ko")
        payload["consecutive_passes"] = state.get("consecutive_passes", 0)
        payload["komi"] = state.get("komi", 6.5)
        if state.get("score"):
            payload["score"] = state.get("score")
        if state.get("territory_board"):
            payload["territory_board"] = state.get("territory_board")
    else:
        if state.get("win_line"):
            payload["win_line"] = state.get("win_line")
    return payload


def _game_event_data(view: Dict[str, Any]) -> Dict[str, Any]:
    """Keep durable UI events compact and free of board/history token bulk."""
    data = {
        key: view.get(key)
        for key in (
            "game_id",
            "game_type",
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
                if _is_go(state) and state.get("score"):
                    sc = state.get("score")
                    initial["msg"] += f" {sc.get('result','')} (B:{sc.get('black_score')} W:{sc.get('white_score')})"
            else:
                last_move = state.get("last_move")
                # For Go, last move could be pass
                hist = state.get("history") or []
                last_entry = hist[-1] if hist else None
                if last_entry and last_entry.get("pass"):
                    initial["msg"] = f"对手已虚手(pass)，轮到你落子。当前回合: {state.get('turn')}"
                elif last_move:
                    initial["msg"] = (
                        f"对手已落子({last_move[0]},{last_move[1]})，轮到你落子。当前回合: {state.get('turn')}"
                    )
                else:
                    initial["msg"] = f"对手已落子，轮到你落子。当前回合: {state.get('turn')}"
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
            + " [等待对手超时(5分钟)，可用 gomoku_view/go_view 查看当前状态]"
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
        game_type = _query(request, "game_type").strip() or None
        if game_type:
            game_type = _normalize_game_type(game_type)
        try:
            limit = max(1, min(100, int(_query(request, "limit", "20"))))
        except (TypeError, ValueError):
            limit = 20
        summary = []
        for state in list_games(status=status, limit=limit):
            gt = _normalize_game_type(state.get("game_type"))
            if game_type and gt != game_type:
                continue
            summary.append({
                "game_id": state.get("id"),
                "game_type": gt,
                "board_size": state.get("board_size"),
                "status": state.get("status"),
                "turn": state.get("turn"),
                "winner": state.get("winner"),
                "players": state.get("players"),
                "move_count": len(state.get("history") or []),
                "updated_at": state.get("updated_at"),
                "created_at": state.get("created_at"),
                "captures": state.get("captures") if gt=="go" else None,
                "komi": state.get("komi") if gt=="go" else None,
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
        gt = _normalize_game_type(state.get("game_type"))
        if gt == "go":
            state["board_ascii"] = render_ascii_go(
                state.get("board") or [],
                tuple(state.get("last_move")) if state.get("last_move") else None,
                tuple(state.get("ko")) if state.get("ko") else None,
                state.get("captures"),
                state.get("territory_board"),
            )
            state["board_svg"] = render_svg_go(
                state.get("board") or [],
                tuple(state.get("last_move")) if state.get("last_move") else None,
                tuple(state.get("ko")) if state.get("ko") else None,
                state.get("territory_board"),
                state.get("captures"),
            )
        else:
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
        gt = _normalize_game_type(state.get("game_type"))
        try:
            move_no = max(0, min(len(history), int(_query(request, "move_no", "0"))))
        except (TypeError, ValueError):
            move_no = 0
        if gt == "go":
            board = _go_engine.create_board(size)
            captures = {"black": 0, "white": 0}
            ko = None
            history_hashes: List[str] = []
            # Replay up to move_no, recalculating captures/ko by replaying moves
            for idx, move in enumerate(history[:move_no]):
                if move.get("pass"):
                    continue
                try:
                    x = int(move["x"]); y = int(move["y"])
                    color = 1 if move.get("color") == "black" else 2
                    # Use engine play_move logic but simplified: just place and handle captures
                    # We need to simulate with ko handling
                    # For replay, we use the same logic as play_move but without validation of ko history beyond immediate
                    # Instead we just apply captures via engine helpers
                    board[y][x] = color
                    # Find captured groups
                    captured = _go_engine._captured_groups(board, x, y, color)
                    for grp in captured:
                        for gx, gy in grp:
                            board[gy][gx] = 0
                            captures["black" if color==1 else "white"] += 1
                    # Determine ko for next move (if single capture)
                    if len(captured)==1 and len(captured[0])==1:
                        own_group = _go_engine._group(board, x, y)
                        if len(own_group)==1 and len(_go_engine._liberties(board, own_group))==1:
                            ko = next(iter(captured[0]))
                        else:
                            ko = None
                    else:
                        ko = None
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
            last = history[move_no - 1] if move_no else None
            last_move = [last.get("x"), last.get("y")] if last and not last.get("pass") else None
            is_live_edge = move_no == len(history)
            # For live edge, show actual ko/captures/score; for replay, show replay state
            if is_live_edge:
                ko = state.get("ko")
                captures = state.get("captures") or captures
                territory_board = state.get("territory_board")
                score = state.get("score")
            else:
                territory_board = None
                score = None
            replay_status = state.get("status") if is_live_edge else (
                "playing" if (state.get("players") or {}).get("white") else "waiting"
            )
            replay_winner = state.get("winner") if is_live_edge else None
            replay_turn = state.get("turn") if is_live_edge else (
                "black" if move_no % 2 == 0 else "white"
            )
            # If last move was pass, turn already handled
            return _http_json({
                "ok": True,
                "game_id": game_id,
                "game_type": gt,
                "move_no": move_no,
                "total": len(history),
                "status": replay_status,
                "turn": replay_turn,
                "winner": replay_winner,
                "board": board,
                "board_ascii": render_ascii_go(board, tuple(last_move) if last_move else None, tuple(ko) if ko else None, captures, territory_board),
                "board_svg": render_svg_go(board, tuple(last_move) if last_move else None, tuple(ko) if ko else None, territory_board, captures),
                "last_move": last_move,
                "history": history,
                "captures": captures,
                "ko": ko,
                "score": score,
            })
        else:
            board = _gomoku_engine.create_board(size)
            for move in history[:move_no]:
                try:
                    board[int(move["y"])][int(move["x"])] = (
                        1 if move.get("color") == "black" else 2
                    )
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
            last = history[move_no - 1] if move_no else None
            last_move = [last.get("x"), last.get("y")] if last else None
            is_live_edge = move_no == len(history)
            win_line = state.get("win_line") if is_live_edge else None
            replay_status = state.get("status") if is_live_edge else (
                "playing" if (state.get("players") or {}).get("white") else "waiting"
            )
            replay_winner = state.get("winner") if is_live_edge else None
            replay_turn = state.get("turn") if is_live_edge else (
                "black" if move_no % 2 == 0 else "white"
            )
            return _http_json({
                "ok": True,
                "game_id": game_id,
                "game_type": gt,
                "move_no": move_no,
                "total": len(history),
                "status": replay_status,
                "turn": replay_turn,
                "winner": replay_winner,
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
        game_type = _normalize_game_type(data.get("game_type") or data.get("gameType") or "gomoku")
        try:
            board_size = int(data.get("board_size") or _default_board_size(game_type))
        except (TypeError, ValueError):
            board_size = _default_board_size(game_type)
        if board_size < 9 or board_size > 19:
            board_size = _default_board_size(game_type)
        # Go board size should be 9/13/19 but allow 9-19 for flexibility
        if game_type == "go" and board_size not in (9,13,19):
            # snap to nearest standard? keep as is but warn via default
            pass
        try:
            komi = float(data.get("komi", 6.5))
        except (TypeError, ValueError):
            komi = 6.5
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
        if game_type == "go":
            prompt_a = f"""你正在参与围棋对战 Game Arena (Go/Weiqi)
游戏ID: {game_id}  棋盘: {board_size}x{board_size}  贴目: {komi}  你执黑(●) 先行
请立即调用 go_create(game_id="{game_id}", board_size={board_size}, komi={komi})。
宿主会通过延迟结果等待白方加入；返回后继续用 go_place 落子(x,y) 或 go_pass 虚手，目标围地获胜。
规则：提子、禁自杀、打劫(ko)需先在他处落子、连续两次虚手结束并自动计分。"""
            prompt_b = f"""你正在参与围棋对战 Game Arena (Go/Weiqi)
游戏ID: {game_id}  棋盘: {board_size}x{board_size}  贴目: {komi}  你执白(○)
请立即调用 go_join(game_id="{game_id}")。
宿主会通过延迟结果等待黑方落子；返回后继续用 go_place 回应或 go_pass 虚手，目标围地获胜。
规则：提子、禁自杀、打劫(ko)需先在他处落子、连续两次虚手结束并自动计分。"""
        else:
            prompt_a = f"""你正在参与五子棋对战 Game Arena
游戏ID: {game_id}  棋盘: {board_size}x{board_size}  你执黑(●) 先行
请立即调用 gomoku_create(game_id="{game_id}", board_size={board_size})。
宿主会通过延迟结果等待白方加入；返回后继续用 gomoku_place 落子，目标五子连珠获胜。"""
            prompt_b = f"""你正在参与五子棋对战 Game Arena
游戏ID: {game_id}  棋盘: {board_size}x{board_size}  你执白(○)
请立即调用 gomoku_join(game_id="{game_id}")。
宿主会通过延迟结果等待黑方落子；返回后继续用 gomoku_place 回应，目标五子连珠获胜。"""
        return {
            "status": 202,
            "json": {
                "ok": True,
                "game_id": game_id,
                "game_type": game_type,
                "board_size": board_size,
                "komi": komi if game_type=="go" else None,
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

# ── Gomoku tools (original, kept for compatibility) ──

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
    return _gomoku_create_impl(game_id, board_size)

def _gomoku_create_impl(game_id: str = "", board_size: int | None = None) -> Dict[str,Any]:
    sid = _current_session_id()
    size = int(board_size) if board_size is not None and str(board_size).strip() else _default_board_size("gomoku")
    if size < 9 or size > 19:
        return {"ok": False, "error": "board_size must be 9-19"}
    gid = str(game_id or "").strip() or _gen_id()
    gid = "".join(c for c in gid if c.isalnum() or c in "-_") or _gen_id()
    if load_game(gid) is not None:
        return {"ok": False, "error": f"game_id {gid} already exists"}
    board = _gomoku_engine.create_board(size)
    now = _now_ts()
    state = {
        "id": gid,
        "game_type": "gomoku",
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
        "msg": f"房间 {gid} 创建成功，你执黑(●) {size}x{size} 五子棋，等待白方加入（最长5分钟）...",
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
    return _gomoku_join_impl(game_id)

def _gomoku_join_impl(game_id: str) -> Dict[str,Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if _normalize_game_type(state.get("game_type")) != "gomoku":
        return {"ok": False, "error": f"game {gid} is not a gomoku game (type={state.get('game_type')})"}
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
        "msg": f"已加入房间 {gid}，你执白(○) {state.get('board_size')}x{state.get('board_size')} 五子棋，等待黑方落子（最长5分钟）...",
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
    if _normalize_game_type(state.get("game_type")) != "gomoku":
        return {"ok": False, "error": f"game {gid} is not gomoku, use go_place for Go games"}
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
    my_color = None
    if players.get("black") == sid:
        my_color = "black"
    elif players.get("white") == sid:
        my_color = "white"
    else:
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
    won, line = _gomoku_engine.check_win(board, xi, yi, color_int)
    if won:
        state["winner"] = my_color
        state["win_line"] = line
        state["status"] = "finished"
        state["updated_at"] = _now_ts()
        save_game(state)
        view = _game_view_payload(state)
        view.update({"ok": True, "msg": f"落子({xi},{yi})获胜！{my_color} 五连珠！", "wait_for_opponent": False})
        return _with_game_event(view)
    if _gomoku_engine.is_draw(board):
        state["winner"] = "draw"
        state["status"] = "finished"
        state["updated_at"] = _now_ts()
        save_game(state)
        view = _game_view_payload(state)
        view.update({"ok": True, "msg": f"落子({xi},{yi})平局，棋盘已满", "wait_for_opponent": False})
        return _with_game_event(view)
    state["turn"] = "white" if turn=="black" else "black"
    state["updated_at"] = _now_ts()
    save_game(state)
    view = _game_view_payload(state)
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
            "game_type": {"type": "string", "description": "filter by game_type: gomoku/go"},
        },
        "additionalProperties": False,
    },
)
def gomoku_list(status: str = "", limit: int = 20, game_type: str = "") -> Dict[str,Any]:
    try:
        lim = int(limit) if str(limit).strip() else 20
    except:
        lim = 20
    lim = max(1, min(100, lim))
    st = str(status or "").strip() or None
    gt_filter = _normalize_game_type(game_type) if str(game_type or "").strip() else None
    items = list_games(status=st, limit=100)
    summary = []
    for s in items:
        gt = _normalize_game_type(s.get("game_type"))
        if gt_filter and gt != gt_filter:
            continue
        summary.append({
            "game_id": s.get("id"),
            "game_type": gt,
            "board_size": s.get("board_size"),
            "status": s.get("status"),
            "turn": s.get("turn"),
            "winner": s.get("winner"),
            "players": s.get("players"),
            "move_count": len(s.get("history") or []),
            "updated_at": s.get("updated_at"),
        })
        if len(summary) >= lim:
            break
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
    # For Go, compute final score even on surrender? Keep winner as opponent
    if _is_go(state):
        try:
            state["score"] = _go_engine.score(state.get("board") or [], state.get("captures") or {}, float(state.get("komi",6.5)))
        except Exception:
            pass
    save_game(state)
    view = _game_view_payload(state)
    view.update({"ok": True, "msg": f"{my_color} 认输，{winner} 获胜", "wait_for_opponent": False})
    return _with_game_event(view)

# ── Go (Weiqi) tools ──

@plugin.tool(
    name="go_create",
    description="Create a Go (Weiqi/Baduk) game room (black first). Board 9/13/19, komi 6.5 default. Blocks until white joins (5min).",
    effect="workspace_write",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string", "description": "Optional custom game id"},
            "board_size": {"type": "integer", "description": "Board size 9/13/19 (9-19 allowed)", "minimum": 9, "maximum": 19},
            "komi": {"type": "number", "description": "Komi for white, default 6.5"},
        },
        "additionalProperties": False,
    },
)
def go_create(game_id: str = "", board_size: int | None = None, komi: float | None = None) -> Dict[str, Any]:
    sid = _current_session_id()
    size = int(board_size) if board_size is not None and str(board_size).strip() else _default_board_size("go")
    if size < 9 or size > 19:
        return {"ok": False, "error": "board_size must be 9-19 (standard 9/13/19)"}
    try:
        k = float(komi) if komi is not None and str(komi).strip() else 6.5
    except (TypeError, ValueError):
        k = 6.5
    gid = str(game_id or "").strip() or _gen_id()
    gid = "".join(c for c in gid if c.isalnum() or c in "-_") or _gen_id()
    if load_game(gid) is not None:
        return {"ok": False, "error": f"game_id {gid} already exists"}
    board = _go_engine.create_board(size)
    now = _now_ts()
    state = {
        "id": gid,
        "game_type": "go",
        "board_size": size,
        "board": board,
        "players": {"black": sid or "unknown", "white": ""},
        "player_names": {"black": sid[:8] if sid else "black", "white": ""},
        "turn": "black",
        "status": "waiting",
        "winner": None,
        "history": [],
        "last_move": None,
        "captures": {"black": 0, "white": 0},
        "ko": None,
        "consecutive_passes": 0,
        "komi": k,
        "score": None,
        "territory_board": None,
        "board_hashes": [_go_board_hash(board)],
        "created_at": now,
        "updated_at": now,
    }
    save_game(state)
    view = _game_view_payload(state)
    view.update({
        "ok": True,
        "color": "black",
        "msg": f"围棋房间 {gid} 创建成功，你执黑(●) {size}x{size} 贴目{k}，等待白方加入（最长5分钟）...",
        "wait_for_opponent": True,
        "wait_reason": "join",
    })
    return _begin_wait(view)


@plugin.tool(
    name="go_join",
    description="Join a waiting Go game as white. Blocks until black moves (5min).",
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
def go_join(game_id: str) -> Dict[str, Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if _normalize_game_type(state.get("game_type")) != "go":
        return {"ok": False, "error": f"game {gid} is not a Go game (type={state.get('game_type')})"}
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
        "msg": f"已加入围棋房间 {gid}，你执白(○) {state.get('board_size')}x{state.get('board_size')} 贴目{state.get('komi',6.5)}，等待黑方落子（最长5分钟）...",
        "wait_for_opponent": True,
        "wait_reason": "place",
    })
    return _begin_wait(view)


@plugin.tool(
    name="go_place",
    description="Place a Go stone at (x,y). Handles capture, ko, suicide. Blocks until opponent moves if not finished (5min).",
    effect="workspace_write",
    input_schema={
        "type": "object",
        "properties": {
            "game_id": {"type": "string"},
            "x": {"type": "integer", "minimum": 0, "maximum": 18},
            "y": {"type": "integer", "minimum": 0, "maximum": 18},
        },
        "required": ["game_id", "x", "y"],
        "additionalProperties": False,
    },
)
def go_place(game_id: str, x: int, y: int) -> Dict[str, Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if _normalize_game_type(state.get("game_type")) != "go":
        return {"ok": False, "error": f"game {gid} is not Go, use gomoku_place for Gomoku"}
    if state.get("status") == "waiting":
        return {"ok": False, "error": "game waiting for white to join, cannot place yet"}
    if state.get("status") == "finished":
        return {"ok": False, "error": f"game already finished, winner={state.get('winner')}", **_game_view_payload(state)}
    size = int(state.get("board_size") or 19)
    try:
        xi = int(x); yi = int(y)
    except Exception:
        return {"ok": False, "error": "x,y must be integers"}
    if not (0 <= xi < size and 0 <= yi < size):
        return {"ok": False, "error": f"x,y out of range 0-{size-1}"}
    players = state.get("players") or {}
    turn = state.get("turn")
    my_color = None
    if players.get("black") == sid:
        my_color = "black"
    elif players.get("white") == sid:
        my_color = "white"
    else:
        if sid and sid != "unknown":
            return {"ok": False, "error": "you are not a player of this game"}
        my_color = turn
    if turn != my_color:
        return {"ok": False, "error": f"not your turn, current turn={turn}", **_game_view_payload(state)}
    board = state.get("board")
    captures = state.get("captures") or {"black":0,"white":0}
    ko = tuple(state.get("ko")) if state.get("ko") else None
    history_hashes = state.get("board_hashes") or []
    color_int = 1 if my_color == "black" else 2
    ok, err, new_ko, cap_count = _go_engine.play_move(board, xi, yi, color_int, captures, ko, history_hashes)
    if not ok:
        return {"ok": False, "error": err, **_game_view_payload(state)}
    # Update state
    move_no = len(state.get("history") or []) + 1
    state["history"].append({"x": xi, "y": yi, "color": my_color, "move_no": move_no, "ts": _now_ts(), "session_id": sid, "captured": cap_count})
    state["last_move"] = [xi, yi]
    state["captures"] = captures
    state["ko"] = list(new_ko) if new_ko else None
    state["consecutive_passes"] = 0
    state["board"] = board
    # Update hashes for ko/superko
    h = _go_board_hash(board)
    history_hashes.append(h)
    # Keep last 50 hashes
    if len(history_hashes) > 50:
        history_hashes = history_hashes[-50:]
    state["board_hashes"] = history_hashes
    state["turn"] = "white" if turn == "black" else "black"
    state["updated_at"] = _now_ts()
    save_game(state)
    view = _game_view_payload(state)
    view.update({
        "ok": True,
        "msg": f"已落子({xi},{yi})" + (f" 提子{cap_count}" if cap_count else "") + f"，等待对手落子（最长5分钟）... 提子 B:{captures.get('black',0)} W:{captures.get('white',0)}",
        "wait_for_opponent": True,
        "wait_reason": "place",
        "my_color": my_color,
        "captured": cap_count,
        "ko": state["ko"],
    })
    return _begin_wait(view)


@plugin.tool(
    name="go_pass",
    description="Pass your turn in Go. Two consecutive passes end the game and trigger scoring.",
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
def go_pass(game_id: str) -> Dict[str, Any]:
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if _normalize_game_type(state.get("game_type")) != "go":
        return {"ok": False, "error": f"game {gid} is not Go"}
    if state.get("status") == "waiting":
        return {"ok": False, "error": "game waiting for white to join"}
    if state.get("status") == "finished":
        return {"ok": False, "error": f"game already finished, winner={state.get('winner')}", **_game_view_payload(state)}
    players = state.get("players") or {}
    turn = state.get("turn")
    my_color = None
    if players.get("black") == sid:
        my_color = "black"
    elif players.get("white") == sid:
        my_color = "white"
    else:
        if sid and sid != "unknown":
            return {"ok": False, "error": "you are not a player"}
        my_color = turn
    if turn != my_color:
        return {"ok": False, "error": f"not your turn, current turn={turn}", **_game_view_payload(state)}
    move_no = len(state.get("history") or []) + 1
    state["history"].append({"x": -1, "y": -1, "color": my_color, "move_no": move_no, "ts": _now_ts(), "session_id": sid, "pass": True})
    state["consecutive_passes"] = int(state.get("consecutive_passes") or 0) + 1
    state["ko"] = None  # pass clears ko
    state["last_move"] = None
    if state["consecutive_passes"] >= 2:
        # Game ends, scoring
        try:
            score = _go_engine.score(state.get("board") or [], state.get("captures") or {}, float(state.get("komi", 6.5)))
        except Exception as e:
            score = {"winner": "draw", "black_score": 0, "white_score": 0, "result": f"score error: {e}"}
        state["score"] = score
        state["territory_board"] = score.get("territory_board")
        state["winner"] = score.get("winner")
        state["status"] = "finished"
        state["updated_at"] = _now_ts()
        save_game(state)
        view = _game_view_payload(state)
        view.update({
            "ok": True,
            "msg": f"{my_color} 虚手，双方连续虚手，游戏结束 {score.get('result')} B:{score.get('black_score')} W:{score.get('white_score')} (贴目{score.get('komi')}) 提子 B:{score.get('black_captures')} W:{score.get('white_captures')}",
            "wait_for_opponent": False,
            "score": score,
        })
        return _with_game_event(view)
    else:
        state["turn"] = "white" if turn == "black" else "black"
        state["updated_at"] = _now_ts()
        save_game(state)
        view = _game_view_payload(state)
        view.update({
            "ok": True,
            "msg": f"{my_color} 虚手(pass)，等待对手落子（最长5分钟）... 已连续虚手{state['consecutive_passes']}次，再虚手一次将结束计分",
            "wait_for_opponent": True,
            "wait_reason": "place",
            "my_color": my_color,
        })
        return _begin_wait(view)


@plugin.tool(
    name="go_view",
    description="View Go board, turn, captures, ko, history, winner (non-blocking).",
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
def go_view(game_id: str) -> Dict[str, Any]:
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if _normalize_game_type(state.get("game_type")) != "go":
        return {"ok": False, "error": f"game {gid} is not Go, use gomoku_view"}
    view = _game_view_payload(state)
    view["ok"] = True
    return view


@plugin.tool(
    name="go_list",
    description="List Go games in lobby (non-blocking).",
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
def go_list(status: str = "", limit: int = 20) -> Dict[str, Any]:
    try:
        lim = int(limit) if str(limit).strip() else 20
    except:
        lim = 20
    lim = max(1, min(100, lim))
    st = str(status or "").strip() or None
    items = list_games(status=st, limit=100)
    summary = []
    for s in items:
        if _normalize_game_type(s.get("game_type")) != "go":
            continue
        summary.append({
            "game_id": s.get("id"),
            "game_type": "go",
            "board_size": s.get("board_size"),
            "status": s.get("status"),
            "turn": s.get("turn"),
            "winner": s.get("winner"),
            "players": s.get("players"),
            "move_count": len(s.get("history") or []),
            "updated_at": s.get("updated_at"),
            "captures": s.get("captures"),
            "komi": s.get("komi"),
        })
        if len(summary) >= lim:
            break
    return {"ok": True, "games": summary, "count": len(summary)}


@plugin.tool(
    name="go_surrender",
    description="Surrender current Go game (non-blocking, wakes opponent).",
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
def go_surrender(game_id: str) -> Dict[str, Any]:
    # Reuse gomoku_surrender logic but ensure Go type check
    sid = _current_session_id()
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    if _normalize_game_type(state.get("game_type")) != "go":
        return {"ok": False, "error": f"game {gid} is not Go"}
    if state.get("status") == "finished":
        return {"ok": False, "error": "game already finished", **_game_view_payload(state)}
    players = state.get("players") or {}
    my_color = None
    if players.get("black") == sid:
        my_color = "black"
    elif players.get("white") == sid:
        my_color = "white"
    else:
        if sid and sid != "unknown":
            return {"ok": False, "error": "you are not a player"}
        my_color = state.get("turn")
    winner = "white" if my_color == "black" else "black"
    state["winner"] = winner
    state["status"] = "finished"
    state["updated_at"] = _now_ts()
    try:
        state["score"] = _go_engine.score(state.get("board") or [], state.get("captures") or {}, float(state.get("komi", 6.5)))
        state["territory_board"] = state["score"].get("territory_board")
    except Exception:
        pass
    save_game(state)
    view = _game_view_payload(state)
    view.update({"ok": True, "msg": f"{my_color} 认输，{winner} 获胜", "wait_for_opponent": False})
    return _with_game_event(view)

# ── Unified view/list for frontend convenience ──

@plugin.tool(
    name="game_view",
    description="View any Game Arena game (gomoku or go) by id (non-blocking).",
    effect="read",
    input_schema={
        "type": "object",
        "properties": {"game_id": {"type": "string"}},
        "required": ["game_id"],
        "additionalProperties": False,
    },
)
def game_view(game_id: str) -> Dict[str, Any]:
    gid = str(game_id).strip()
    state = load_game(gid)
    if not state:
        return {"ok": False, "error": f"game {gid} not found"}
    view = _game_view_payload(state)
    view["ok"] = True
    return view

@plugin.tool(
    name="game_list",
    description="List all Game Arena games (both gomoku and go).",
    effect="read",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "waiting|playing|finished or empty"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "game_type": {"type": "string", "description": "gomoku/go or empty for all"},
        },
        "additionalProperties": False,
    },
)
def game_list(status: str = "", limit: int = 20, game_type: str = "") -> Dict[str, Any]:
    try:
        lim = int(limit) if str(limit).strip() else 20
    except:
        lim = 20
    lim = max(1, min(100, lim))
    st = str(status or "").strip() or None
    gt_filter = _normalize_game_type(game_type) if str(game_type or "").strip() else None
    items = list_games(status=st, limit=100)
    summary = []
    for s in items:
        gt = _normalize_game_type(s.get("game_type"))
        if gt_filter and gt != gt_filter:
            continue
        summary.append({
            "game_id": s.get("id"),
            "game_type": gt,
            "board_size": s.get("board_size"),
            "status": s.get("status"),
            "turn": s.get("turn"),
            "winner": s.get("winner"),
            "players": s.get("players"),
            "move_count": len(s.get("history") or []),
            "updated_at": s.get("updated_at"),
        })
        if len(summary) >= lim:
            break
    return {"ok": True, "games": summary, "count": len(summary)}
