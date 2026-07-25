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
    '请求失败': 'Request failed', '需要确认': 'Confirmation required', '工具请求': 'Tool request', '允许': 'Allow', '拒绝': 'Deny'
  };
  var attrs = ['aria-label', 'title', 'placeholder'];
  var textOriginal = new WeakMap(), attrOriginal = new WeakMap();
  function tr(value) {
    var s = String(value == null ? '' : value);
    if (map[s]) return map[s];
    return s.replace(/^文件“(.+)”超过 (.+) 限制。$/, 'File “$1” exceeds the $2 limit.')
      .replace(/^请求失败：(.+)$/, 'Request failed: $1');
  }
  function walk(root) {
    var els = [];
    if (root && root.nodeType === 1) els.push(root);
    if (root && root.querySelectorAll) els = els.concat(Array.from(root.querySelectorAll('*')));
    els.forEach(function (el) {
      if (el.matches('script,style,code,pre')) return;
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
