/**
 * Runtime config injected by webui.py into index.html before </head>.
 * Defaults allow Vite dev without the Python server for static smoke tests.
 *
 * 本文件被两处复用：
 *   1) ESM 消费者直接 import（保留行首 export 语法）；
 *   2) 页面运行时由 app/index.js 以 `?raw` 拼进共享 UI 作用域（拼装时去掉行首 export），
 *      因此函数体内可以 typeof 探测 sessionStore / currentSessionId 等作用域变量。
 * 约束：顶层只写函数声明，不要写 import / 其它可执行语句，否则 (2) 的拼装会失败。
 */
export function readRuntimeConfig(root = globalThis) {
  const w = root;
  if (typeof w.__CONTEXT_WINDOW__ !== 'number' || w.__CONTEXT_WINDOW__ <= 0) {
    w.__CONTEXT_WINDOW__ = 128000;
  }
  if (typeof w.__UI_LOG_TRUNCATE_KEEP_LINES__ !== 'number') {
    w.__UI_LOG_TRUNCATE_KEEP_LINES__ = 80;
  }
  if (typeof w.__WORK_DIR__ !== 'string') w.__WORK_DIR__ = '';
  if (typeof w.__SESSIONS_DIR__ !== 'string') w.__SESSIONS_DIR__ = '';
  w.MyAgentWorkspace = { context: getWorkspaceRequestContext, apiUrl: workspaceApiUrl,
    absolutePath: workspaceAbsolutePath, assetUrl: workspaceAssetUrl };
  return {
    contextWindow: w.__CONTEXT_WINDOW__,
    logTruncateKeepLines: w.__UI_LOG_TRUNCATE_KEEP_LINES__,
    workDir: w.__WORK_DIR__,
    sessionsDir: w.__SESSIONS_DIR__,
  };
}

/**
 * 路径根访问器：返回「当前激活会话」的工作目录（服务端 /sessions 的 work_dir）。
 * 取不到时（草稿态 / 未选会话 / 旧后端没有该字段）回退到注入的全局默认工作目录
 * window.__WORK_DIR__，保证原有「相对路径显示 / 打开文件 / 工作区链接」行为不变。
 */
export function getActiveWorkDir(root = globalThis) {
  const w = (root && typeof root === 'object') ? root : globalThis;
  let session = null;
  try {
    const sid = (typeof currentSessionId !== 'undefined' && currentSessionId)
      ? String(currentSessionId)
      : '';
    if (sid) session = workspaceSessionRecord(sid);
  } catch (e) {
    // 作用域变量不可用（ESM 消费方 / 页面初始化早期）→ 走全局默认目录
    session = null;
  }
  if (session) {
    const value = session.effective_work_dir || session.subagent_work_dir || session.git_worktree_path || session.work_dir;
    if (typeof value === 'string' && value) return value;
  }
  if (typeof currentSessionId === 'undefined' || !currentSessionId) {
    const draft = typeof newSessionWorkDir !== 'undefined' ? String(newSessionWorkDir || '') : '';
    if (draft) return draft;
    if (typeof pendingNewSession !== 'undefined' && pendingNewSession) {
      const pending = pendingNewSession.session || {};
      const value = pending.effective_work_dir || pending.subagent_work_dir || pending.git_worktree_path
        || pending.work_dir || pendingNewSession.workDir;
      if (value) return String(value);
    }
  }
  return (typeof w.__WORK_DIR__ === 'string') ? w.__WORK_DIR__ : '';
}

export function getWorkspaceRequestContext(sessionId) {
  const sid = typeof sessionId === 'string' ? sessionId
    : (typeof currentSessionId !== 'undefined' ? String(currentSessionId || '') : '');
  if (sid) return { session_id: sid };
  const root = getActiveWorkDir();
  return root ? { work_dir: root } : {};
}

export function workspaceSessionRecord(sessionId) {
  const sid = String(sessionId || '');
  if (typeof sessionStore !== 'undefined' && sessionStore && typeof sessionStore.get === 'function') {
    const session = sessionStore.get(sid);
    if (session) return session;
  }
  if (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) {
    const address = subagentCatalogStore.getAddress(sid);
    const entries = address ? subagentCatalogStore.entriesOf(address.parentSessionId) : [];
    const entry = entries.find(item => item.childId === sid);
    if (entry && entry.raw) return entry.raw;
  }
  return null;
}

export function workspaceApiUrl(endpoint, params = {}, context) {
  const query = new URLSearchParams(Object.assign({}, context || getWorkspaceRequestContext(), params));
  return endpoint + (query.toString() ? '?' + query : '');
}

export function workspaceAbsolutePath(path, context) {
  const raw = String(path || '').replace(/\\/g, '/');
  if (/^[A-Za-z]:\//.test(raw) || raw.startsWith('//')) return raw;
  let root = getActiveWorkDir();
  if (context && context.work_dir) root = context.work_dir;
  else if (context && context.session_id) {
    const session = workspaceSessionRecord(context.session_id);
    if (session) root = session.effective_work_dir || session.subagent_work_dir || session.git_worktree_path || session.work_dir || root;
  }
  root = String(root || '').replace(/\\/g, '/').replace(/\/+$/, '');
  if (root.startsWith('/') && (raw === root || raw.startsWith(root + '/'))) return raw;
  const rel = raw.replace(/^\/+/, '');
  if (/^(?:\.config|\.sugaragent)\/(?:history-media|attachments)\//.test(rel) || rel.startsWith('uploads/chat/')) {
    root = String(globalThis.__WORK_DIR__ || root).replace(/\\/g, '/').replace(/\/+$/, '');
  }
  return root ? root + '/' + rel : raw;
}

export function workspaceAssetUrl(path, context) {
  const ctx = context || getWorkspaceRequestContext();
  const base = ctx.session_id ? '/api/sessions/' + encodeURIComponent(ctx.session_id) + '/workspace-assets/' : '/api/workspace-assets/';
  return base + workspaceAbsolutePath(path, ctx).split('/').map(encodeURIComponent).join('/');
}
