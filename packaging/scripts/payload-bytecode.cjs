'use strict'

const fs = require('node:fs')
const path = require('node:path')

function scanBytecode(root) {
  const base = fs.realpathSync(root)
  if (!['payload', 'runtime'].includes(path.basename(base))) throw new Error('字节码检查仅用于桌面载荷目录')
  for (const name of ['workspace', '.config', '.sugaragent']) {
    if (fs.existsSync(path.join(base, name))) throw new Error(`拒绝处理含用户数据的载荷：${name}`)
  }
  const files = []
  const directories = []
  const stack = [base]
  while (stack.length) {
    const directory = stack.pop()
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name)
      if (entry.isSymbolicLink()) {
        if (entry.name === '__pycache__' || /\.py[co]$/i.test(entry.name)) throw new Error(`缓存路径含符号链接：${full}`)
        continue
      }
      if (entry.isDirectory()) {
        stack.push(full)
        if (entry.name === '__pycache__') directories.push(full)
      } else if (entry.isFile() && /\.py[co]$/i.test(entry.name)) {
        files.push(full)
      }
    }
  }
  return { base, files, directories }
}

function assertNoLooseBytecode(root) {
  const { files, directories } = scanBytecode(root)
  if (files.length || directories.length) {
    throw new Error(`载荷含 ${files.length} 个松散字节码文件、${directories.length} 个缓存目录；请重新准备载荷`)
  }
}

function cleanupPyc(root) {
  const { base, files, directories } = scanBytecode(root)
  const owned = target => {
    const relative = path.relative(base, fs.realpathSync(target))
    if (!relative || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
      throw new Error(`缓存清理目标超出载荷：${target}`)
    }
  }
  // Check all candidates before deleting anything. Bytecode-only modules are
  // code, not disposable caches; keep them for an explicit layout review.
  for (const file of files) {
    owned(file)
    const cache = path.basename(path.dirname(file)) === '__pycache__'
    const stem = path.basename(file).replace(/\.py[co]$/i, '').replace(/\.cpython-\d+(?:\.opt-\d+)?$/, '')
    const source = path.join(cache ? path.dirname(path.dirname(file)) : path.dirname(file), stem + '.py')
    if (!fs.existsSync(source)) throw new Error(`发现没有源码的字节码模块，不能作为缓存删除：${file}`)
  }
  for (const directory of directories) owned(directory)
  let bytes = 0
  for (const file of files) {
    bytes += fs.statSync(file).size
    fs.unlinkSync(file)
  }
  for (const directory of directories.sort((a, b) => b.length - a.length)) {
    // Non-recursive removal also protects unexpected non-cache contents.
    fs.rmdirSync(directory)
  }
  assertNoLooseBytecode(root)
  return { files: files.length, directories: directories.length, bytes }
}

module.exports = { cleanupPyc, assertNoLooseBytecode }
