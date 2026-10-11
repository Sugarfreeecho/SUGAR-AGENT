import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_payload_excludes_retained_user_data_without_building(tmp_path):
    node = shutil.which('node')
    matcher = ROOT / 'packaging/node_modules/app-builder-lib/out/fileMatcher.js'
    if not node or not matcher.is_file():
        pytest.skip('electron-builder matcher is unavailable')
    script = r'''
const assert = require('node:assert/strict');
const path = require('node:path');
const root = process.argv[1];
const payload = process.argv[2];
const config = require(path.join(root, 'packaging/electron-builder.config.cjs'));
const { FileMatcher } = require(path.join(root, 'packaging/node_modules/app-builder-lib/out/fileMatcher.js'));
const { createFilter } = require(path.join(root, 'packaging/node_modules/app-builder-lib/out/util/filter.js'));
const patterns = [];
new FileMatcher(payload, payload, value => value, config.extraResources[0].filter).computeParsedPatterns(patterns);
const filter = createFilter(payload, patterns);
for (const relative of ['.config', '.config/model_profiles.json', '.config/nested/file',
                        '.sugaragent', '.sugaragent/mcp_servers.json', 'workspace', 'workspace/sessions/history.json']) {
  assert.equal(filter(path.join(payload, relative), { isDirectory: () => !relative.includes('/') }), false, relative);
}
for (const relative of ['app/main.py', 'app/config_paths.py', 'python/python.exe', 'plugins/demo/plugin.py',
                        'workspace-template/skills/example/SKILL.md']) {
  assert.equal(filter(path.join(payload, relative), { isDirectory: () => false }), true, relative);
}
'''
    result = subprocess.run(
        [node, '-e', script, str(ROOT), str(tmp_path / 'payload')],
        capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')


@pytest.mark.parametrize('previous_patch', [False, True])
def test_workspace_patch_preserves_atomic_rollback_and_is_idempotent(tmp_path, previous_patch):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is unavailable')
    script = tmp_path / 'scripts/patch-nsis.mjs'
    script.parent.mkdir()
    shutil.copyfile(ROOT / 'packaging/scripts/patch-nsis.mjs', script)
    templates = tmp_path / 'node_modules/app-builder-lib/templates/nsis'
    templates.mkdir(parents=True)
    source_templates = ROOT / 'packaging/node_modules/app-builder-lib/templates/nsis'
    if not source_templates.is_dir():
        pytest.skip('electron-builder templates are unavailable')
    for name in ('multiUserUi.nsh', 'uninstaller.nsh'):
        shutil.copyfile(source_templates / name, templates / name)
    if previous_patch:
        template = templates / 'uninstaller.nsh'
        source = template.read_text(encoding='utf-8')
        source = source.replace(
            'IfFileExists "$INSTDIR$R0\\$R2\\*.*" isDir isNotDir',
            'StrCmp "$R0\\$R2" "\\resources\\runtime\\workspace" continue\n'
            '    IfFileExists "$INSTDIR$R0\\$R2\\*.*" isDir isNotDir', 1,
        )
        template.write_text(source, encoding='utf-8')
    outputs = []
    for _ in range(2):
        result = subprocess.run([node, str(script)], capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
        outputs.append((templates / 'uninstaller.nsh').read_text(encoding='utf-8'))
    assert outputs[0] == outputs[1]
    source = outputs[0]
    atomic = source.split('Function un.atomicRMDir', 1)[1].split('FunctionEnd', 1)[0]
    restore = source.split('Function un.restoreFiles', 1)[1].split('FunctionEnd', 1)[0]
    assert '\\resources\\runtime\\workspace' in atomic
    assert atomic.count('\\resources\\runtime\\workspace') == 1
    assert '\\resources\\runtime\\.config' in atomic
    assert '\\resources\\runtime\\.sugaragent' in atomic
    assert 'workspace' not in restore and '.config' not in restore
    assert 'Call un.restoreFiles' in source
    assert 'Call un.SugarAgentRemoveFiles' in source
    assert 'RMDir /r $INSTDIR' not in source


def test_workspace_patch_fails_when_required_template_changes(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is unavailable')
    script = tmp_path / 'scripts/patch-nsis.mjs'
    script.parent.mkdir()
    shutil.copyfile(ROOT / 'packaging/scripts/patch-nsis.mjs', script)
    templates = tmp_path / 'node_modules/app-builder-lib/templates/nsis'
    templates.mkdir(parents=True)
    (templates / 'uninstaller.nsh').write_text('Changed template', encoding='utf-8')
    result = subprocess.run([node, str(script)], capture_output=True, timeout=15)
    assert result.returncode != 0


def test_workspace_removal_rule_preprocesses_without_building_an_installer(tmp_path):
    import os

    cache = Path(os.environ.get('LOCALAPPDATA', '')) / 'electron-builder/Cache'
    compilers = list(cache.glob('nsis-*/nsis-*/makensis.exe'))
    if not compilers:
        pytest.skip('Cached NSIS compiler is unavailable')
    script = tmp_path / 'validate.nsi'
    source = ROOT / 'packaging/nsis/installer.nsh'
    script.write_text(
        'Unicode true\nName "SugarAgent rule check"\nOutFile "unused.exe"\n'
        '!define ONE_CLICK\n'
        f'!include /CHARSET=UTF8 "{source}"\n'
        'Section "Validate"\nSectionEnd\n',
        encoding='utf-8-sig',
    )
    result = subprocess.run(
        [str(compilers[0]), '/NOCONFIG', '/PPO', str(script)],
        cwd=tmp_path, capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    assert b'Function un.SugarAgentRemoveFiles' in result.stdout
    assert b'"\\resources\\runtime\\.config" sugar_remove_next' in result.stdout
    assert b'"\\resources\\runtime\\.sugaragent" sugar_remove_next' in result.stdout
    assert not (tmp_path / 'unused.exe').exists()
