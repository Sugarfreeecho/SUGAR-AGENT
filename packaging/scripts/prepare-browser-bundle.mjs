import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { sha256, filesUnder, browserInputs, inside, assertBrowserBundle } = require('./browser-bundle.cjs')
const policy = require('../browser-runtime.lock.json')
const REPO = path.resolve(import.meta.dirname, '../..')
const log = message => process.stdout.write(message + '\n')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))

export function runtimeDependency(directory) {
  const version = readJson(path.join(directory,'package.json')).dependencies?.['@playwright/mcp']
  const lock = readJson(path.join(directory,'package-lock.json'))
  if (!/^\d+\.\d+\.\d+$/.test(version || '') || lock.packages?.['']?.dependencies?.['@playwright/mcp'] !== version || lock.packages?.['node_modules/@playwright/mcp']?.version !== version) throw new Error('浏览器运行依赖必须固定版本，package.json 与 package-lock.json 必须一致')
  return version
}

function run(executable, args, cwd, env = process.env) {
  const result = spawnSync(executable, args, { cwd, env, stdio:'inherit', shell:false, windowsHide:true })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`浏览器资源构建失败：${path.basename(executable)} ${args.join(' ')}（${result.status}）`)
}
function npmEntry() {
  const candidates = [process.env.npm_execpath, path.join(path.dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js')]
  const entry = candidates.find(file => file && fs.existsSync(file) && file.endsWith('.js'))
  if (!entry) throw new Error('未找到构建用 npm-cli.js，请通过 npm run payload 启动或安装标准 Node.js')
  return entry
}
function removeChild(root, relative) {
  fs.rmSync(inside(root, relative), { recursive:true, force:true })
}
async function lockedFile(url, destination, expected, local) {
  if (fs.existsSync(destination) && sha256(destination) === expected) return
  fs.mkdirSync(path.dirname(destination), {recursive:true})
  if (local && fs.existsSync(local) && sha256(local) === expected) { fs.copyFileSync(local, destination); return }
  log(`· 下载固定浏览器运行资源：${url}`)
  const response = await fetch(url, {signal:AbortSignal.timeout(180000)})
  if (!response.ok) throw new Error(`下载失败：${url}（HTTP ${response.status}）`)
  const temporary = destination + '.partial-' + process.pid
  try {
    fs.writeFileSync(temporary, Buffer.from(await response.arrayBuffer()))
    if (sha256(temporary) !== expected) throw new Error(`下载校验失败：${url}`)
    fs.renameSync(temporary, destination)
  } finally { fs.rmSync(temporary, {force:true}) }
}

export async function prepareBrowserAssets({ repo=REPO, cache=path.join(repo,'packaging/build/browser-cache') } = {}) {
  if (process.platform !== 'win32' || process.arch !== 'x64') throw new Error('当前桌面发布目标为 Windows x64，请使用对应的构建主机')
  const extension = path.join(repo,'browser-extension'), runtime = path.join(repo,'plugins/browser-use/node')
  const mcpVersion = runtimeDependency(runtime)
  const npm = npmEntry()
  const env = {...process.env, PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:'1', PLAYWRIGHT_SKIP_BROWSER_GC:'1'}
  fs.mkdirSync(cache, {recursive:true})
  const node = path.join(cache,`node-v${policy.node.version}-win-x64/node.exe`)
  const license = path.join(path.dirname(node),'LICENSE')
  await lockedFile(policy.node.url, node, policy.node.sha256, process.execPath)
  await lockedFile(policy.node.licenseUrl, license, policy.node.licenseSha256, path.join(cache,'node-LICENSE'))
  const probe = spawnSync(node, ['-p','JSON.stringify({version:process.versions.node,platform:process.platform,arch:process.arch})'], {encoding:'utf8',windowsHide:true})
  const actual = probe.status === 0 ? JSON.parse(probe.stdout) : {}
  if (actual.version !== policy.node.version || actual.platform !== policy.node.platform || actual.arch !== policy.node.arch) throw new Error('内置 Node 版本或架构校验失败')

  // Install in a build cache, never prune the developer's plugin dependencies.
  const lockDigest = sha256(path.join(runtime,'package-lock.json'))
  const dependencies = path.join(cache,'mcp-'+lockDigest)
  const stamp = path.join(dependencies,'installed.json')
  if (!fs.existsSync(stamp) || readJson(stamp).lockDigest !== lockDigest || !['@playwright/mcp','playwright','playwright-core'].every(name=>fs.existsSync(path.join(dependencies,'node_modules',name,'package.json'))) || readJson(path.join(dependencies,'node_modules/@playwright/mcp/package.json')).version !== mcpVersion) {
    removeChild(cache,path.basename(dependencies))
    fs.mkdirSync(dependencies,{recursive:true})
    for (const file of ['package.json','package-lock.json']) fs.copyFileSync(path.join(runtime,file),path.join(dependencies,file))
    log('· 安装锁定版浏览器生产依赖（不下载浏览器内核）…')
    run(process.execPath,[npm,'ci','--omit=dev','--ignore-scripts','--no-audit','--no-fund'],dependencies,env)
    fs.writeFileSync(stamp,JSON.stringify({lockDigest}))
  }
  log('· 构建 SugarAgent 浏览器扩展…')
  run(process.execPath,[npm,'ci','--no-audit','--no-fund'],extension,env)
  run(process.execPath,[npm,'run','build'],extension,env)
  run(process.execPath,[npm,'run','package'],extension,env)
  const version = readJson(path.join(extension,'package.json')).version
  const pluginVersion = readJson(path.join(repo,'plugins/browser-use/.myagent-plugin/plugin.json')).version
  if (version !== pluginVersion || readJson(path.join(extension,'dist/manifest.json')).version !== version) throw new Error('浏览器扩展、dist 与宿主版本不一致')
  return {repo,version,node,license,dependencies,lockDigest,inputDigest:browserInputs(repo)}
}

export function stageBrowserBundle(payload, assets) {
  payload = path.resolve(payload)
  let ancestor = payload
  while (!fs.existsSync(ancestor)) ancestor = path.dirname(ancestor)
  payload = path.resolve(fs.realpathSync(ancestor),path.relative(ancestor,payload))
  const normalize = value => process.platform === 'win32' ? value.toLowerCase() : value
  const source = normalize(fs.realpathSync(assets.repo)), destination = normalize(payload), build = path.join(source,'packaging','build')
  if (destination === source || source.startsWith(destination+path.sep) || destination.startsWith(source+path.sep) && !destination.startsWith(build+path.sep)) throw new Error('浏览器载荷输出不能覆盖源目录；仓库内只允许 packaging/build 下的独立目录')
  fs.mkdirSync(payload,{recursive:true})
  fs.rmSync(path.join(payload,'browser-bundle.json'),{force:true})
  for (const relative of ['node','browser-extension','outputs/browser-extension','plugins/browser-use']) removeChild(payload,relative)
  const copy = (source, relative) => { const destination = inside(payload,relative);fs.mkdirSync(path.dirname(destination),{recursive:true});fs.copyFileSync(source,destination) }
  for (const file of filesUnder(path.join(assets.repo,'plugins/browser-use'),{source:true})) copy(file,'plugins/browser-use/'+path.relative(path.join(assets.repo,'plugins/browser-use'),file))
  fs.cpSync(path.join(assets.dependencies,'node_modules'),inside(payload,'plugins/browser-use/node/node_modules'),{recursive:true})
  copy(assets.node,'node/node.exe');copy(assets.license,'node/LICENSE')
  for (const file of filesUnder(path.join(assets.repo,'browser-extension/dist'))) if (!file.endsWith('.map')) copy(file,'browser-extension/dist/'+path.relative(path.join(assets.repo,'browser-extension/dist'),file))
  const archive = `sugaragent-browser-${assets.version}.zip`
  for (const suffix of ['', '.sha256']) copy(path.join(assets.repo,'outputs/browser-extension',archive+suffix),'outputs/browser-extension/'+archive+suffix)
  const catalog = spawnSync(path.join(payload,'node/node.exe'), ['--input-type=module','-e',
    'import {BrowserEngine} from "./plugins/browser-use/node/engine.mjs";const e=new BrowserEngine({generation:0});try{const t=await e.catalog();if(!t.some(x=>x.name==="browser_get_context")||!t.some(x=>x.name==="browser_click"))throw Error("Missing browser tools");console.log("BROWSER_CATALOG_OK "+t.length)}finally{await e.close()}'],
    {cwd:payload,encoding:'utf8',windowsHide:true,timeout:30000,env:{PATH:path.join(payload,'node'),SYSTEMROOT:process.env.SYSTEMROOT || '',WINDIR:process.env.WINDIR || '',TEMP:process.env.TEMP || '',TMP:process.env.TMP || '',PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:'1'}})
  if (catalog.status !== 0 || !catalog.stdout.includes('BROWSER_CATALOG_OK')) throw new Error('内置浏览器运行组件自检失败：'+(catalog.error?.message || catalog.stderr))
  log('· '+catalog.stdout.trim())
  const files = ['node','plugins/browser-use','browser-extension','outputs/browser-extension'].flatMap(relative=>filesUnder(path.join(payload,relative))).map(file=>({path:path.relative(payload,file).replaceAll('\\','/'),sha256:sha256(file),bytes:fs.statSync(file).size}))
  const info = {schemaVersion:1,version:assets.version,inputDigest:assets.inputDigest,lockDigest:assets.lockDigest,node:policy.node,files}
  fs.writeFileSync(path.join(payload,'browser-bundle.json'),JSON.stringify(info,null,2)+'\n')
  assertBrowserBundle(payload,{repo:assets.repo})
  log(`· 浏览器发布组件已就绪：${assets.version}，${files.length} 文件，Node ${policy.node.version}`)
  return info
}

async function main() {
  const at = process.argv.indexOf('--output')
  if (at < 0 || !process.argv[at+1]) throw new Error('请提供 --output <隔离载荷目录>')
  stageBrowserBundle(process.argv[at+1],await prepareBrowserAssets())
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch(error=>{console.error(error.message);process.exitCode=1})
