import json
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from types import SimpleNamespace

import pytest

import plugins.manager as manager


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    monkeypatch.setattr(manager, "_canonical_manager_paths", manager.OrderedDict())
    monkeypatch.setattr(manager, "_default_manager", None)
    monkeypatch.setattr(manager, "_default_manager_config", None)


def count_resolutions(monkeypatch):
    original = Path.resolve
    calls = []
    def resolve(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    return calls


def test_unchanged_canonical_configuration_reuses_names_but_reads_state_live(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"version": 1, "plugins": {}}), encoding="utf8")
    monkeypatch.setattr(manager, "default_discovery_dirs", lambda: (plugins,))
    monkeypatch.setattr(manager, "default_state_path", lambda: state)
    calls = count_resolutions(monkeypatch)
    first = manager.get_plugin_manager()
    count = len(calls)
    assert manager.get_plugin_manager() is first
    assert len(calls) == count
    first.state.set_enabled("demo", False)
    assert manager.get_plugin_manager().state.is_enabled("demo") is False


def test_new_file_invalidates_a_cached_missing_name(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    calls = count_resolutions(monkeypatch)
    manager._canonical_manager_path(state)
    manager._canonical_manager_path(state)
    assert calls == [state]
    state.write_text("{}", encoding="utf8")
    manager._canonical_manager_path(state)
    assert calls == [state, state]


def test_replaced_file_is_resolved_again(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text("{}", encoding="utf8")
    calls = count_resolutions(monkeypatch)
    manager._canonical_manager_path(state)
    replacement = tmp_path / "new.json"
    replacement.write_text("{}", encoding="utf8")
    replacement.replace(state)
    manager._canonical_manager_path(state)
    assert calls == [state, state]


def test_replaced_parent_invalidates_even_a_missing_leaf(tmp_path, monkeypatch):
    parent = tmp_path / "config"
    parent.mkdir()
    state = parent / "missing.json"
    calls = count_resolutions(monkeypatch)
    manager._canonical_manager_path(state)
    moved = tmp_path / "old-config"
    # Both explicit targets belong to this disposable test directory.
    assert parent.absolute().is_relative_to(tmp_path.absolute())
    assert moved.absolute().is_relative_to(tmp_path.absolute())
    parent.rename(moved)
    parent.mkdir()
    manager._canonical_manager_path(state)
    assert calls == [state, state]


def test_aliases_keep_live_resolution(tmp_path, monkeypatch):
    alias = tmp_path / "alias"
    alias.mkdir()
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    target = [one]
    original = Path.resolve
    calls = []
    def resolve(path, *args, **kwargs):
        if path == alias:
            calls.append(path)
            return target[0]
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    assert manager._canonical_manager_path(alias) == str(one)
    target[0] = two
    assert manager._canonical_manager_path(alias) == str(two)
    assert calls == [alias, alias]
    assert not manager._canonical_manager_paths


def test_missing_parent_is_not_cached(tmp_path, monkeypatch):
    state = tmp_path / "not-created" / "state.json"
    calls = count_resolutions(monkeypatch)
    manager._canonical_manager_path(state)
    manager._canonical_manager_path(state)
    assert calls == [state, state]
    assert not manager._canonical_manager_paths


def test_identity_failure_cannot_hide_a_live_resolution_error(tmp_path, monkeypatch):
    path = tmp_path / "plugins"
    path.mkdir()
    manager._canonical_manager_path(path)
    original_lstat, original_resolve = Path.lstat, Path.resolve
    def lstat(p):
        if p == path:
            raise PermissionError("guard denied")
        return original_lstat(p)
    def resolve(p, *args, **kwargs):
        if p == path:
            raise PermissionError("resolution denied")
        return original_resolve(p, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(PermissionError, match="resolution denied"):
        manager._canonical_manager_path(path)


@pytest.mark.parametrize("attributes,inode", [(0x400, 1), (0, 0)])
def test_reparse_or_unknown_identity_cannot_be_cached(tmp_path, monkeypatch, attributes, inode):
    original = Path.lstat
    def lstat(path):
        if path == tmp_path:
            return SimpleNamespace(st_ino=inode, st_mode=0o40755, st_file_attributes=attributes)
        return original(path)
    monkeypatch.setattr(Path, "lstat", lstat)
    assert manager._manager_path_identity(tmp_path) is None


def test_cache_is_bounded(tmp_path):
    for i in range(manager._CANONICAL_MANAGER_PATH_LIMIT + 3):
        path = tmp_path / str(i)
        path.mkdir()
        manager._canonical_manager_path(path)
    assert len(manager._canonical_manager_paths) == manager._CANONICAL_MANAGER_PATH_LIMIT


def test_environment_configuration_change_selects_new_manager(tmp_path, monkeypatch):
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    monkeypatch.delenv("PLUGINS_DIRS", raising=False)
    monkeypatch.setenv("PLUGINS_DIR", str(one))
    monkeypatch.setenv("PLUGINS_STATE_PATH", str(tmp_path / "state.json"))
    first = manager.get_plugin_manager()
    monkeypatch.setenv("PLUGINS_DIR", str(two))
    second = manager.get_plugin_manager()
    assert first is not second
    assert second.discovery_dirs == (two,)


@pytest.mark.parametrize("stage", ["paths", "canonical", "construct"])
def test_slow_lookup_does_not_block_another_manager_reader(tmp_path, monkeypatch, stage):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    monkeypatch.setattr(manager, "default_discovery_dirs", lambda: (plugins,))
    monkeypatch.setattr(manager, "default_state_path", lambda: tmp_path / "state.json")
    name = {"paths": "default_discovery_dirs", "canonical": "_canonical_manager_path",
            "construct": "PluginManager"}[stage]
    original = getattr(manager, name)
    entered, release = threading.Event(), threading.Event()
    first_lock = threading.Lock()
    first = [True]

    def slow_once(*args, **kwargs):
        with first_lock:
            blocked = first[0]
            first[0] = False
        if blocked:
            entered.set()
            assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, name, slow_once)
    with ThreadPoolExecutor(2) as pool:
        slow = pool.submit(manager.get_plugin_manager)
        try:
            assert entered.wait(5)
            fast = pool.submit(manager.get_plugin_manager).result(timeout=2)
        finally:
            release.set()
        assert slow.result(timeout=5) is fast
        assert manager.get_plugin_manager() is fast


@pytest.mark.parametrize("stage", ["paths", "construct"])
def test_older_lookup_cannot_publish_after_environment_switch(tmp_path, monkeypatch, stage):
    one, two = tmp_path / "one", tmp_path / "two"
    one.mkdir()
    two.mkdir()
    monkeypatch.delenv("PLUGINS_DIRS", raising=False)
    monkeypatch.setenv("PLUGINS_DIR", str(one))
    monkeypatch.setenv("PLUGINS_STATE_PATH", str(tmp_path / "one.json"))
    name = "default_discovery_dirs" if stage == "paths" else "PluginManager"
    original = getattr(manager, name)
    entered, release = threading.Event(), threading.Event()
    first_lock = threading.Lock()
    first = [True]

    def slow_once(*args, **kwargs):
        result = original(*args, **kwargs)
        with first_lock:
            blocked = first[0]
            first[0] = False
        if blocked:
            entered.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(manager, name, slow_once)
    with ThreadPoolExecutor(2) as pool:
        old = pool.submit(manager.get_plugin_manager)
        try:
            assert entered.wait(5)
            monkeypatch.setenv("PLUGINS_DIR", str(two))
            monkeypatch.setenv("PLUGINS_STATE_PATH", str(tmp_path / "two.json"))
            current = pool.submit(manager.get_plugin_manager).result(timeout=2)
        finally:
            release.set()
        assert old.result(timeout=5) is current
    assert manager.get_plugin_manager() is current
    assert current.discovery_dirs == (two,)
    assert current.state.path == tmp_path / "two.json"


def test_cold_concurrent_readers_return_one_published_manager(tmp_path, monkeypatch):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    barrier = threading.Barrier(8)
    monkeypatch.setattr(manager, "default_state_path", lambda: tmp_path / "state.json")

    def dirs():
        barrier.wait(timeout=5)
        return (plugins,)

    monkeypatch.setattr(manager, "default_discovery_dirs", dirs)
    with ThreadPoolExecutor(8) as pool:
        readers = [pool.submit(manager.get_plugin_manager) for _ in range(8)]
        results = [future.result(timeout=5) for future in readers]
    assert all(result is results[0] for result in results)
    assert manager._default_manager is results[0]


def test_canonical_resolution_of_other_path_progresses_during_slow_resolve(tmp_path, monkeypatch):
    slow_path, fast_path = tmp_path / "slow", tmp_path / "fast"
    slow_path.mkdir()
    fast_path.mkdir()
    original = Path.resolve
    entered, release = threading.Event(), threading.Event()

    def resolve(path, *args, **kwargs):
        if path == slow_path:
            entered.set()
            assert release.wait(5)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with ThreadPoolExecutor(2) as pool:
        slow = pool.submit(manager._canonical_manager_path, slow_path)
        try:
            assert entered.wait(5)
            assert pool.submit(manager._canonical_manager_path, fast_path).result(timeout=2) == str(fast_path)
        finally:
            release.set()
        assert slow.result(timeout=5) == str(slow_path)


def test_incomplete_legacy_copy_is_not_exposed_to_another_reader(tmp_path, monkeypatch):
    legacy, target = tmp_path / "old.json", tmp_path / "new.json"
    legacy.write_text("complete", encoding="utf8")
    original = manager.shutil.move
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def move(source, destination):
        calls.append((source, destination))
        # Model the copy phase of a cross-volume move: destination exists but
        # source has not yet been removed. Readers must wait for completion.
        target.write_text("partial", encoding="utf8")
        entered.set()
        assert release.wait(5)
        return original(source, destination)

    def read_after_migration():
        second_started.set()
        return manager._migrate_legacy_path(target, legacy).read_text(encoding="utf8")

    monkeypatch.setattr(manager.shutil, "move", move)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(manager._migrate_legacy_path, target, legacy)
        try:
            assert entered.wait(5)
            second = pool.submit(read_after_migration)
            assert second_started.wait(5)
            with pytest.raises(FutureTimeout):
                second.result(timeout=.05)
        finally:
            release.set()
        assert first.result(timeout=5) == target
        assert second.result(timeout=5) == "complete"
    assert len(calls) == 1


def test_failed_path_lookup_does_not_replace_published_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "default_discovery_dirs", lambda: (tmp_path,))
    monkeypatch.setattr(manager, "default_state_path", lambda: tmp_path / "state.json")
    published = manager.get_plugin_manager()

    def fail():
        raise PermissionError("path unavailable")

    monkeypatch.setattr(manager, "default_state_path", fail)
    with pytest.raises(PermissionError, match="path unavailable"):
        manager.get_plugin_manager()
    assert manager._default_manager is published
    assert not manager._default_manager_lock.locked()
