(function () {
  'use strict';
  if (localStorage.getItem('myagent-language') !== 'en') return;
  var map = {
    '会话列表': 'Session list', '未连接': 'Disconnected', '新建会话': 'New session', '移除此设备': 'Remove this device',
    '退出设备': 'Disconnect device', '选择一个会话': 'Select a session', '输入消息…': 'Enter a message…',
    '停止': 'Stop', '发送': 'Send', '连接到这台电脑': 'Connect to this computer',
    '先在电脑本机创建一次性配对码，再在这里输入。浏览器凭证会存入 HttpOnly Cookie，页面脚本无法读取。': 'Create a one-time pairing code on the computer, then enter it here. Browser credentials are stored in an HttpOnly cookie and cannot be read by page scripts.',
    '设备名称': 'Device name', '配对': 'Pair', '正在配对…': 'Pairing…', '配对失败': 'Pairing failed',
    '连接中…': 'Connecting…', '已连接': 'Connected', '已断线': 'Disconnected', '连接错误': 'Connection error',
    '连接不可用': 'Connection unavailable', '请求超时': 'Request timed out', '连接已断开': 'Connection closed',
    '请求失败': 'Request failed', '需要确认': 'Confirmation required', '工具请求': 'Tool request', '允许': 'Allow', '拒绝': 'Deny',
    '上下文摘要': 'Context summary', '上下文裁剪': 'Context trimming', '上下文压缩已完成': 'Context compression completed',
    '上下文窗口已满，开始压缩': 'Context window full; starting compression', '正在思考中...': 'Thinking...', '执行中...': 'Running...', '执行结果': 'Result',
    '任务已由用户中断。': 'Task interrupted by the user.', '任务已由用户中断（父会话）。': 'Task interrupted by the user (parent session)',
    '本机网络已恢复，正在继续任务…': 'The local network is back; continuing the task…', '本机仍处于离线状态，Agent 正在沉睡并等待网络恢复…': 'The local machine is still offline; the Agent is sleeping until the network recovers…',
    '确认放宽工作区的 Shell': 'Confirm relaxed-workspace Shell access', '确认网络下载': 'Confirm network download',
    '将执行的大致命令如下，请确认是否允许：': 'The approximate command to run is below. Confirm whether to allow it:',
    '将把远程文件写入工作区指定路径。': 'The remote file will be written to the specified workspace path.',
    'URL：': 'URL:', '保存为（工作区内）：': 'Save as (inside workspace):', '（未指定）': '(not specified)',
    '工具执行异常：': 'Tool execution error: ', '工具执行异常: ': 'Tool execution error: ', '未知工具：': 'Unknown tool: ',
    '待办更新失败：': 'Todo update failed: ', 'MCP 调用异常：': 'MCP call error: ', 'subagent 执行异常：': 'Subagent execution error: '
  };
  var attrs = ['aria-label', 'title', 'placeholder'];
  var contentSelector = '#sessions [data-i18n-skip],#messages [data-i18n-skip],[data-i18n-skip]';
  var textOriginal = new WeakMap(), attrOriginal = new WeakMap();
  function tr(value) {
    var s = String(value == null ? '' : value);
    if (map[s]) return map[s];
    return s.replace(/^文件“(.+)”超过 (.+) 限制。$/, 'File “$1” exceeds the $2 limit.')
      .replace(/^请求失败：(.+)$/, 'Request failed: $1')
      .replace(/【上下文窗口已满，开始压缩】/g, '[Context window full; starting compression]')
      .replace(/【上下文压缩已完成】/g, '[Context compression completed]')
      .replace(/【上下文摘要】/g, '[Context summary]')
      .replace(/【上下文裁剪】/g, '[Context trimming]')
      .replace(/【要点】/g, '[Key points]')
      .replace(/上下文窗口已满，开始压缩/g, 'Context window full; starting compression')
      .replace(/上下文压缩已完成/g, 'Context compression completed')
      .replace(/正在进行上下文裁剪以控制 token（可能需数秒，请稍候）…/g, 'Trimming context to control tokens (this may take a few seconds; please wait)…')
      .replace(/正在进行上下文裁剪（可能需数秒，请稍候）…/g, 'Trimming context (this may take a few seconds; please wait)…')
      .replace(/摘要模型仍在生成或等待响应中，请稍候…/g, 'The summary model is still generating or waiting for a response; please wait…')
      .replace(/模型仍在更新要点或等待响应中，请稍候…/g, 'The model is still updating key points or waiting for a response; please wait…')
      .replace(/已完成上下文裁剪与摘要以控制长度/g, 'Context trimming and summarization completed to control length')
      .replace(/已完成上下文裁剪以控制长度/g, 'Context trimming completed to control length')
      .replace(/正在分析上下文并准备本地裁剪…/g, 'Analyzing context and preparing local trimming…')
      .replace(/正在执行本地裁剪与微压…/g, 'Performing local trimming and micro-compression…')
      .replace(/已对非关键信息进行裁剪/g, 'Non-critical information trimmed')
      .replace(/裁剪后仍超限，开始生成历史摘要…/g, 'Still over the limit after trimming; generating a history summary…')
      .replace(/当前上下文无需进一步裁剪或摘要/g, 'The current context needs no further trimming or summarization')
      .replace(/【自动·长度策略】/g, '[Automatic length policy]')
      .replace(/【context_manage·compact】/g, '[context_manage·compact]')
      .replace(/【安全确认】用户已允许：(.+)/g, '[Safety confirmation] User allowed: $1')
      .replace(/【安全确认】用户已拒绝执行（已跳过）。\s*(.+)/g, '[Safety confirmation] User denied execution (skipped): $1')
      .replace(/^Todo 计划已连续 (\d+) 轮未更新，已插入更新提醒$/g, 'The Todo plan has not been updated for $1 rounds; an update reminder was inserted')
      .replace(/^网络连接失败，正在重连（第 (\d+) 次，(.+)s 后重试）\.\.\.$/g, 'Network connection failed; reconnecting (attempt $1, retrying in $2s)…')
      .replace(/^检测到本机网络已断开，Agent 进入沉睡状态并等待网络恢复…$/g, 'The local network is disconnected; the Agent is sleeping until it recovers…')
      .replace(/^工具执行异常：(.+)$/g, 'Tool execution error: $1')
      .replace(/^工具执行异常:\s*(.+)$/g, 'Tool execution error: $1')
      .replace(/^未知工具：(.+)$/g, 'Unknown tool: $1')
      .replace(/^待办更新失败：(.+)$/g, 'Todo update failed: $1')
      .replace(/^MCP 调用异常：(.+)$/g, 'MCP call error: $1')
      .replace(/^subagent 执行异常：(.+)$/g, 'Subagent execution error: $1')
      .replace(/^模型未输出最终内容，正在重试（(\d+)\/(\d+)）$/g, 'The model did not produce a final response; retrying ($1/$2)')
      .replace(/^模型输出达到输出 token 上限，已丢弃半截工具调用并重试（(\d+)\/(\d+)）$/g, 'Model output reached the output-token limit; the incomplete tool call was discarded and retried ($1/$2)')
      .replace(/^已清理临时文件 (\d+) 个（已移入 \.trash）$/g, 'Cleaned up $1 temporary files (moved to .trash)')
      .replace(/执行中\.\.\./g, 'Running...')
      .replace(/执行结果/g, 'Result')
      .replace(/正在思考中\.\.\./g, 'Thinking...');
  }
  function walk(root) {
    var els = [];
    if (root && root.nodeType === 1) els.push(root);
    if (root && root.querySelectorAll) els = els.concat(Array.from(root.querySelectorAll('*')));
    els.forEach(function (el) {
      if (el.matches('script,style,code,pre')) return;
      if (el.matches(contentSelector) || el.closest(contentSelector)) return;
      var ao = attrOriginal.get(el) || {};
      attrs.forEach(function (attr) {
        if (!el.hasAttribute(attr)) return;
        if (!(attr in ao)) ao[attr] = el.getAttribute(attr);
        el.setAttribute(attr, tr(ao[attr]));
      });
      attrOriginal.set(el, ao);
      Array.from(el.childNodes).forEach(function (node) {
        if (node.nodeType !== 3 || !node.nodeValue.trim()) return;
        if (!textOriginal.has(node)) textOriginal.set(node, node.nodeValue);
        var original = textOriginal.get(node), trimmed = original.trim(), translated = tr(trimmed);
        node.nodeValue = original.replace(trimmed, translated);
      });
    });
  }
  document.documentElement.lang = 'en';
  walk(document.body);
  new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType === 1) walk(node);
        else if (node.parentElement) walk(node.parentElement);
      });
      if (mutation.type === 'characterData' && mutation.target.parentElement) walk(mutation.target.parentElement);
    });
  }).observe(document.body, { childList: true, subtree: true, characterData: true });
}());
