'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')
const packaging = path.resolve(__dirname, '..')

function buildStartupLauncher({ output, target, payload, workDir }) {
  if (process.platform !== 'win32') throw new Error('Windows 启动入口需要在 Windows 上构建')
  const compiler = path.join(process.env.WINDIR || 'C:\\Windows', 'Microsoft.NET', 'Framework64', 'v4.0.30319', 'csc.exe')
  if (!fs.existsSync(compiler)) throw new Error(`缺少 Windows .NET Framework 编译器：${compiler}`)
  fs.mkdirSync(workDir, { recursive: true })
  const settings = path.join(workDir, 'launcher-target.txt')
  fs.writeFileSync(settings, target || '', 'utf8')
  const args = ['/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll', '/reference:System.Web.Extensions.dll',
    `/win32icon:${path.join(packaging, 'assets', 'app.ico')}`, `/out:${output}`,
    `/resource:${path.join(packaging, 'electron', 'sugar-logo.png')},BrandLogo`,
    `/resource:${settings},LauncherTarget`]
  if (payload) args.push(`/resource:${payload},PortablePayload`)
  args.push(path.join(packaging, 'native', 'StartupLauncher.cs'))
  const result = spawnSync(compiler, args, { windowsHide: true, encoding: 'utf8' })
  if (result.error || result.status !== 0) throw new Error(result.error ? result.error.message : result.stdout + result.stderr)
}

async function brandRuntimeExe(context, runtime) {
  // afterPack runs before electron-builder edits its primary exe. Swapping in
  // the launcher makes the runtime a secondary exe, which is otherwise only
  // signed. Explicitly apply the same icon/version/ProductName/LegalCopyright.
  await context.packager.signAndEditResources(runtime, context.arch, context.outDir,
    path.basename(runtime, '.exe'), context.packager.platformSpecificBuildOptions.requestedExecutionLevel)
}

async function installStartupLauncher(context) {
  const name = context.packager.appInfo.productFilename
  const entry = path.join(context.appOutDir, `${name}.exe`)
  const runtimeName = `${name}Runtime.exe`
  const runtime = path.join(context.appOutDir, runtimeName)
  fs.renameSync(entry, runtime)
  try {
    await brandRuntimeExe(context, runtime)
    buildStartupLauncher({ output: entry, target: runtimeName,
      workDir: path.join(packaging, 'build', 'native-launcher') })
  } catch (error) {
    if (fs.existsSync(entry)) fs.unlinkSync(entry)
    fs.renameSync(runtime, entry)
    throw error
  }
}

module.exports = { buildStartupLauncher, installStartupLauncher, brandRuntimeExe }
