"""Desktop browser guest policy and a real sandboxed webview smoke."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.proc_flags import hidden_flags

ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_browser_guest_policy():
    result = subprocess.run(['node', '--test', str(ROOT / 'tests/js/sidebar_browser_guests.cjs')],
                            capture_output=True, encoding='utf-8', timeout=20, creationflags=hidden_flags())
    assert result.returncode == 0, result.stdout + result.stderr


def test_sidebar_browser_real_electron(tmp_path):
    if os.name != 'nt':
        pytest.skip('The bundled desktop runtime is Windows-only')
    electron = ROOT / 'packaging/node_modules/electron/dist/electron.exe'
    if not electron.exists():
        pytest.skip('Packaging dependencies are unavailable')
    env = os.environ.copy()
    env.pop('ELECTRON_RUN_AS_NODE', None)

    def run(executable):
        return subprocess.run([str(executable), '--disable-gpu', str(ROOT / 'tests/js/sidebar_browser_electron.cjs')],
                              capture_output=True, encoding='utf-8', timeout=50, env=env, creationflags=hidden_flags())

    result = run(electron)
    if 'install_dir_access.cc' in result.stderr:
        runtime = tmp_path / 'electron'
        shutil.copytree(electron.parent, runtime)
        result = run(runtime / 'electron.exe')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'navigation, isolation, popup and cleanup checks passed' in result.stdout
