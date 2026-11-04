import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { assertBrowserBundle } = require('./browser-bundle.cjs')
const repo = path.resolve(import.meta.dirname,'../..')
const at = process.argv.indexOf('--payload')
const payload = path.resolve(at >= 0 ? process.argv[at+1] : path.join(repo,'packaging/build/payload'))
const info = assertBrowserBundle(payload,{repo})
const bundledPython = path.join(payload,'python/python.exe')
const python = fs.existsSync(bundledPython) ? bundledPython : path.join(repo,'python/python.exe')
const work = fs.mkdtempSync(path.join(os.tmpdir(),'sugar-bundle-smoke-'))
const source = String.raw`
import asyncio, importlib, json, pathlib, sys, types, zipfile
root, work = map(pathlib.Path, sys.argv[1:])
package = types.ModuleType('browser_bundle_smoke')
package.__path__ = [str(root / 'plugins/browser-use')]
sys.modules[package.__name__] = package
setup = importlib.import_module(package.__name__ + '.setup')
runtime = importlib.import_module(package.__name__ + '.runtime')
setup.shutil.which = lambda _name: None
state = setup.snapshot()
for key in ('extension_ready','download_ready','node_available','runtime_installed','runtime_bundled'):
    assert state[key], (key, state)
assert state['node_source'] == 'bundled'
assert pathlib.Path(state['extension_directory']).is_relative_to(root)
archive = root / 'outputs/browser-extension' / ('sugaragent-browser-' + state['version'] + '.zip')
with zipfile.ZipFile(archive) as zipped:
    assert json.loads(zipped.read('manifest.json'))['version'] == state['version']
    assert all(not name.endswith('.map') for name in zipped.namelist())
async def check():
    assert (await setup.install_runtime())['status'] == 'succeeded'
    worker = runtime.BrowserRuntime('isolated-smoke','chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo',work)
    try:
        await worker.start()
        names = [tool['name'] for tool in worker.catalog]
        assert {'browser_get_context','browser_snapshot','browser_click'} <= set(names)
        status = await worker.request('status', {})
        assert status['connected'] is False
        return names
    finally:
        await worker.close()
names = asyncio.run(check())
print(json.dumps({'ok':True,'version':state['version'],'node_source':state['node_source'],
                  'node_and_npm_on_path':False,'runtime_installed':True,'tool_count':len(names),
                  'extension_and_download_ready':True,'offline_install_check':True}))
`
try {
  const result = spawnSync(python,['-B','-c',source,payload,work],{cwd:work,encoding:'utf8',windowsHide:true,timeout:60000,
    env:{PATH:'',SYSTEMROOT:process.env.SYSTEMROOT || '',WINDIR:process.env.WINDIR || '',TEMP:os.tmpdir(),TMP:os.tmpdir(),PYTHONUTF8:'1',PYTHONDONTWRITEBYTECODE:'1'}})
  if (result.status !== 0) throw new Error('隔离载荷验证失败：'+(result.error?.message || result.stderr || result.stdout))
  const summary = {...JSON.parse(result.stdout.trim().split(/\r?\n/).at(-1)),payload,node:info.node.version,files:info.files.length}
  fs.writeFileSync(path.join(payload,'browser-smoke.json'),JSON.stringify(summary,null,2)+'\n')
  console.log(JSON.stringify(summary,null,2))
} finally {
  const resolved = path.resolve(work)
  if (!resolved.startsWith(path.resolve(os.tmpdir())+path.sep) || !path.basename(resolved).startsWith('sugar-bundle-smoke-')) throw new Error('Unexpected smoke cleanup path')
  fs.rmSync(resolved,{recursive:true,force:true})
}
