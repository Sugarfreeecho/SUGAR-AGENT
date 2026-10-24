"""asr.py —— 本地转写（没字幕的视频用 Whisper 转出文字）。

对应上游 `lib/asr.py`，但形态变了：上游是独立 venv 的边车脚本（`yt-dlp` 下音频 +
命令行跑），这里是**宿主进程内的模块** —— 因为 `faster-whisper` 就装在宿主那套
Python 里，再起一个子进程只会多一层冷启动。

四个关键点（都是踩出来的）：
  ① **不硬塞镜像地址**。上游在国内必须设 `HF_ENDPOINT=hf-mirror.com`，但本机实测
     huggingface.co 直连 200、而 hf-mirror 对 `resolve/main/...` 回 308 ——
     huggingface_hub 0.36 拿到 308 直接抛 `FileMetadataError`（"似乎不在 huggingface.co"）。
     所以这里**不覆盖** HF_ENDPOINT：用户自己设了就用用户的，没设就走官方源。
     国内机器确实需要镜像的话，在宿主环境里自己配 `HF_ENDPOINT`。
  ② **不用 yt-dlp**：直接问 `bilibili_api` 要 DASH 音频流地址再自己下。少一个依赖，
     也少一处"下到 %TEMP% 被沙箱拒掉"的坑。
  ③ **CPU 上的活放线程里**：`WhisperModel.transcribe` 是同步阻塞的，直接在事件循环里
     跑会把整个宿主的 HTTP 服务卡死几十秒。
  ④ **同一条时间只转一条**：两路并发各跑一半，比串行还慢，还把 CPU 占满。
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import subprocess
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

# ⭐ 必须在 import faster_whisper 之前设好（它 import 时就会读这些）。
#    只关 Xet 存储：新版默认走 Xet，部分网络/镜像不代理它，会 401。
#    HF_ENDPOINT 故意不设 —— 理由见模块开头 ①。
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 模型加载一次要好几秒、占几百 MB —— 缓存住，别每条视频都重来。
_models: dict[str, Any] = {}
_model_lock = threading.Lock()
# 进程内串行化转写（不是"每次调用一个锁"，那样等于没锁）
_run_lock = threading.Lock()

DEFAULT_MODEL = "small"
MAX_MINUTES = 20


@asynccontextmanager
async def _lock():
    """Serialize all plugin loops without blocking them or binding to one loop."""
    while not _run_lock.acquire(blocking=False):
        await asyncio.sleep(0.05)
    try:
        yield
    finally:
        _run_lock.release()


FFMPEG_HINT = "torch"


def ffmpeg_path() -> str:
    """ffmpeg 可执行文件。优先用宿主自带的那份，其次 PATH。

    ⭐ 为什么要它：宿主语音输入收的是**16kHz 单声道 PCM WAV、≤120 秒**，
       B站 给的是 m4s（AAC）。不转码 + 不切片，那套接口收不了长视频。
    """
    candidates = [
        os.environ.get("BILI_FFMPEG") or "",
        str(Path(__file__).resolve().parents[2] / "tools" / "ffmpeg-8.1-essentials_build" / "bin" / "ffmpeg.exe"),
        str(Path(__file__).resolve().parents[2] / "tools" / "ffmpeg-8.1-essentials_build" / "bin" / "ffmpeg"),
    ]
    for item in candidates:
        if item and Path(item).is_file():
            return item
    found = shutil.which("ffmpeg")
    return found or ""


def ready(engine: str = "local") -> dict:
    """这套东西现在能不能用。给 /status 和提示词用。

    ⚠️ 只用 `find_spec` 查在不在，**真的 import** 要 10 秒 —— 这个函数会被
    /status 每 15 秒调一次，也会在拼提示词时调，import 一次能把 HTTP 线程卡住。
    """
    if str(engine or "").lower() == "host":
        # 走宿主语音输入那条路：只要 ffmpeg 在就行（模型/服务由语音输入插件负责）
        if not ffmpeg_path():
            return {"ready": False, "reason": "找不到 ffmpeg（tools/ffmpeg-8.1-essentials_build 或 PATH）"}
        return {"ready": True, "reason": ""}
    for module, hint in (("faster_whisper", "pip install faster-whisper"), ("av", "pip install av")):
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            return {"ready": False, "reason": f"缺少 {module}（{hint}）"}
    return {"ready": True, "reason": ""}


def tmp_dir(data_dir: Path) -> Path:
    path = Path(data_dir) / "tmp" / "asr"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── 取音频 ──────────────────────────────────────────────────────────────

def _pick_audio(download: dict) -> tuple[str, int]:
    """从 get_download_url 的返回里挑一条音频流 → (候选地址拼成的多行串, 码率)。

    多行是为了"主地址被 CDN 拒了就换备用"：B站 的 baseUrl 带时效签名，
    过一会儿或换节点就会 403。
    """
    dash = (download or {}).get("dash") or {}
    audios = [
        a
        for a in (dash.get("audio") or [])
        if (a.get("baseUrl") or a.get("base_url") or "").strip()
    ]
    if audios:
        best = max(audios, key=lambda a: a.get("bandwidth") or 0)
        url = (best.get("baseUrl") or best.get("base_url") or "").strip()
        backup = best.get("backupUrl") or best.get("backup_url") or []
        lines = [url]
        if isinstance(backup, list):
            lines += [str(b).strip() for b in backup[:2] if str(b).strip()]
        return "\n".join(lines), int(best.get("bandwidth") or 0)

    # 老视频没有 dash，只有 durl（整段 mp4/flv）
    durl = (download or {}).get("durl") or []
    if durl and durl[0].get("url"):
        return str(durl[0]["url"]), 0
    return "", 0


async def _download_audio(source: str, dest: Path) -> int:
    """按行尝试候选地址（第一个成功就停），返回落盘字节数。"""
    import aiohttp

    headers = {"Referer": "https://www.bilibili.com", "User-Agent": UA}
    timeout = aiohttp.ClientTimeout(total=300)
    last_error = ""
    for candidate in [line.strip() for line in source.splitlines() if line.strip()]:
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(candidate, headers=headers) as response:
                    if response.status != 200:
                        last_error = f"HTTP {response.status}"
                        continue
                    size = 0
                    with dest.open("wb") as handle:
                        async for chunk in response.content.iter_chunked(1 << 16):
                            handle.write(chunk)
                            size += len(chunk)
            if size > 0:
                return size
            last_error = "下到 0 字节"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
    raise RuntimeError(f"音频下载失败（{last_error or '没有可用地址'}）")


# ── 转写 ────────────────────────────────────────────────────────────────

def _load_model(size: str):
    with _model_lock:
        cached = _models.get(size)
        if cached is None:
            from faster_whisper import WhisperModel

            cached = WhisperModel(size, device="cpu", compute_type="int8")
            _models[size] = cached
        return cached


def _transcribe_blocking(path: str, size: str, lang: str) -> str:
    model = _load_model(size)
    segments, _info = model.transcribe(
        path,
        language=None if lang == "auto" else lang,
        vad_filter=True,  # 掐掉静音段：省时间，也少出"嗯…啊…"这类幻觉
    )
    return "".join(segment.text for segment in segments).strip()


async def _transcribe_locked(
    data_dir: Path,
    bvid: str,
    cred,
    model_size: str,
    lang: str,
    max_minutes: int,
) -> dict:
    from bilibili_api import video

    audio_path: Optional[Path] = None
    try:
        handle = video.Video(bvid=bvid, credential=cred)
        try:
            info = await handle.get_info()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"取视频信息失败：{type(exc).__name__}: {str(exc)[:160]}"}

        duration = int(info.get("duration") or 0)
        limit = max(0, int(max_minutes or 0)) * 60
        if limit and duration > limit:
            return {
                "ok": False,
                "skipped": True,
                "error": f"视频时长 {duration // 60} 分 {duration % 60} 秒，超过转写上限 {max_minutes} 分钟",
                "hint": "长视频转写太贵，直接跳过。",
            }

        cid = int(info.get("cid") or 0)
        if not cid and info.get("pages"):
            cid = int((info["pages"][0] or {}).get("cid") or 0)
        if not cid:
            return {"ok": False, "error": "拿不到 cid"}

        try:
            download = await handle.get_download_url(cid=cid)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"取音频地址失败：{type(exc).__name__}: {str(exc)[:160]}"}

        source, _bandwidth = _pick_audio(download)
        if not source:
            return {"ok": False, "error": "这个视频没有可用的音频流（可能是番剧/付费内容）"}

        audio_path = tmp_dir(data_dir) / f"{bvid}.m4s"
        try:
            size = await _download_audio(source, audio_path)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}

        # 模型第一次用要联网下（tiny≈75MB / base≈145MB / small≈484MB）。
        # 单独给 15 分钟，别把它算进"转写超时"——否则第一次用必然超时失败。
        try:
            await asyncio.wait_for(asyncio.to_thread(_load_model, model_size), timeout=900)
        except asyncio.TimeoutError:
            return {
                "ok": False,
                "error": "模型加载超时（>15 分钟）",
                "hint": "首次使用要下载模型；网络慢就先把 asr_model 改成 tiny。",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"模型加载失败：{type(exc).__name__}: {str(exc)[:160]}",
                "hint": "首次使用需要联网下载模型；也可把 asr_model 调小一档（tiny / base）。",
            }

        timeout = max(120.0, duration * 2.5)
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(_transcribe_blocking, str(audio_path), model_size, lang),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"转写超时（>{int(timeout)} 秒）", "hint": "跳过这条。"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"转写失败：{type(exc).__name__}: {str(exc)[:160]}"}

        return {
            "ok": True,
            "bvid": bvid,
            "title": info.get("title", ""),
            "text": text,
            "chars": len(text),
            "audio_seconds": duration,
            "audio_kb": size // 1024,
            "model": model_size,
            "note": "" if text else "转写结果是空的（可能没有人声）",
        }
    finally:
        # 音频不留在磁盘上：一段 20 分钟的视频有几十 MB。
        if audio_path is not None:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass


SPEECH_CHUNK_SECONDS = 110          # 宿主那边上限 120 秒，留 10 秒余量
SPEECH_MAX_BYTES = 4 * 1024 * 1024  # 宿主 MAX_AUDIO_BYTES


def _split_audio(source: Path, work: Path, seconds: int = SPEECH_CHUNK_SECONDS) -> list[Path]:
    """ffmpeg 把音频转成 16k/单声道/PCM16 WAV，并按秒切片。

    ⚠️ 宿主语音输入的验收条件很硬：RIFF/PCM16/**16000Hz/1 声道**、≤120 秒、≤4MB。
       所以不能直接喂 m4s，也不能整段喂 —— 必须转码 + 切片。
    """
    binary = ffmpeg_path()
    if not binary:
        raise RuntimeError("找不到 ffmpeg（tools/ffmpeg-8.1-essentials_build 或 PATH）")
    for old in work.glob("part_*.wav"):
        old.unlink(missing_ok=True)
    command = [
        binary, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        "-f", "segment", "-segment_time", str(int(seconds)), "-reset_timestamps", "1",
        str(work / "part_%03d.wav"),
    ]
    result = subprocess.run(command, capture_output=True, timeout=600)
    if result.returncode != 0:
        tail = (result.stderr or b"").decode("utf-8", "ignore").strip()[-300:]
        raise RuntimeError(f"ffmpeg 退出码 {result.returncode}：{tail}")
    parts = sorted(work.glob("part_*.wav"))
    if not parts:
        raise RuntimeError("ffmpeg 没切出文件（可能整段没有音轨）")
    return parts


def canonical_wav(data: bytes) -> bytes:
    """把 ffmpeg 的 WAV 压成"教科书式" 44 字节头 + 纯 PCM。

    ⚠️ 宿主语音输入的验收很硬：`RIFF/WAVEfmt /data` 必须紧挨着（`data` 在偏移 36），
       16kHz / 单声道 / PCM16。而 ffmpeg 会塞一个 `LIST`（含编码器名、时间码），
       把 `data` 推到偏移 100 多 —— 直接被判 `Expected PCM16 WAV`（实测踩过）。
       所以这里自己走一遍 chunk，重建最简头。
    """
    import struct

    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise RuntimeError("ffmpeg 产出的不是 RIFF/WAVE")
    position, fmt, pcm = 12, b"", b""
    while position + 8 <= len(data):
        chunk_id = data[position:position + 4]
        size = int.from_bytes(data[position + 4:position + 8], "little")
        body = data[position + 8:position + 8 + size]
        if chunk_id == b"fmt ":
            fmt = body
        elif chunk_id == b"data":
            pcm = body
        position += 8 + size + (size & 1)
    if len(fmt) < 16 or not pcm:
        raise RuntimeError("WAV 里没有 fmt/data 块")
    channels = struct.unpack_from("<H", fmt, 2)[0]
    rate = struct.unpack_from("<I", fmt, 4)[0]
    bits = struct.unpack_from("<H", fmt, 14)[0]
    if (channels, rate, bits) != (1, 16000, 16):
        raise RuntimeError(f"切片格式不对：{channels} 声道 / {rate} Hz / {bits} bit")
    header = (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
        + b"data" + struct.pack("<I", len(pcm))
    )
    return header + pcm


def _read_canonical(path: Path) -> bytes:
    return canonical_wav(path.read_bytes())


def _join_texts(texts: list[str], lang: str) -> str:
    bits = [str(t or "").strip() for t in texts if str(t or "").strip()]
    separator = "" if str(lang or "").lower().startswith(("zh", "yue")) else " "
    return separator.join(bits)


async def _transcribe_via_host(
    data_dir: Path,
    bvid: str,
    cred,
    speech_call,
    lang: str,
    max_minutes: int,
) -> dict:
    """下载音频 → ffmpeg 切片 → 逐片交给宿主语音输入 → 拼起来。

    `speech_call` 是**同步**可调用：`(wav_bytes, identity, language) -> dict`。
    为什么同步：它内部要把协程扔回宿主主循环（`run_coroutine_threadsafe`），
    而这里正跑在插件自己的线程里。
    """
    from bilibili_api import video

    handle = video.Video(bvid=bvid, credential=cred)
    info = await handle.get_info()
    duration = int(info.get("duration") or 0)
    if int(max_minutes) > 0 and duration and duration > int(max_minutes) * 60:
        return {
            "ok": False, "skipped": True,
            "error": f"视频 {duration // 60} 分钟，超过上限 {int(max_minutes)} 分钟",
            "hint": "这类直接跳过，别切开转 —— 切片调用次数会翻好几倍。",
        }

    page = (info.get("pages") or [{}])[0]
    cid = int(page.get("cid") or info.get("cid") or 0)
    download = await handle.get_download_url(cid=cid)
    source, bandwidth = _pick_audio(download)
    work = tmp_dir(data_dir) / f"host-{bvid}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        audio_path = work / "audio.m4s"
        size = await _download_audio(source, audio_path)
        parts = await asyncio.to_thread(_split_audio, audio_path, work)
        texts: list[str] = []
        for index, part in enumerate(parts):
            payload = await asyncio.to_thread(_read_canonical, part)
            if len(payload) > SPEECH_MAX_BYTES:
                return {
                    "ok": False,
                    "error": f"切片 {index} 有 {len(payload) // 1024} KB，超过语音接口 4MB 上限",
                    "hint": "把片长调小（SPEECH_CHUNK_SECONDS）。",
                }
            result = await asyncio.to_thread(
                speech_call, payload, f"bili-{bvid}-{index}", lang
            )
            texts.append(str((result or {}).get("text") or ""))
        text = _join_texts(texts, lang)
        return {
            "ok": True,
            "bvid": bvid,
            "title": info.get("title", ""),
            "text": text,
            "chars": len(text),
            "audio_seconds": duration,
            "audio_kb": size // 1024,
            "engine": "host",
            "chunks": len(parts),
            "bandwidth": bandwidth,
            "note": "" if text else "转写结果是空的（可能没有人声）",
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def transcribe(
    data_dir: Path,
    bvid: str,
    cred=None,
    model_size: str = DEFAULT_MODEL,
    lang: str = "zh",
    max_minutes: int = MAX_MINUTES,
    engine: str = "host",
    speech_call=None,
) -> dict:
    """把一条视频转成文字。

    返回 `{"ok": True, "text": ...}`；失败时 `{"ok": False, "error": ...}`。
    「转出来是空的」也是一种结果（纯音乐/无人声），返回 `ok=True, text=""`，
    免得模型把它当成故障反复重试。

    `cred` 由调用方传进来（host.py 那边已有 bili_client 的凭证加载逻辑）——
    别在这里 `import bili_client`：插件目录不在 sys.path 上，这个 import 会失败。
    """
    engine = str(engine or "host").lower()
    if engine == "host" and callable(speech_call):
        async with _lock():
            try:
                return await _transcribe_via_host(
                    data_dir, bvid, cred, speech_call, str(lang or "zh"),
                    int(max_minutes if max_minutes is not None else MAX_MINUTES),
                )
            except Exception as exc:  # noqa: BLE001
                # 宿主那条路坏了（服务没起、模型没准备、provider 报错）——
                # 能退本地 whisper 就退，退不了就把原因带回去。
                reason = f"{type(exc).__name__}: {str(exc)[:160]}"
                fallback = ready("local")
                if not fallback["ready"]:
                    return {
                        "ok": False,
                        "error": f"语音输入那条路失败：{reason}",
                        "hint": "去设置里看看语音输入插件是否启用/模型是否就绪，或把转写引擎改成 local。",
                    }
                result = await _transcribe_locked(
                    data_dir, bvid, cred, str(model_size or DEFAULT_MODEL),
                    str(lang or "zh"), int(max_minutes if max_minutes is not None else MAX_MINUTES),
                )
                if result.get("ok"):
                    result["note"] = f"语音输入那条路失败（{reason}），已退回本地 Whisper"
                    result["engine"] = "local-fallback"
                return result

    check = ready("local")
    if not check["ready"]:
        return {
            "ok": False,
            "error": check["reason"],
            "hint": "本地转写不可用；此类视频直接跳过即可，别反复重试。",
        }

    async with _lock():
        return await _transcribe_locked(
            data_dir,
            bvid,
            cred,
            str(model_size or DEFAULT_MODEL),
            str(lang or "zh"),
            int(max_minutes if max_minutes is not None else MAX_MINUTES),
        )
