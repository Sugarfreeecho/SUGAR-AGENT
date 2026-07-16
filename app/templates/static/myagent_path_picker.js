/**
 * General Agent 本机路径选择：调用 /api/pick-path，为配置项与聊天输入附加浏览按钮。
 */
(function (global) {
  'use strict';

  var MAX_CHAT_UPLOAD_FILE_BYTES = 100 * 1024 * 1024;
  var MAX_CHAT_UPLOAD_TOTAL_BYTES = 200 * 1024 * 1024;

  var FOLDER_SVG =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path>' +
    '</svg>';

  function injectStyles() {
    if (document.getElementById('myagent-path-picker-styles')) return;
    var st = document.createElement('style');
    st.id = 'myagent-path-picker-styles';
    st.textContent =
      '.path-input-row{display:flex;align-items:stretch;gap:0.35rem;width:100%;}' +
      '.path-input-row>.ip,.path-input-row>.tx,.path-input-row>input[type="text"],.path-input-row>input:not([type]){flex:1;min-width:0;}' +
      '.path-browse-btn{flex-shrink:0;width:2.35rem;padding:0;border:1px solid var(--border-glass,rgba(255,255,255,.08));' +
      'border-radius:var(--radius-sm,8px);background:var(--surface-glass2,rgba(40,40,60,.94));color:var(--text-secondary,#a6adc8);' +
      'cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:color .18s,border-color .18s,background .18s;}' +
      '.path-browse-btn:hover{color:var(--text-primary,#cdd6f4);border-color:var(--border-brand-accent,rgba(124,111,247,.35));background:rgba(108,92,231,.12);}' +
      '.path-browse-btn:disabled{opacity:.45;cursor:not-allowed;}' +
      '.path-browse-btn--ghost{background:transparent;border-color:transparent;box-shadow:none;width:2.1rem;}' +
      '.path-browse-btn--ghost:hover{background:rgba(108,92,231,.1);border-color:transparent;color:var(--accent-2,#d4b8fc);}' +
      '.input-wrapper .path-browse-btn--ghost{align-self:center;margin-right:-0.15rem;}' +
      '.input-wrapper.is-file-uploading{border-color:rgba(99,102,241,.52);}' +
      '.chat-upload-status{box-sizing:border-box;width:100%;margin:.38rem 0 0;padding:.42rem .58rem;border:1px solid rgba(99,102,241,.22);border-radius:10px;background:rgba(99,102,241,.08);color:var(--text-secondary,#a6adc8);font-size:.72rem;}' +
      '.chat-upload-status-row{display:flex;align-items:center;gap:.5rem;}' +
      '.chat-upload-status-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' +
      '.chat-upload-cancel{flex:none;border:0;background:transparent;color:var(--accent-2,#d4b8fc);font:inherit;font-weight:700;cursor:pointer;padding:.08rem .2rem;}' +
      '.chat-upload-progress{height:4px;margin-top:.36rem;border-radius:999px;overflow:hidden;background:rgba(255,255,255,.1);}' +
      '.chat-upload-progress-bar{display:block;width:0;height:100%;border-radius:inherit;background:linear-gradient(90deg,#6366f1,#a78bfa);transition:width .12s linear;}';
    document.head.appendChild(st);
  }

  async function pickPath(kind, initial, multiple) {
    var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, 50000) : null;
    var r;
    try {
      r = await fetch('/api/pick-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ kind: kind || 'directory', initial: initial || '', multiple: !!multiple }),
        signal: controller ? controller.signal : undefined,
      });
    } finally {
      if (timer) clearTimeout(timer);
    }
    var j = await r.json().catch(function () {
      return { ok: false, error: '请求失败' };
    });
    if (!r.ok || !j.ok) {
      if (j && j.cancelled) return null;
      var err = (j && j.error) || '无法打开选择对话框';
      if (/取消|cancelled|800704c7|2147023673/i.test(err)) return null;
      throw new Error(err);
    }
    if (multiple) return Array.isArray(j.paths) ? j.paths : (j.path ? [j.path] : []);
    return j.path || null;
  }

  async function runPick(btn, kind, initial, onPicked, multiple) {
    btn.disabled = true;
    try {
      var p = await pickPath(kind, initial || '', !!multiple);
      if (onPicked) onPicked(p);
    } catch (e) {
      return;
    } finally {
      btn.disabled = false;
    }
  }

  function quotePickedPath(p) {
    var s = String(p || '').trim();
    if (!s) return '';
    if ((s.charAt(0) === '"' && s.charAt(s.length - 1) === '"')
        || (s.charAt(0) === "'" && s.charAt(s.length - 1) === "'")) {
      s = s.slice(1, -1);
    }
    return '"' + s.replace(/"/g, '\\"') + '"';
  }

  function wrapInputWithBrowse(input, kind, title) {
    if (!input || input.dataset.pathBrowseWrapped === '1') return input;
    injectStyles();
    var row = document.createElement('div');
    row.className = 'path-input-row';
    var parent = input.parentNode;
    if (!parent) return input;
    parent.insertBefore(row, input);
    row.appendChild(input);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'path-browse-btn';
    btn.innerHTML = FOLDER_SVG;
    var tipText = title || '浏览路径';
    btn.setAttribute('aria-label', tipText);
    if (typeof bindUiHoverTip === 'function') {
      btn.setAttribute('data-ui-tip', tipText);
      btn.removeAttribute('title');
      bindUiHoverTip(btn);
    } else {
      btn.title = tipText;
    }

    btn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var fixedKind = input.getAttribute('data-path-kind') || kind;
      if (fixedKind !== 'file' && fixedKind !== 'directory') {
        fixedKind = 'directory';
      }
      runPick(btn, fixedKind, input.value || '', function (p) {
        if (!p) return;
        var nextPath = Array.isArray(p) ? (p[0] || '') : String(p);
        if (!nextPath) return;
        input.value = nextPath;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
    row.appendChild(btn);
    input.dataset.pathBrowseWrapped = '1';
    return input;
  }

  function insertPathAtCursor(textarea, p) {
    var ins = quotePickedPath(p);
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.slice(0, start);
    var after = textarea.value.slice(end);
    if (before.length && !/\s$/.test(before)) ins = ' ' + ins;
    if (after.length && !/^\s/.test(after)) ins = ins + ' ';
    textarea.value = before + ins + after;
    var pos = before.length + ins.length;
    textarea.selectionStart = textarea.selectionEnd = pos;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.focus();
  }

  function insertTextAtCursor(textarea, text) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.slice(0, start);
    var after = textarea.value.slice(end);
    var ins = String(text || '');
    if (before.length && !/\s$/.test(before)) ins = ' ' + ins;
    if (after.length && !/^\s/.test(after)) ins = ins + ' ';
    textarea.value = before + ins + after;
    var pos = before.length + ins.length;
    textarea.selectionStart = textarea.selectionEnd = pos;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.focus();
  }

  function formatBytes(n) {
    n = Number(n || 0);
    if (!isFinite(n) || n <= 0) return '';
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return Math.round(n / 102.4) / 10 + ' KB';
    if (n < 1024 * 1024 * 1024) return Math.round(n / 104857.6) / 10 + ' MB';
    return Math.round(n / 107374182.4) / 10 + ' GB';
  }

  function validatedChatUploadList(files) {
    var list = Array.prototype.slice.call(files || []).filter(Boolean);
    var total = 0;
    list.forEach(function (file) {
      var size = Number(file && file.size || 0);
      if (size > MAX_CHAT_UPLOAD_FILE_BYTES) {
        throw new Error('文件“' + String(file && file.name || '未命名文件') + '”超过 ' + formatBytes(MAX_CHAT_UPLOAD_FILE_BYTES) + ' 限制。');
      }
      total += Math.max(0, size);
    });
    if (total > MAX_CHAT_UPLOAD_TOTAL_BYTES) {
      throw new Error('本次上传总大小超过 ' + formatBytes(MAX_CHAT_UPLOAD_TOTAL_BYTES) + ' 限制。');
    }
    return list;
  }

  function uploadChatFiles(files, options) {
    var list;
    try {
      list = validatedChatUploadList(files);
    } catch (error) {
      return Promise.reject(error);
    }
    if (!list.length) return Promise.resolve([]);
    options = options || {};
    var form = new FormData();
    list.forEach(function (file) { form.append('files', file, file.name || 'upload.bin'); });
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/upload-chat-files', true);
      xhr.withCredentials = true;
      xhr.timeout = 10 * 60 * 1000;
      if (xhr.upload && typeof options.onProgress === 'function') {
        xhr.upload.onprogress = function (event) {
          options.onProgress(event.loaded || 0, event.lengthComputable ? event.total : 0);
        };
      }
      if (typeof options.registerAbort === 'function') {
        options.registerAbort(function () { xhr.abort(); });
      }
      xhr.onload = function () {
        var data;
        try { data = JSON.parse(xhr.responseText || '{}'); }
        catch (_error) { data = { ok: false, error: '上传失败' }; }
        if (xhr.status < 200 || xhr.status >= 300 || !data.ok) {
          reject(new Error((data && data.error) || '上传失败'));
          return;
        }
        resolve(Array.isArray(data.files) ? data.files : []);
      };
      xhr.onerror = function () { reject(new Error('上传失败：网络连接异常。')); };
      xhr.ontimeout = function () { reject(new Error('上传超时，请重试。')); };
      xhr.onabort = function () {
        var error = new Error('上传已取消。');
        error.name = 'AbortError';
        reject(error);
      };
      xhr.send(form);
    });
  }

  function currentChatSessionId() {
    try {
      return typeof currentSessionId !== 'undefined' ? String(currentSessionId || '') : '';
    } catch (_error) {
      return '';
    }
  }

  function appendUploadedText(textarea, text, targetSessionId) {
    if (!text) return;
    var activeSessionId = currentChatSessionId();
    if (targetSessionId && activeSessionId && targetSessionId !== activeSessionId) {
      try {
        if (typeof persistInputDraft === 'function') {
          var existing = '';
          if (typeof draftBySession !== 'undefined'
              && Object.prototype.hasOwnProperty.call(draftBySession, targetSessionId)) {
            existing = String(draftBySession[targetSessionId] || '');
          } else if (typeof readStoredInputDraft === 'function') {
            existing = String(readStoredInputDraft(targetSessionId) || '');
          }
          persistInputDraft(targetSessionId, existing.trim() ? (existing + ' ' + text) : text);
          return;
        }
      } catch (_error) { /* fall through only when session draft storage is unavailable */ }
      return;
    }
    insertTextAtCursor(textarea, text);
  }

  function insertUploadedFiles(textarea, files, options) {
    var targetSessionId = currentChatSessionId();
    return uploadChatFiles(files, options).then(function (uploaded) {
      var text = uploaded.map(function (item) {
        return quotePickedPath(item.path || item.rel || item.name);
      }).join(' ');
      appendUploadedText(textarea, text, targetSessionId);
    });
  }

  function dispatchUploadError(textarea, error) {
    console.error('chat file upload failed:', error);
    textarea.dispatchEvent(new CustomEvent('myagent:file-paste-error', {
      bubbles: true,
      detail: { message: String((error && error.message) || error || '上传失败') }
    }));
  }

  function setChatUploadBusy(textarea, busy) {
    var wrapper = textarea.closest ? textarea.closest('.input-wrapper') : null;
    if (busy) textarea.dataset.fileUploadBusy = '1';
    else delete textarea.dataset.fileUploadBusy;
    if (wrapper) {
      wrapper.classList.toggle('is-file-uploading', !!busy);
      if (busy) wrapper.setAttribute('aria-busy', 'true');
      else wrapper.removeAttribute('aria-busy');
    }
    textarea.dispatchEvent(new CustomEvent('myagent:file-upload-state', {
      bubbles: true,
      detail: { busy: !!busy }
    }));
  }

  function createChatUploadStatus(textarea, files) {
    var wrapper = textarea.closest ? textarea.closest('.input-wrapper') : null;
    var panel = document.createElement('div');
    panel.className = 'chat-upload-status';
    panel.setAttribute('role', 'status');
    panel.innerHTML = '<div class="chat-upload-status-row"><span class="chat-upload-status-label"></span><button type="button" class="chat-upload-cancel">取消</button></div>' +
      '<div class="chat-upload-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span class="chat-upload-progress-bar"></span></div>';
    panel.querySelector('.chat-upload-status-label').textContent = '正在上传 ' + files.length + ' 个文件… 0%';
    if (wrapper && wrapper.parentNode) wrapper.parentNode.insertBefore(panel, wrapper.nextSibling);
    return panel;
  }

  function startChatFileUpload(textarea, files) {
    var list;
    try {
      list = validatedChatUploadList(files);
    } catch (error) {
      dispatchUploadError(textarea, error);
      return Promise.reject(error);
    }
    if (!list.length) return Promise.resolve();
    if (textarea._myAgentActiveUpload) {
      var busyError = new Error('已有文件正在上传，请等待完成或先取消。');
      dispatchUploadError(textarea, busyError);
      return Promise.reject(busyError);
    }
    var panel = createChatUploadStatus(textarea, list);
    var label = panel.querySelector('.chat-upload-status-label');
    var progress = panel.querySelector('.chat-upload-progress');
    var bar = panel.querySelector('.chat-upload-progress-bar');
    var cancel = panel.querySelector('.chat-upload-cancel');
    var abortUpload = null;
    var state = textarea._myAgentActiveUpload = {};
    setChatUploadBusy(textarea, true);
    cancel.addEventListener('click', function () {
      cancel.disabled = true;
      label.textContent = '正在取消上传…';
      if (abortUpload) abortUpload();
    });
    return insertUploadedFiles(textarea, list, {
      registerAbort: function (abort) { abortUpload = abort; },
      onProgress: function (loaded, total) {
        if (textarea._myAgentActiveUpload !== state) return;
        var percent = total > 0 ? Math.min(100, Math.round(loaded * 100 / total)) : 0;
        label.textContent = '正在上传 ' + list.length + ' 个文件… ' + percent + '%';
        bar.style.width = percent + '%';
        progress.setAttribute('aria-valuenow', String(percent));
      }
    }).catch(function (error) {
      if (!error || error.name !== 'AbortError') dispatchUploadError(textarea, error);
      throw error;
    }).finally(function () {
      if (textarea._myAgentActiveUpload === state) {
        delete textarea._myAgentActiveUpload;
        setChatUploadBusy(textarea, false);
      }
      if (panel.parentNode) panel.parentNode.removeChild(panel);
    });
  }

  function clipboardFilesFromEvent(ev) {
    var data = ev && ev.clipboardData;
    if (!data) return [];
    var files = [];
    var items = Array.prototype.slice.call(data.items || []);
    items.forEach(function (item) {
      if (!item || item.kind !== 'file' || typeof item.getAsFile !== 'function') return;
      var file = item.getAsFile();
      if (file) files.push(file);
    });
    if (!files.length) files = Array.prototype.slice.call(data.files || []).filter(Boolean);
    return files.map(function (file, index) {
      if (String(file && file.name || '').trim()) return file;
      var subtype = String(file && file.type || '').split('/')[1] || 'bin';
      subtype = subtype.replace(/[^a-z0-9.+-]/gi, '') || 'bin';
      var name = 'clipboard-' + Date.now() + '-' + (index + 1) + '.' + subtype;
      try {
        return new File([file], name, { type: file.type || 'application/octet-stream', lastModified: Date.now() });
      } catch (_error) {
        return file;
      }
    });
  }

  function clipboardHasUsableText(ev) {
    var data = ev && ev.clipboardData;
    if (!data || typeof data.getData !== 'function') return false;
    try {
      return String(data.getData('text/plain') || '').trim().length > 0;
    } catch (_error) {
      return false;
    }
  }

  function bindPasteUpload(textarea) {
    if (!textarea || textarea.dataset.filePasteBound === '1') return;
    textarea.dataset.filePasteBound = '1';
    textarea.addEventListener('paste', function (ev) {
      // Office applications put a bitmap preview on the clipboard alongside
      // copied text. Prefer the text and leave the textarea's native paste
      // behavior intact; upload files only when the clipboard has no text.
      if (clipboardHasUsableText(ev)) return;
      var files = clipboardFilesFromEvent(ev);
      if (!files.length) return;
      ev.preventDefault();
      startChatFileUpload(textarea, files).catch(function () {});
    });
  }

  function attachChatPicker(button, textarea) {
    if (!button || !textarea) return;
    injectStyles();
    bindPasteUpload(textarea);
    button.classList.add('path-browse-btn', 'path-browse-btn--ghost');
    button.innerHTML = FOLDER_SVG;
    button.setAttribute('aria-label', '选择文件');
    button.setAttribute('data-ui-tip', '选择文件');
    button.dataset.silentPickerUnavailable = '1';
    button.removeAttribute('title');

    button.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var initial = (global && typeof global.__WORK_DIR__ === 'string') ? global.__WORK_DIR__ : '';
      runPick(button, 'file', initial, function (p) {
        var paths = Array.isArray(p) ? p : (p ? [p] : []);
        if (!paths.length) return;
        var text = paths.map(function (item) { return quotePickedPath(item); }).join(' ');
        insertTextAtCursor(textarea, text);
      }, false);
    });
  }

  function scan(root) {
    root = root || document;
    var nodes = root.querySelectorAll('[data-path-kind]');
    var i;
    for (i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var kind = el.getAttribute('data-path-kind');
      if (kind === 'file' || kind === 'directory') {
        wrapInputWithBrowse(el, kind);
      }
    }
  }

  global.MyAgentPathPicker = {
    pickPath: pickPath,
    wrapInputWithBrowse: wrapInputWithBrowse,
    attachChatPicker: attachChatPicker,
    uploadChatFiles: uploadChatFiles,
    insertUploadedFiles: insertUploadedFiles,
    startChatFileUpload: startChatFileUpload,
    clipboardFilesFromEvent: clipboardFilesFromEvent,
    clipboardHasUsableText: clipboardHasUsableText,
    scan: scan,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      scan(document);
    });
  } else {
    scan(document);
  }
})(typeof window !== 'undefined' ? window : globalThis);
