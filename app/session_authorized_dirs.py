from __future__ import annotations
import os
from pathlib import Path
from typing import List

def _get_work_dir() -> Path:
    try:
        from agent_harness import WORK_DIR
        return Path(WORK_DIR).resolve()
    except Exception:
        return Path.cwd().resolve()

def _normalize_dir(path_str: str) -> str:
    p = Path(str(path_str or "").strip()).expanduser()
    try:
        rp = p.resolve()
    except Exception:
        rp = Path(os.path.abspath(str(p)))
    s = str(rp)
    if os.name == "nt":
        s = os.path.normcase(s)
    s = s.rstrip("/\\")
    if not s:
        s = str(rp.anchor) if rp.anchor else "/"
    return s

def _is_within(path: Path, root: Path) -> bool:
    try:
        return path == root or root in path.parents
    except Exception:
        try:
            return str(path).lower().startswith(str(root).lower() + os.sep) if os.name=="nt" else str(path).startswith(str(root)+os.sep)
        except Exception:
            return False

def _is_path_authorized(canonical: Path, authorized: List[Path]) -> bool:
    try:
        cp = canonical.resolve()
    except Exception:
        cp = canonical
    for auth in authorized:
        try:
            ap = Path(auth).resolve() if isinstance(auth, (str, Path)) else Path(str(auth)).resolve()
        except Exception:
            continue
        if _is_within(cp, ap):
            return True
    return False

def get_authorized_dirs_for_session(session_id: str, workspace: Path | None = None) -> List[Path]:
    ws = workspace or _get_work_dir()
    sid = str(session_id or "").strip()
    if not sid:
        return [ws.resolve()]
    try:
        from agent_harness import session_manager
        meta = session_manager._load_metadata(sid)
        if isinstance(meta, dict):
            raw_list = meta.get("authorized_dirs")
            if isinstance(raw_list, list) and raw_list:
                out: List[Path] = []
                seen = set()
                for item in raw_list:
                    s = str(item or "").strip()
                    if not s:
                        continue
                    try:
                        p = Path(s).resolve()
                    except Exception:
                        p = Path(s)
                    norm = str(p).lower() if os.name=="nt" else str(p)
                    if norm in seen:
                        continue
                    seen.add(norm)
                    out.append(p)
                if out:
                    return out
    except Exception:
        pass
    return [ws.resolve()]

def is_path_authorized_for_session(canonical: Path, session_id: str, workspace: Path | None = None) -> bool:
    auth = get_authorized_dirs_for_session(session_id, workspace)
    return _is_path_authorized(canonical, auth)

def compute_required_authorization_dirs(paths: List[Path], session_id: str, workspace: Path | None = None) -> List[Path]:
    ws = workspace or _get_work_dir()
    auth = get_authorized_dirs_for_session(session_id, ws)
    required: List[Path] = []
    seen = set()
    for p in paths or []:
        try:
            cp = Path(p).resolve() if isinstance(p, Path) else Path(str(p)).resolve()
        except Exception:
            cp = Path(str(p))
        if _is_path_authorized(cp, auth):
            continue
        req: Path
        try:
            if cp.is_file():
                req = cp.parent.resolve()
            elif cp.is_dir():
                req = cp.resolve()
            else:
                if cp.suffix:
                    req = cp.parent.resolve()
                else:
                    req = cp.resolve()
        except Exception:
            req = cp.parent if cp.suffix else cp
        try:
            req = req.resolve()
        except Exception:
            pass
        norm = str(req).lower() if os.name=="nt" else str(req)
        if norm in seen:
            continue
        seen.add(norm)
        required.append(req)
    if len(required) > 1:
        pruned: List[Path] = []
        for cand in sorted(required, key=lambda pp: len(str(pp))):
            if any(_is_within(cand, other) and cand != other for other in pruned):
                continue
            if any(_is_within(cand, p) for p in pruned):
                continue
            pruned.append(cand)
        required = pruned
    return required

def add_authorized_dir(session_id: str, dir_path: str | Path) -> List[Path]:
    sid = str(session_id or "").strip()
    if not sid:
        return []
    try:
        raw = Path(str(dir_path)).resolve()
    except Exception:
        raw = Path(str(dir_path))
    norm_str = _normalize_dir(str(raw))
    try:
        from agent_harness import session_manager
        with session_manager._session_metadata_lock(sid):
            meta = session_manager._load_metadata_unlocked(sid)
            if not isinstance(meta, dict):
                meta = {}
            existing = meta.get("authorized_dirs")
            if not isinstance(existing, list):
                ws = _get_work_dir()
                existing = [str(ws.resolve())]
            existing_normed: List[str] = []
            seen = set()
            for item in existing:
                s = _normalize_dir(str(item))
                low = s.lower() if os.name=="nt" else s
                if low in seen:
                    continue
                seen.add(low)
                existing_normed.append(s)
            low_new = norm_str.lower() if os.name=="nt" else norm_str
            if low_new not in seen:
                existing_normed.append(norm_str)
                seen.add(low_new)
            path_objs = [Path(p) for p in existing_normed]
            sorted_pairs = sorted(zip(existing_normed, path_objs), key=lambda x: len(x[0]))
            pruned: List[str] = []
            pruned_paths: List[Path] = []
            for s, p in sorted_pairs:
                covered = False
                for pp in pruned_paths:
                    if _is_within(p, pp):
                        covered = True
                        break
                if covered:
                    continue
                pruned.append(s)
                pruned_paths.append(p)
            meta["authorized_dirs"] = pruned
            meta["updated_at"] = __import__("datetime").datetime.now().isoformat()
            session_manager._save_metadata_unlocked(sid, meta)
            return [Path(p) for p in pruned]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("add_authorized_dir failed %s: %s", sid, e)
        return get_authorized_dirs_for_session(sid)
    return get_authorized_dirs_for_session(sid)

def ensure_session_authorized_dirs(session_id: str) -> List[Path]:
    sid = str(session_id or "").strip()
    if not sid:
        return []
    try:
        from agent_harness import session_manager
        with session_manager._session_metadata_lock(sid):
            meta = session_manager._load_metadata_unlocked(sid)
            if not isinstance(meta, dict):
                meta = {}
            if not isinstance(meta.get("authorized_dirs"), list) or not meta.get("authorized_dirs"):
                ws = _get_work_dir()
                meta["authorized_dirs"] = [str(ws.resolve())]
                meta["updated_at"] = __import__("datetime").datetime.now().isoformat()
                session_manager._save_metadata_unlocked(sid, meta)
                return [ws.resolve()]
            return [Path(p) for p in meta["authorized_dirs"]]
    except Exception:
        return get_authorized_dirs_for_session(sid)
