"""Release boundaries and installed runtime resolution, without rebuilding the app."""
import asyncio
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]


def node(script, *arguments):
    result = subprocess.run([shutil.which('node'), '--input-type=module', '-e', script, *map(str, arguments)],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    return result.stdout


def packaged_modules(monkeypatch):
    name = 'browser_package_resolution_test'
    package = types.ModuleType(name)
    package.__path__ = [str(ROOT / 'plugins/browser-use')]
    monkeypatch.setitem(sys.modules, name, package)
    import importlib
    return importlib.import_module(name + '.runtime_paths'), importlib.import_module(name + '.setup')


def test_browser_is_bundled_but_requires_explicit_first_enable(tmp_path, monkeypatch):
    from plugins import PluginManager
    from plugins.tiers import default_enabled, tier_of, tools_resident, packaged_by_default
    assert tier_of('browser-use') == 'extension'
    assert packaged_by_default('browser-use') and not tools_resident('browser-use')
    assert default_enabled('browser-use') is False
    manager = PluginManager([ROOT / 'plugins'], tmp_path / 'plugins.json')
    assert manager.is_enabled('browser-use') is False
    monkeypatch.setenv('PLUGIN_BROWSER_USE_ENABLED', '1')
    assert manager.is_enabled('browser-use') is True


def test_installed_runtime_never_falls_back_to_system_node(tmp_path, monkeypatch):
    paths, setup = packaged_modules(monkeypatch)
    (tmp_path / 'browser-bundle.json').write_text('{}')
    monkeypatch.setattr(paths.shutil, 'which', lambda _name: '/unrelated/system/node')
    assert paths.node_executable(tmp_path) == ''
    executable = tmp_path / 'node' / ('node.exe' if paths.os.name == 'nt' else 'node')
    executable.parent.mkdir();executable.write_bytes(b'fixture')
    assert paths.node_executable(tmp_path) == str(executable)
    monkeypatch.setattr(setup, 'ROOT', tmp_path)
    monkeypatch.setattr(setup, 'NODE', tmp_path / 'plugins/browser-use/node')
    with pytest.raises(ValueError, match='修复或重新安装'):
        asyncio.run(setup.install_runtime())


def test_runtime_detection_checks_locked_version_and_required_modules(tmp_path, monkeypatch):
    paths, _ = packaged_modules(monkeypatch)
    (tmp_path / 'package.json').write_text(json.dumps({'dependencies':{'@playwright/mcp':'0.0.83'}}))
    for relative in ['server.mjs','engine.mjs','relay.mjs','node_modules/playwright/package.json','node_modules/playwright-core/package.json','node_modules/@playwright/mcp/package.json']:
        file = tmp_path / relative;file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({'version':'0.0.82'}) if '@playwright/mcp' in relative else '{}')
    assert paths.runtime_installed(tmp_path) is False
    (tmp_path / 'node_modules/@playwright/mcp/package.json').write_text('{"version":"0.0.83"}')
    assert paths.runtime_installed(tmp_path) is True
    (tmp_path / 'node_modules/playwright-core/package.json').unlink()
    assert paths.runtime_installed(tmp_path) is False


def test_release_inputs_ignore_dev_dependencies_and_secrets_but_detect_source_changes(tmp_path):
    for relative in ['browser-extension/src/app.js','plugins/browser-use/host.py','frontend/src/app/modules/smooth-stream.js']:
        file=tmp_path/relative;file.parent.mkdir(parents=True, exist_ok=True);file.write_text('initial')
    output=node("""
      import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';
      import helpers from './packaging/scripts/browser-bundle.cjs';
      const root=process.argv[1],before=helpers.browserInputs(root);
      for(const relative of ['browser-extension/node_modules/private','plugins/browser-use/.env','plugins/browser-use/artifacts/token']){
        const file=path.join(root,relative);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'do not ship');
      }
      assert.equal(helpers.browserInputs(root),before);
      fs.writeFileSync(path.join(root,'frontend/src/app/modules/smooth-stream.js'),'shared follower changed');assert.notEqual(helpers.browserInputs(root),before);
      fs.writeFileSync(path.join(root,'frontend/src/app/modules/smooth-stream.js'),'initial');assert.equal(helpers.browserInputs(root),before);
      fs.writeFileSync(path.join(root,'browser-extension/src/app.js'),'changed');assert.notEqual(helpers.browserInputs(root),before);
      assert.throws(()=>helpers.assertBrowserBundle(root),/缺少浏览器连接/);
      assert.throws(()=>helpers.inside(root,'../outside'),/无效|越界/);console.log('OK');
    """,tmp_path)
    assert 'OK' in output


def test_staging_refuses_repository_source_and_case_aliases():
    assert 'OK' in node("""
      import assert from 'node:assert/strict';import {stageBrowserBundle} from './packaging/scripts/prepare-browser-bundle.mjs';
      const repo=process.cwd(),targets=[repo,repo+'/plugins',repo+'/browser-extension'];if(process.platform==='win32')targets.push(repo.toLowerCase());for(const target of targets)assert.throws(()=>stageBrowserBundle(target,{repo}),/不能覆盖源目录/);
      console.log('OK');
    """)


def test_build_rejects_unlocked_or_mismatched_runtime_dependency(tmp_path):
    assert 'OK' in node("""
      import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import {runtimeDependency} from './packaging/scripts/prepare-browser-bundle.mjs';
      const root=process.argv[1];fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({dependencies:{'@playwright/mcp':'0.0.83'}}));
      fs.writeFileSync(path.join(root,'package-lock.json'),JSON.stringify({packages:{'':{dependencies:{'@playwright/mcp':'0.0.82'}},'node_modules/@playwright/mcp':{version:'0.0.82'}}}));
      assert.throws(()=>runtimeDependency(root),/固定版本/);console.log('OK');
    """, tmp_path)
