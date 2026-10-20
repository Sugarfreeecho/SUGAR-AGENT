'use strict'

const http = require('node:http')
const path = require('node:path')

/** 路径仍由后端校验；系统交互由拥有前台窗口的 Electron 进程执行。 */
async function openWorkspacePath({ baseUrl, shell, log }, payload) {
  try {
    if (!payload || typeof payload.rel !== 'string' || !payload.rel.trim()
        || payload.rel.length > 32768 || typeof payload.directory !== 'boolean'
        || ['session_id', 'work_dir'].some(key => payload[key] !== undefined
          && (typeof payload[key] !== 'string' || payload[key].length > 32768))) {
      return { ok: false, error: '无效的路径打开请求' }
    }
    const url = new URL('/api/open-workspace-dir', baseUrl)
    for (const key of ['rel', 'session_id', 'work_dir']) {
      if (payload[key]) url.searchParams.set(key, payload[key])
    }
    url.searchParams.set('probe', '1')
    const validated = await new Promise((resolve, reject) => {
      const request = http.get(url, { timeout: 6500 }, response => {
        let body = ''
        response.setEncoding('utf8')
        response.on('data', chunk => {
          body += chunk
          if (body.length > 65536) response.destroy(new Error('路径校验响应过大'))
        })
        response.on('error', reject)
        response.on('end', () => {
          try {
            const result = JSON.parse(body)
            if (response.statusCode !== 200 || result.ok !== true) {
              reject(new Error(result.error || result.detail || '路径校验失败'))
            } else if (typeof result.path !== 'string' || !path.isAbsolute(result.path)
                || typeof result.is_dir !== 'boolean') {
              reject(new Error('路径校验响应异常'))
            } else resolve(result)
          } catch (error) { reject(error) }
        })
      })
      request.on('timeout', () => request.destroy(new Error('路径校验超时')))
      request.on('error', reject)
    })
    // 后台 Python 的 os.startfile 不拥有用户点击所在进程的前台资格。
    // 文件定位使用系统 API，避免 explorer /select 的参数解析与重复窗口问题。
    if (payload.directory && !validated.is_dir) {
      shell.showItemInFolder(validated.path)
    } else {
      const error = await shell.openPath(validated.path)
      if (error) throw new Error(error)
    }
    return { ok: true, path: validated.path }
  } catch (error) {
    log(`系统路径打开失败：${error.message}`)
    return { ok: false, error: error.message }
  }
}

module.exports = { openWorkspacePath }
