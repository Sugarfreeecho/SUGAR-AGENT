/* Folder/archive drops use uploaded contents: browsers do not expose absolute paths. */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const MAX_FILES = 5000, MAX_BYTES = 200 * 1024 * 1024;
  const ARCHIVE_RE = /\.(zip|tar|tar\.gz|tgz|tar\.bz2|tbz2|tar\.xz|txz)$/i;
  /* 安装冲突（技能）：由分区注册的解析器接管「取消 / 覆盖 / 改名」 */
  const conflictResolvers = {};

  function registerConflictResolver(key, resolver) {
    if (key) conflictResolvers[key] = resolver;
  }

  async function droppedFiles(data) {
    const items = Array.from(data.items || []).filter((item) => item.kind === 'file');
    // Capture entries before the drop event's protected data store is released.
    const entries = items.map((item) => item.webkitGetAsEntry ? item.webkitGetAsEntry() : null);
    const fallback = Array.from(data.files || []);
    const files = [];
    let bytes = 0;
    const add = (file, path, sink) => {
      bytes += file.size;
      const target = sink ? sink.files : files;
      if (target.length >= MAX_FILES || bytes > MAX_BYTES) throw new Error(A.t('目录最多 5000 个文件，总大小不能超过 200 MB', 'Maximum 5000 files and 200 MB'));
      target.push({ file, path });
    };
    async function walk(entry, prefix, depth, sink) {
      if (depth > 40) throw new Error(A.t('目录层级过深', 'Directory nesting is too deep'));
      const path = prefix + entry.name;
      if (entry.isFile) {
        const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
        add(file, path, sink);
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        for (;;) {
          const children = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
          if (!children.length) break;
          for (const child of children) await walk(child, path + '/', depth + 1, sink);
        }
      }
    }
    if (entries.length && entries.every(Boolean)) {
      // 批量：每个目录 / 每个压缩包各算一个包，零散文件合成一个包
      const packages = [];
      const loose = { kind: 'dir', files: [] };
      const push = (entry, sink) => walk(entry, '', 0, sink);
      for (const entry of entries) {
        if (entry.isDirectory) {
          const sink = { kind: 'dir', files: [] };
          await push(entry, sink);
          packages.push(sink);
        } else if (ARCHIVE_RE.test(entry.name)) {
          const sink = { kind: 'zip', files: [] };
          await push(entry, sink);
          packages.push(sink);
        } else {
          await push(entry, loose);
        }
      }
      if (loose.files.length) packages.push(loose);
      return packages;
    }
    const archives = fallback.filter((file) => ARCHIVE_RE.test(file.webkitRelativePath || file.name));
    const rest = fallback.filter((file) => !archives.includes(file));
    const packages = archives.map((file) => {
      add(file, file.name);
      return { kind: 'zip', files: files.splice(0, files.length) };
    });
    if (rest.length) {
      const sink = { kind: 'dir', files: [] };
      rest.forEach((file) => {
        bytes += file.size;
        if (sink.files.length >= MAX_FILES || bytes > MAX_BYTES) {
          throw new Error(A.t('目录最多 5000 个文件，总大小不能超过 200 MB', 'Maximum 5000 files and 200 MB'));
        }
        sink.files.push({ file, path: file.webkitRelativePath || file.name });
      });
      packages.push(sink);
    }
    return packages;
  }

  /** 上传一个包；技能遇到同名时交给分区的冲突解析器，按选择重试。 */
  async function uploadPackage(packageKind, pack, resolverKey) {
    const post = async (mode, renameTo) => {
      const form = new FormData();
      form.append('kind', pack.kind);
      if (mode) form.append('on_conflict', mode);
      if (renameTo) form.append('rename_to', renameTo);
      pack.files.forEach(({ file, path }) => form.append('files', file, path));
      const response = await fetch('/api/' + packageKind + '/install-upload', {
        method: 'POST', credentials: 'same-origin', body: form,
      });
      const result = await response.json().catch(() => ({}));
      return { response, result };
    };
    let { response, result } = await post();
    while (response.status === 409 && result && result.conflict && resolverKey && conflictResolvers[resolverKey]) {
      const choice = await conflictResolvers[resolverKey](result.conflict);
      if (!choice || choice.mode === 'cancel') {
        return { ok: false, name: result.conflict.name, cancelled: true, error: A.t('已取消', 'Cancelled') };
      }
      ({ response, result } = await post(choice.mode, choice.rename_to));
    }
    if (!response.ok || !result.ok) {
      const label = (pack.files[0] && pack.files[0].path) || '';
      return { ok: false, name: label, error: result.error || A.t('安装失败', 'Installation failed') };
    }
    if (window.MyAgentResourceCache) window.MyAgentResourceCache.invalidate();
    return { ok: true, name: result.name || '' };
  }

  function bind(root) {
    root.querySelectorAll('[data-browse-kind]').forEach((button) => {
      if (button.dataset.browseBound) return;
      button.dataset.browseBound = '1';
      button.addEventListener('click', async () => {
        const input = root.querySelector('[data-field="' + button.dataset.browseField + '"]');
        if (!input || !window.MyAgentPathPicker) return;
        button.disabled = true;
        try {
          const multiple = button.dataset.browseMultiple === '1';
          const path = await MyAgentPathPicker.pickPath(button.dataset.browseKind, input.value, multiple);
          if (path && Array.isArray(path)) {
            if (path.length) input.value = path.join('\n');
            input.dispatchEvent(new Event('input', { bubbles: true }));
          } else if (path) {
            input.value = button.dataset.browseCommand ? '"' + path.replace(/"/g, '\\"') + '"' : path;
            input.dispatchEvent(new Event('input', { bubbles: true }));
          }
        } catch (error) { A.reportError(error); }
        finally { button.disabled = false; }
      });
    });
    root.querySelectorAll('[data-package-kind]').forEach((zone) => {
      if (zone.dataset.dropBound) return;
      zone.dataset.dropBound = '1';
      let busy = false;
      const hasFiles = (event) => event.dataTransfer && Array.from(event.dataTransfer.types || []).includes('Files');
      zone.addEventListener('dragover', (event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = busy ? 'none' : 'copy';
        zone.classList.add('is-dragover');
      });
      zone.addEventListener('dragleave', (event) => {
        if (!zone.contains(event.relatedTarget)) zone.classList.remove('is-dragover');
      });
      zone.addEventListener('drop', async (event) => {
        if (!hasFiles(event)) return;
        event.preventDefault(); event.stopPropagation();
        zone.classList.remove('is-dragover');
        if (busy) return;
        busy = true;
        zone.setAttribute('aria-busy', 'true');
        const controls = Array.from(zone.querySelectorAll('input,button'));
        const disabled = controls.map((control) => control.disabled);
        controls.forEach((control) => { control.disabled = true; });
        const dialogOk = zone.closest('#st-dlg-body') ? document.getElementById('st-dlg-ok') : null;
        if (dialogOk) dialogOk.disabled = true;
        try {
          const packages = await droppedFiles(event.dataTransfer);
          if (!packages.length) throw new Error(A.t('目录中没有可安装的文件', 'No installable files in this folder'));
          const bad = packages.find((pack) => pack.kind === 'zip'
            && (pack.files.length !== 1 || !ARCHIVE_RE.test(pack.files[0].path)));
          if (bad) throw new Error(A.t('请拖入技能 / 插件目录或 ZIP、TAR 压缩包', 'Drop a package folder or ZIP/TAR archive'));
          A.toast(A.t('正在解析并安装…', 'Parsing and installing…'));
          const results = [];
          for (const pack of packages) {
            results.push(await uploadPackage(zone.dataset.packageKind, pack, zone.dataset.packageResolve));
          }
          const installed = results.filter((item) => item.ok).length;
          const failed = results.filter((item) => !item.ok);
          if (!installed) {
            throw new Error(failed.length === 1
              ? failed[0].error
              : A.t('全部失败：', 'All failed: ') + failed.map((item) => item.error).join('；'));
          }
          if (failed.length) {
            A.reportError(new Error(
              A.t('部分成功：已安装 ', 'Partially done: installed ') + installed
              + A.t(' 个，失败 ', ', failed ') + failed.length + A.t(' 个：', ': ')
              + failed.map((item) => (item.name ? item.name + '（' + item.error + '）' : item.error)).join('；')
            ));
          } else {
            A.toast(packages.length > 1
              ? A.t('已安装 ', 'Installed ') + installed + A.t(' 个', '')
              : A.t('已安装', 'Installed'));
          }
          if (dialogOk && zone.isConnected && !document.getElementById('st-dialog').hidden) A.closeDialog();
          A.reload();
        } catch (error) { A.reportError(error); }
        finally {
          busy = false; zone.removeAttribute('aria-busy');
          controls.forEach((control, index) => { control.disabled = disabled[index]; });
          if (dialogOk && zone.isConnected) dialogOk.disabled = false;
        }
      });
    });
  }
  window.MyAgentPackageImport = { bind, registerConflictResolver };
})();
