"""Force another session's cache write during each prefix comparison."""
import builtins
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import importlib.util
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


@pytest.fixture
def tokenizer():
    baseline = os.getenv("SESSION_STATE_BASELINE_DIR")
    if baseline:
        spec = importlib.util.spec_from_file_location("tokenizer_race_baseline", Path(baseline) / "app/agent_tokenizer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    import agent_tokenizer
    return agent_tokenizer


@pytest.mark.parametrize("cache_kind", ["hash", "text", "tokens"])
def test_concurrent_cache_append_during_prefix_matching(tokenizer, monkeypatch, cache_kind):
    t = tokenizer
    with ThreadPoolExecutor(max_workers=1) as executor:
        written = False

        def append_from_another_session(cache, value):
            nonlocal written
            if written:
                return
            written = True

            def write():
                with getattr(t, "_INCREMENTAL_TOKEN_CACHE_LOCK", nullcontext()):
                    cache.append(value)

            # Also proves the expensive comparison does not hold the lock.
            executor.submit(write).result(timeout=2)

        if cache_kind == "tokens":
            cache = deque([("A", 1), ("unrelated", 9)], maxlen=4)
            monkeypatch.setattr(t, "_FLATTEN_TOKEN_CACHE", cache)
            monkeypatch.setattr(t, "_FLATTEN_TOKEN_EXACT", {})

            class Text(str):
                def startswith(self, prefix, *args):
                    append_from_another_session(cache, ("concurrent", 10))
                    return super().startswith(prefix, *args)

            monkeypatch.setattr(t, "_flatten_messages_incremental", lambda _: Text("A\n\nB"))
            monkeypatch.setattr(t, "count_text_tokens", len)
            assert t.count_message_tokens_incremental([object()]) == 4
        else:
            def compare(items):
                append_from_another_session(cache, concurrent_row)
                return builtins.all(items)

            monkeypatch.setattr(t, "all", compare, raising=False)
            if cache_kind == "hash":
                cache = deque([(1, ["other"], [object()]), (1, ["second"], [object()])], maxlen=8)
                concurrent_row = (1, ["concurrent"], [object()])
                monkeypatch.setattr(t, "_MESSAGE_TOKEN_LIST_CACHE", cache)
                assert t._reuse_hash_prefix([object(), object()]) == ([], 0)
            else:
                cache = deque([([object()], "other"), ([object()], "second")], maxlen=8)
                concurrent_row = ([object()], "concurrent")
                monkeypatch.setattr(t, "_FLATTEN_TEXT_CACHE", cache)
                monkeypatch.setattr(t, "_flatten_message_parts", str)
                assert t._flatten_messages_incremental(["target", "tail"]) == "target\n\ntail"
        assert written
