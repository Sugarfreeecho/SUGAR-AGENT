/**
 * General Agent local path picker.
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
      '.path-input-row{display:flex;align-items:stretch;gap:.35rem;width:100%;}' +
      '.path-input-row>.ip,.path-input-row>.tx,.path-input-row>input[type="text"],.path-input-row>input:not([type]){flex:1;min-width:0;}' +
      '.path-browse-btn{flex-shrink:0;width:2.35rem;padding:0;border:1px solid var(--border-glass,rgba(255,255,255,.08));border-radius:var(--radius-sm,8px);background:var(--surface-glass2,rgba(40,40,60,.94));color:var(--text-secondary,#a6adc8);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:color .18s,border-color .18s,background .18s;}' +
      '.path-browse-btn:hover{color:var(--text-primary,#cdd6f4);border-color:var(--border-brand-accent,rgba(124,111,247,.35));background:rgba(108,92,231,.12);}' +
      '.path-browse-btn:disabled{opacity:.45;cursor:not-allowed;}' +
      '.path-browse-btn--ghost{background:transparent;border-color:transparent;box-shadow:none;width:2.1rem;}' +
      '.path-browse-btn--ghost:hover{background:rgba(108,92,231,.1);border-color:transparent;color:var(--accent-2,#d4b8fc);}' +
      '.input-wrapper .path-browse-btn--ghost{align-self:center;margin-right:-.15rem;}' +
      '.input-wrapper.is-drag-over{border-color:rgba(203,166,247,.62);box-shadow:0 0 0 3px rgba(203,166,247,.12),0 0 28px rgba(139,92,246,.18);}' +
      '.input-wrapper.is-file-uploading{border-color:rgba(99,102,241,.52);}' +
      '.chat-upload-status{box-sizing:border-box;width:100%;margin:.38rem 0 0;padding:.42rem .58rem;border:1px solid rgba(99,102,241,.22);border-radius:10px;background:rgba(99,102,241,.08);color:var(--text-secondary,#a6adc8);font-size:.72rem;}' +
      '.chat-upload-status-row{display:flex;align-items:center;gap:.5rem;}' +
      '.chat-upload-status-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' +
      '.chat-upload-cancel{flex:none;border:0;background:transparent;color:var(--accent-2,#d4b8fc);font:inherit;font-weight:700;cursor:pointer;padding:.08rem .2rem;}' +
      '.chat-upload-cancel:hover{color:var(--text-primary,#fff);}' +
      '.chat-upload-progress{height:4px;margin-top:.36rem;border-radius:999px;overflow:hidden;background:rgba(255,255,255,.1);}' +
      '.chat-upload-progress-bar{display:block;width:0;height:100%;border-radius:inherit;background:linear-gradient(90deg,#6366f1,#a78bfa);transition:width .12s linear;}' +
      '.workspace-file-popover{position:fixed;display:none;z-index:260;width:min(46rem,calc(100vw - 1.2rem));height:min(44rem,82vh);max-height:min(44rem,82vh);border:1px solid var(--border-glass,rgba(255,255,255,.08));border-radius:var(--radius-sm,8px);background:var(--surface-glass2,rgba(40,40,60,.96));box-shadow:var(--shadow-soft,0 18px 50px rgba(0,0,0,.34));overflow:hidden;backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);}' +
      '.workspace-file-popover.is-open{display:flex;flex-direction:column;}' +
      '.workspace-file-search{position:relative;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid var(--border-glass,rgba(255,255,255,.08));background:var(--surface-glass3,rgba(255,255,255,.035));color:var(--text-primary,#cdd6f4);padding:.56rem .72rem;font:inherit;font-size:.78rem;outline:none;}' +
      '.workspace-file-search::placeholder{color:var(--text-muted,#6c7086);}' +
      '.workspace-file-list{position:relative;flex:1;min-height:0;overflow:auto;padding:.36rem .38rem .2rem;}' +
      '.workspace-file-item{width:100%;display:grid;grid-template-columns:1.05rem minmax(0,1fr) auto;gap:.2rem .38rem;align-items:center;text-align:left;border:0;border-radius:8px;background:transparent;color:var(--text-secondary,#a6adc8);padding:.22rem .36rem;cursor:pointer;font:inherit;font-size:.74rem;}' +
      '.workspace-file-item:hover,.workspace-file-item.is-active{background:rgba(255,255,255,.055);color:var(--text-primary,#cdd6f4);}' +
      '.workspace-file-item.is-selected{background:rgba(var(--accent-rgb,137,180,250),.12);color:var(--text-primary,#cdd6f4);}' +
      '.workspace-file-check{width:.82rem;height:.82rem;border:1px solid var(--border-glass,rgba(255,255,255,.14));border-radius:4px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.62rem;line-height:1;background:transparent;}' +
      '.workspace-file-item.is-selected .workspace-file-check{background:rgb(var(--brand-accent-rgb,99,102,241));border-color:transparent;color:#fff;}' +
      '.workspace-file-dir-row{grid-template-columns:1.05rem minmax(0,1fr) auto;color:var(--text-primary,#cdd6f4);font-weight:650;}' +
      '.workspace-file-dir-row .workspace-file-tree{grid-column:2/3;}' +
      '.workspace-file-file-row{grid-template-columns:1.05rem minmax(0,1fr) auto;}' +
      '.workspace-file-tree{min-width:0;display:flex;align-items:center;gap:.24rem;}' +
      '.workspace-file-indent{flex:0 0 auto;width:var(--indent,0);}' +
      '.workspace-file-chevron{width:.8rem;min-width:.8rem;color:var(--text-muted,#6c7086);font-size:.72rem;text-align:center;border:0;background:transparent;padding:0;cursor:pointer;}' +
      '.workspace-file-icon{position:relative;width:.98rem;min-width:.98rem;height:.74rem;margin-top:.04rem;border-radius:3px;border:1px solid rgba(203,166,247,.28);background:linear-gradient(135deg,rgba(203,166,247,.18),rgba(99,102,241,.1));box-shadow:inset 0 .12rem .26rem rgba(255,255,255,.08);}' +
      '.workspace-file-icon:before{content:"";position:absolute;left:.06rem;right:.06rem;top:.12rem;height:.16rem;border-radius:999px;background:rgba(203,166,247,.34);}' +
      '.workspace-file-icon:after{content:"";position:absolute;left:.06rem;right:.06rem;bottom:.11rem;height:.24rem;border-radius:2px;background:rgba(99,102,241,.16);}' +
      '.workspace-file-icon.is-file{width:.82rem;min-width:.82rem;height:1rem;margin-top:0;border-radius:3px;background:transparent;border:1.5px solid rgba(166,173,200,.58);box-shadow:none;color:var(--text-muted,#6c7086);}' +
      '.workspace-file-icon.is-file:before{left:auto;right:-1.5px;top:-1.5px;width:.3rem;height:.3rem;border:0;border-left:1.5px solid rgba(166,173,200,.58);border-bottom:1.5px solid rgba(166,173,200,.58);border-radius:0 3px 0 3px;background:var(--surface-glass2,rgba(40,40,60,.94));}' +
      '.workspace-file-icon.is-file:after{display:none;}' +
      '.workspace-file-icon.is-folder-svg{width:1rem;min-width:1rem;height:1rem;margin-top:0;border:0;background:transparent;box-shadow:none;color:var(--text-muted,#6c7086);display:inline-flex;align-items:center;justify-content:center;}' +
      '.workspace-file-icon.is-folder-svg:before,.workspace-file-icon.is-folder-svg:after{display:none;}' +
      '.workspace-file-icon.is-folder-svg svg{width:1rem;height:1rem;display:block;}' +
      '.workspace-file-icon.is-image{border-color:rgba(45,212,191,.72);}' +
      '.workspace-file-icon.is-image:after{display:block;left:.12rem;right:.12rem;bottom:.15rem;height:.24rem;clip-path:polygon(0 100%,38% 38%,56% 66%,76% 24%,100% 100%);background:rgba(45,212,191,.72);}' +
      '.workspace-file-icon.is-audio{border-color:rgba(251,191,36,.76);}' +
      '.workspace-file-icon.is-audio:after{display:block;left:.17rem;right:auto;bottom:.18rem;width:.36rem;height:.4rem;border-radius:0;background:rgba(251,191,36,.76);clip-path:polygon(0 32%,45% 32%,100% 0,100% 100%,45% 68%,0 68%);}' +
      '.workspace-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.74rem;}' +
      '.workspace-file-dir{grid-column:2/-1;color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}' +
      '.workspace-file-meta{color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;}' +
      '.workspace-file-footer{position:relative;display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.42rem .52rem;border-top:1px solid var(--border-glass,rgba(255,255,255,.08));background:var(--surface-glass3,rgba(255,255,255,.025));font-size:.72rem;color:var(--text-muted,#6c7086);}' +
      '.workspace-file-outside{flex-shrink:0;border:1px solid var(--border-glass,rgba(255,255,255,.1));border-radius:8px;padding:.28rem .58rem;background:rgba(255,255,255,.035);color:var(--text-secondary,#a6adc8);font:inherit;font-size:.7rem;font-weight:700;cursor:pointer;transition:background .16s,border-color .16s,color .16s;}' +
      '.workspace-file-outside:hover{background:rgba(255,255,255,.07);border-color:var(--border-brand-accent,rgba(124,111,247,.35));color:var(--text-primary,#fff);}' +
      '.workspace-file-insert{border:0;border-radius:8px;padding:.34rem .62rem;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:.72rem;font-weight:700;cursor:pointer;}' +
      '.workspace-file-insert:disabled{opacity:.45;cursor:not-allowed;}' +
      '.workspace-file-empty{padding:1rem;text-align:center;color:var(--text-muted,#6c7086);font-size:.78rem;}' +
      '.theme-light .workspace-file-popover{background:rgba(255,255,255,.98);border-color:rgba(15,23,42,.1);box-shadow:0 18px 48px rgba(15,23,42,.14);}' +
      '.theme-light .workspace-file-search,.theme-light .workspace-file-footer{background:rgba(15,23,42,.025);}' +
      '.theme-light .workspace-file-item:hover,.theme-light .workspace-file-item.is-active{background:rgba(15,23,42,.05);}' +
      '.theme-light .workspace-file-outside{background:rgba(15,23,42,.025);}';
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
    var j = await r.json().catch(function () { return { ok: false, error: '请求失败' }; });
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
    if ((s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') ||
        (s.charAt(0) === "'" && s.charAt(s.length - 1) === "'")) {
      s = s.slice(1, -1);
    }
    return '"' + s.replace(/"/g, '\\"') + '"';
  }

  function fileIconTypeClass(name) {
    var ext = String(name || '').toLowerCase().split('.').pop() || '';
    if (/^(png|jpe?g|gif|webp|bmp|svg|tiff?|ico|avif)$/.test(ext)) return 'is-image';
    if (/^(mp3|wav|flac|aac|m4a|ogg|oga|opus|wma|aiff?)$/.test(ext)) return 'is-audio';
    return '';
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

  function formatBytes(n) {
    n = Number(n || 0);
    if (!isFinite(n) || n <= 0) return '';
    if (n < 1024) return n + ' B';
    if (n < 1024 * 1024) return Math.round(n / 102.4) / 10 + ' KB';
    if (n < 1024 * 1024 * 1024) return Math.round(n / 104857.6) / 10 + ' MB';
    return Math.round(n / 107374182.4) / 10 + ' GB';
  }

  async function fetchWorkspaceFiles(query, dir, signal) {
    var params = [];
    if (query) params.push('q=' + encodeURIComponent(query));
    else if (dir) params.push('dir=' + encodeURIComponent(dir));
    var url = '/api/workspace-files' + (params.length ? ('?' + params.join('&')) : '');
    var r = await fetch(url, { credentials: 'same-origin', signal: signal });
    var j = await r.json().catch(function () { return { ok: false, error: '读取工作区文件失败' }; });
    if (!r.ok || !j.ok) throw new Error((j && j.error) || '读取工作区文件失败');
    return Array.isArray(j.files) ? j.files : [];
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
      var remembered = Array.isArray(textarea._myAgentStructuredAttachments)
        ? textarea._myAgentStructuredAttachments.slice()
        : [];
      uploaded.forEach(function (item) {
        if (!item || !item.path) return;
        if (!remembered.some(function (existing) { return existing.path === item.path; })) {
          remembered.push({ path: item.path, name: item.name || '', size: Number(item.size || 0) });
        }
      });
      textarea._myAgentStructuredAttachments = remembered;
      var text = uploaded.map(function (item) {
        return quotePickedPath(item.path || item.rel || item.name);
      }).join(' ');
      appendUploadedText(textarea, text, targetSessionId);
    });
  }

  function chatAttachments(textarea) {
    return Array.isArray(textarea && textarea._myAgentStructuredAttachments)
      ? textarea._myAgentStructuredAttachments.slice()
      : [];
  }

  function clearChatAttachments(textarea) {
    if (textarea) textarea._myAgentStructuredAttachments = [];
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
    var count = files.length;
    panel.querySelector('.chat-upload-status-label').textContent = '正在上传 ' + count + ' 个文件… 0%';
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

  function createWorkspaceFilePanel(textarea, uploadOutsideFiles) {
    var panel = document.createElement('div');
    panel.className = 'workspace-file-popover';
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML =
      '<input class="workspace-file-search" type="text" autocomplete="off" spellcheck="false" placeholder="搜索工作区文件（↑↓ 移动 · Enter 选择 · Esc 关闭）">' +
      '<div class="workspace-file-list" role="listbox"></div>' +
      '<div class="workspace-file-footer"><span class="workspace-file-count">未选择文件</span><button type="button" class="workspace-file-outside">选择工作目录外文件</button></div>';
    document.body.appendChild(panel);

    var search = panel.querySelector('.workspace-file-search');
    var list = panel.querySelector('.workspace-file-list');
    var countLabel = panel.querySelector('.workspace-file-count');
    var outsideBtn = panel.querySelector('.workspace-file-outside');
    var state = {
      items: [],
      visible: [],
      active: 0,
      open: false,
      debounce: null,
      controller: null,
      selected: Object.create(null),
      expanded: Object.create(null),
      loadedDirs: Object.create(null),
      itemMap: Object.create(null),
    };

    function positionPanel() {
      var anchor = textarea.closest ? textarea.closest('.input-wrapper') : textarea;
      var rect = anchor.getBoundingClientRect();
      var gap = 8;
      var width = Math.min(Math.max(rect.width, 520), window.innerWidth - 16);
      var left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      var titlebar = document.querySelector('.titlebar');
      var titlebarBottom = titlebar ? titlebar.getBoundingClientRect().bottom : 44;
      var rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
      var maxHeight = Math.min(44 * rootSize, window.innerHeight * 0.82);
      var availableAbove = Math.max(1, rect.top - titlebarBottom - gap);
      var height = Math.min(maxHeight, availableAbove);
      var top = rect.top - height - gap;
      if (height < 96) {
        var availableBelow = Math.max(1, window.innerHeight - rect.bottom - gap - 8);
        height = Math.min(maxHeight, availableBelow);
        top = rect.bottom + gap;
      }
      panel.style.left = left + 'px';
      panel.style.top = Math.max(titlebarBottom, top) + 'px';
      panel.style.width = width + 'px';
      panel.style.height = Math.max(1, Math.floor(height)) + 'px';
      panel.style.maxHeight = Math.max(1, Math.floor(height)) + 'px';
    }

    function updateSelectedUi() {
      var n = Object.keys(state.selected).length;
      countLabel.textContent = n ? ('已选择 ' + n + ' 项') : '未选择文件';
      list.querySelectorAll('.workspace-file-item').forEach(function (btn) {
        var key = btn.getAttribute('data-path-key') || '';
        var on = !!state.selected[key];
        btn.classList.toggle('is-selected', on);
        var check = btn.querySelector('.workspace-file-check');
        if (check) check.textContent = on ? '✓' : '';
      });
    }

    function setActive(idx) {
      var buttons = list.querySelectorAll('.workspace-file-item');
      if (!buttons.length) { state.active = 0; return; }
      state.active = Math.max(0, Math.min(idx, buttons.length - 1));
      for (var i = 0; i < buttons.length; i++) {
        buttons[i].classList.toggle('is-active', i === state.active);
        buttons[i].setAttribute('aria-selected', i === state.active ? 'true' : 'false');
      }
      var activeButton = buttons[state.active];
      if (activeButton && typeof activeButton.scrollIntoView === 'function') activeButton.scrollIntoView({ block: 'nearest' });
    }

    function close() {
      state.open = false;
      panel.classList.remove('is-open');
      panel.setAttribute('aria-hidden', 'true');
      if (state.debounce) clearTimeout(state.debounce);
      if (state.controller) state.controller.abort();
    }

    function itemKey(item) {
      return item ? (item.path || item.rel || item.name || '') : '';
    }

    function itemToken(item) {
      return quotePickedPath(itemKey(item));
    }

    function itemTextStillPresent(item, current) {
      var key = itemKey(item);
      if (!key) return false;
      var rel = String(item && item.rel || '');
      return current.indexOf(itemToken(item)) >= 0
        || current.indexOf(key) >= 0
        || (rel && current.indexOf(quotePickedPath(rel)) >= 0)
        || (rel && current.indexOf(rel) >= 0);
    }

    function insertedTextDelta(before, after) {
      before = String(before || '');
      after = String(after || '');
      var start = 0;
      while (start < before.length && start < after.length && before.charAt(start) === after.charAt(start)) start++;
      var endBefore = before.length - 1;
      var endAfter = after.length - 1;
      while (endBefore >= start && endAfter >= start && before.charAt(endBefore) === after.charAt(endAfter)) {
        endBefore--;
        endAfter--;
      }
      return after.slice(start, endAfter + 1).trim();
    }

    function appendSelectionToken(item, token) {
      if (!token) return;
      var current = String(textarea.value || '');
      if (current.indexOf(token) >= 0) return;
      var before = textarea.value;
      insertTextAtCursor(textarea, token);
      var added = insertedTextDelta(before, textarea.value);
      if (item && added) item._inputToken = added;
    }

    function removeSelectionToken(item, token) {
      if (!token && !item) return;
      var current = String(textarea.value || '');
      var candidates = [];
      function addCandidate(x) {
        x = String(x || '').trim();
        if (x && candidates.indexOf(x) < 0) candidates.push(x);
      }
      addCandidate(item && item._inputToken);
      addCandidate(token);
      addCandidate(item && item.path);
      addCandidate(item && item.rel);
      addCandidate(item && item.path && quotePickedPath(item.path));
      addCandidate(item && item.rel && quotePickedPath(item.rel));
      var next = current;
      candidates.sort(function (a, b) { return b.length - a.length; }).forEach(function (cand) {
        var escaped = cand.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        var re = new RegExp('(?:^|\\s)' + escaped + '(?=\\s|$)', 'g');
        next = next.replace(re, function (match) {
          return match.charAt(0) && /\s/.test(match.charAt(0)) ? ' ' : '';
        });
      });
      next = next.replace(/[ \t]{2,}/g, ' ').trim();
      if (next !== current) {
        textarea.value = next;
        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }

    function toggleItem(item) {
      if (!item) return;
      var key = itemKey(item);
      if (!key) return;
      var token = itemToken(item);
      if (state.selected[key]) {
        var selectedItem = state.selected[key];
        delete state.selected[key];
        removeSelectionToken(selectedItem, token);
      } else {
        state.selected[key] = item;
        appendSelectionToken(item, token);
      }
      updateSelectedUi();
    }

    function syncSelectionFromTextarea() {
      var current = String(textarea.value || '');
      Object.keys(state.selected).forEach(function (key) {
        var item = state.selected[key];
        if (!itemTextStillPresent(item, current)) delete state.selected[key];
      });
    }

    function syncSelectionUiFromTextarea() {
      syncSelectionFromTextarea();
      updateSelectedUi();
    }

    textarea.addEventListener('input', syncSelectionUiFromTextarea);
    if (outsideBtn) {
      outsideBtn.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (typeof uploadOutsideFiles === 'function') uploadOutsideFiles();
      });
    }

    function workspaceRootName() {
      var root = String(global.__WORK_DIR__ || 'workspace');
      var parts = root.split(/[\\/]+/).filter(Boolean);
      return parts[parts.length - 1] || 'workspace';
    }

    function makeDir(name, rel, root) {
      return { type: 'dir', name: name, rel: rel, root: !!root, path: '', dirs: Object.create(null), files: [], children: [], loaded: false };
    }

    function nativeRootFromItem(item, relPath) {
      var abs = String((item && item.path) || '');
      var rel = String(relPath || '').replace(/\//g, '\\');
      if (abs && rel && abs.toLowerCase().slice(-rel.length) === rel.toLowerCase()) {
        return abs.slice(0, Math.max(0, abs.length - rel.length)).replace(/[\\/]+$/, '');
      }
      return String(global.__WORK_DIR__ || '').replace(/[\\/]+$/, '');
    }

    function joinNativePath(root, rel) {
      var base = String(root || '').replace(/[\\/]+$/, '');
      var tail = String(rel || '').replace(/[\\/]+/g, '/');
      if (!tail) return base;
      var sep = base.indexOf('\\') >= 0 ? '\\' : '/';
      return base ? (base + sep + tail.replace(/\//g, sep)) : tail;
    }

    function dirSelectionItem(node) {
      return {
        kind: 'directory',
        name: node.name || node.rel || workspaceRootName(),
        rel: node.rel || '',
        path: node.path || joinNativePath(String(global.__WORK_DIR__ || ''), node.rel || ''),
      };
    }

    function buildTree(items) {
      var root = makeDir(workspaceRootName(), '', true);
      root.path = String(global.__WORK_DIR__ || '').replace(/[\\/]+$/, '');
      root.loaded = !!state.loadedDirs.__root__;
      function ensureDir(parts, rootPath) {
        var node = root;
        var pathParts = [];
        for (var i = 0; i < parts.length; i++) {
          pathParts.push(parts[i]);
          if (!node.dirs[parts[i]]) {
            node.dirs[parts[i]] = makeDir(parts[i], pathParts.join('/'), false);
            node.dirs[parts[i]].path = joinNativePath(rootPath || root.path, pathParts.join('/'));
          }
          node = node.dirs[parts[i]];
          node.loaded = !!state.loadedDirs[node.rel || '__root__'];
        }
        return node;
      }
      (items || []).forEach(function (item) {
        var relPath = String(item.rel || item.path || item.name || '').replace(/\\/g, '/');
        var parts = relPath.split('/').filter(Boolean);
        if (!parts.length) return;
        var rootPath = nativeRootFromItem(item, relPath);
        if (!root.path && rootPath) root.path = rootPath;
        if (item.kind === 'directory') {
          var dirNode = ensureDir(parts, rootPath || root.path);
          dirNode.name = item.name || dirNode.name;
          dirNode.path = item.path || dirNode.path;
          return;
        }
        var node = ensureDir(parts.slice(0, -1), rootPath || root.path);
        node.files.push({ type: 'file', name: item.name || parts[parts.length - 1] || relPath, rel: relPath, item: item });
      });
      function finish(dir) {
        var dirs = Object.keys(dir.dirs).map(function (key) { return dir.dirs[key]; }).sort(function (a, b) {
          return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
        });
        dirs.forEach(finish);
        dir.files.sort(function (a, b) {
          return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
        });
        dir.children = dirs.concat(dir.files);
      }
      finish(root);
      return root;
    }

    function expandKnownDirs(dir, force, depth) {
      if (!dir || dir.type !== 'dir') return;
      depth = Number(depth || 0);
      var key = dir.rel || '__root__';
      if (force) state.expanded[key] = true;
      else if (typeof state.expanded[key] === 'undefined') state.expanded[key] = depth === 0;
      if (force) dir.children.forEach(function (child) {
        if (child.type === 'dir') expandKnownDirs(child, force, depth + 1);
      });
    }

    function flattenTree(root) {
      var rows = [];
      function walk(node, depth) {
        rows.push({ type: 'dir', node: node, depth: depth });
        if (!state.expanded[node.rel || '__root__']) return;
        node.children.forEach(function (child) {
          if (child.type === 'dir') walk(child, depth + 1);
          else rows.push({ type: 'file', node: child, depth: depth + 1 });
        });
      }
      walk(root, 0);
      return rows;
    }

    function itemMapKey(item) {
      return String((item && (item.kind || 'file')) || 'file') + ':' + String((item && (item.rel || item.path || item.name)) || '');
    }

    function mergeLoadedItems(items) {
      (items || []).forEach(function (item) {
        var key = itemMapKey(item);
        if (key !== ':') state.itemMap[key] = item;
      });
      state.items = Object.keys(state.itemMap).map(function (key) { return state.itemMap[key]; });
      state.items.sort(function (a, b) {
        return String(a.rel || '').localeCompare(String(b.rel || ''), undefined, { sensitivity: 'base' });
      });
    }

    function toggleDir(node) {
      if (!node) return;
      var key = node.rel || '__root__';
      state.expanded[key] = !state.expanded[key];
      render(state.items, false);
      if (state.expanded[key] && !search.value && !state.loadedDirs[key]) loadDir(node.rel || '');
    }

    function render(items, loading, error) {
      syncSelectionFromTextarea();
      state.items = (items || []).slice().sort(function (a, b) {
        return String(a.rel || '').localeCompare(String(b.rel || ''), undefined, { sensitivity: 'base' });
      });
      list.innerHTML = '';
      state.visible = [];
      if (loading) { list.innerHTML = '<div class="workspace-file-empty">加载中</div>'; return; }
      if (error) { list.innerHTML = '<div class="workspace-file-empty">' + String(error) + '</div>'; return; }
      if (!state.items.length) { list.innerHTML = '<div class="workspace-file-empty">没有匹配文件</div>'; return; }
      var root = buildTree(state.items);
      expandKnownDirs(root, !!search.value);
      state.visible = flattenTree(root);
      state.visible.forEach(function (row, idx) {
        var node = row.node;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'workspace-file-item ' + (row.type === 'dir' ? 'workspace-file-dir-row' : 'workspace-file-file-row');
        btn.setAttribute('role', 'option');
        btn.setAttribute('data-row-index', String(idx));
        btn.setAttribute('data-path-key', row.type === 'dir'
          ? (dirSelectionItem(node).path || dirSelectionItem(node).rel || dirSelectionItem(node).name || '')
          : (node.item.path || node.item.rel || node.item.name || ''));

        var tree = document.createElement('div');
        tree.className = 'workspace-file-tree';
        var indent = document.createElement('span');
        indent.className = 'workspace-file-indent';
        indent.style.setProperty('--indent', Math.min(row.depth, 10) * 0.86 + 'rem');
        var chevron = document.createElement('span');
        chevron.className = 'workspace-file-chevron';
        chevron.textContent = row.type === 'dir' ? (state.expanded[node.rel || '__root__'] ? '▾' : '▸') : '';
        if (row.type === 'dir') {
          chevron.setAttribute('aria-label', state.expanded[node.rel || '__root__'] ? '折叠文件夹' : '展开文件夹');
          chevron.setAttribute('role', 'button');
          chevron.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            toggleDir(node);
          });
        } else {
          chevron.setAttribute('tabindex', '-1');
        }
        var icon = document.createElement('span');
        icon.className = 'workspace-file-icon' + (row.type === 'file' ? (' is-file ' + fileIconTypeClass(node.item && node.item.name)) : ' is-folder-svg');
        if (row.type === 'dir') icon.innerHTML = FOLDER_SVG;
        var name = document.createElement('div');
        name.className = 'workspace-file-name';
        name.textContent = node.name || node.rel || '';
        var meta = document.createElement('div');
        meta.className = 'workspace-file-meta';
        meta.textContent = row.type === 'dir' ? '' : formatBytes(node.item.size);

        tree.appendChild(indent);
        tree.appendChild(chevron);
        tree.appendChild(icon);
        tree.appendChild(name);
        var check = document.createElement('span');
        check.className = 'workspace-file-check';
        btn.appendChild(check);
        btn.appendChild(tree);
        btn.appendChild(meta);
        btn.addEventListener('mouseenter', function () { setActive(idx); });
        btn.addEventListener('click', function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          if (row.type === 'dir') toggleItem(dirSelectionItem(node));
          else toggleItem(node.item);
        });
        list.appendChild(btn);
      });
      setActive(0);
      updateSelectedUi();
    }

    function loadNow() {
      var q = search.value || '';
      if (state.controller) state.controller.abort();
      state.controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      render(state.items, true);
      fetchWorkspaceFiles(q, '', state.controller ? state.controller.signal : undefined)
        .then(function (items) {
          if (!state.open) return;
          if (q) {
            render(items, false);
          } else {
            state.loadedDirs.__root__ = true;
            mergeLoadedItems(items);
            render(state.items, false);
          }
        })
        .catch(function (err) {
          if (err && err.name === 'AbortError') return;
          if (state.open) render([], false, (err && err.message) || '读取失败');
        });
    }

    function loadDir(rel) {
      var key = rel || '__root__';
      if (state.loadedDirs[key]) return;
      state.loadedDirs[key] = true;
      fetchWorkspaceFiles('', rel || '', undefined)
        .then(function (items) {
          if (!state.open || search.value) return;
          mergeLoadedItems(items);
          render(state.items, false);
        })
        .catch(function () {
          delete state.loadedDirs[key];
        });
    }

    function scheduleLoad() {
      if (state.debounce) clearTimeout(state.debounce);
      state.debounce = setTimeout(loadNow, 120);
    }

    function open() {
      if (state.open) { positionPanel(); try { search.focus(); search.select(); } catch (e) {} return; }
      state.open = true;
      panel.classList.add('is-open');
      panel.setAttribute('aria-hidden', 'false');
      search.value = '';
      state.expanded = Object.create(null);
      state.loadedDirs = Object.create(null);
      state.itemMap = Object.create(null);
      state.items = [];
      render([], true);
      positionPanel();
      loadNow();
      setTimeout(function () { positionPanel(); try { search.focus(); } catch (e) {} }, 0);
    }

    function toggle() { if (state.open) close(); else open(); }

    search.addEventListener('input', scheduleLoad);
    search.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown') { ev.preventDefault(); setActive(state.active + 1); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); setActive(state.active - 1); }
      else if (ev.key === 'Enter') {
        if (ev.isComposing || ev.keyCode === 229 || ev.which === 229) return;
        ev.preventDefault();
        var row = state.visible[state.active];
        if (row && row.type === 'dir') toggleItem(dirSelectionItem(row.node));
        else if (row && row.type === 'file') toggleItem(row.node.item);
      } else if (ev.key === 'Escape') {
        ev.preventDefault();
        close();
        textarea.focus();
      }
    });
    document.addEventListener('click', function (ev) {
      if (!state.open) return;
      if (panel.contains(ev.target)) return;
      close();
    });
    window.addEventListener('resize', function () { if (state.open) positionPanel(); });
    window.addEventListener('scroll', function () { if (state.open) positionPanel(); }, true);

    return { panel: panel, open: open, close: close, toggle: toggle };
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
      if (fixedKind !== 'file' && fixedKind !== 'directory') fixedKind = 'directory';
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

  function bindDropUpload(textarea) {
    var wrapper = textarea.closest ? textarea.closest('.input-wrapper') : textarea;
    if (!wrapper || wrapper.dataset.fileDropBound === '1') return;
    wrapper.dataset.fileDropBound = '1';
    ['dragenter', 'dragover'].forEach(function (name) {
      wrapper.addEventListener(name, function (ev) {
        if (!ev.dataTransfer || !ev.dataTransfer.files || !ev.dataTransfer.files.length) return;
        ev.preventDefault();
        wrapper.classList.add('is-drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(function (name) {
      wrapper.addEventListener(name, function () { wrapper.classList.remove('is-drag-over'); });
    });
    wrapper.addEventListener('drop', function (ev) {
      if (!ev.dataTransfer || !ev.dataTransfer.files || !ev.dataTransfer.files.length) return;
      ev.preventDefault();
      startChatFileUpload(textarea, ev.dataTransfer.files).catch(function () {});
    });
  }

  function attachChatPicker(button, textarea) {
    if (!button || !textarea) return;
    injectStyles();
    bindDropUpload(textarea);
    bindPasteUpload(textarea);
    button.classList.add('path-browse-btn', 'path-browse-btn--ghost');
    button.innerHTML = FOLDER_SVG;
    button.setAttribute('aria-label', '工作区文件');
    button.setAttribute('data-ui-tip', '工作区文件');
    button.dataset.silentPickerUnavailable = '1';
    button.removeAttribute('title');

    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.multiple = true;
    fileInput.style.display = 'none';
    fileInput.setAttribute('aria-hidden', 'true');
    document.body.appendChild(fileInput);
    fileInput.addEventListener('change', function () {
      var files = fileInput.files;
      if (!files || !files.length) return;
      button.disabled = true;
      startChatFileUpload(textarea, files).catch(function () {}).finally(function () {
        fileInput.value = '';
        button.disabled = false;
      });
    });

    var panelApi = createWorkspaceFilePanel(textarea, function () {
      fileInput.click();
    });
    button.addEventListener('click', function (ev) {
      ev.stopPropagation();
      ev.preventDefault();
      if (ev.altKey) { fileInput.click(); return; }
      if (!ev.shiftKey) { panelApi.toggle(); return; }
      var initial = (global && typeof global.__WORK_DIR__ === 'string') ? global.__WORK_DIR__ : '';
      runPick(button, 'file', initial, function (p) {
        var paths = Array.isArray(p) ? p : (p ? [p] : []);
        if (!paths.length) return;
        insertTextAtCursor(textarea, paths.map(function (item) { return quotePickedPath(item); }).join(' '));
      }, false);
    });
  }

  function scan(root) {
    root = root || document;
    var nodes = root.querySelectorAll('[data-path-kind]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var kind = el.getAttribute('data-path-kind');
      if (kind === 'file' || kind === 'directory') wrapInputWithBrowse(el, kind);
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
    chatAttachments: chatAttachments,
    clearChatAttachments: clearChatAttachments,
    scan: scan,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { scan(document); });
  } else {
    scan(document);
  }
})(typeof window !== 'undefined' ? window : globalThis);
