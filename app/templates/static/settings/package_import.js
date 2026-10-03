/* Folder/archive drops use uploaded contents: browsers do not expose absolute paths. */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const MAX_FILES = 5000, MAX_BYTES = 200 * 1024 * 1024;

  async function droppedFiles(data) {
    const items = Array.from(data.items || []).filter((item) => item.kind === 'file');
    // Capture entries before the drop event's protected data store is released.
    const entries = items.map((item) => item.webkitGetAsEntry ? item.webkitGetAsEntry() : null);
    const fallback = Array.from(data.files || []);
    const files = [];
    let bytes = 0;
    const add = (file, path) => {
      bytes += file.size;
      if (files.length >= MAX_FILES || bytes > MAX_BYTES) throw new Error(A.t('目录最多 5000 个文件，总大小不能超过 200 MB', 'Maximum 5000 files and 200 MB'));
      files.push({ file, path });
    };
    async function walk(entry, prefix, depth) {
      if (depth > 40) throw new Error(A.t('目录层级过深', 'Directory nesting is too deep'));
      const path = prefix + entry.name;
      if (entry.isFile) {
        const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
        add(file, path);
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        for (;;) {
          const children = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
          if (!children.length) break;
          for (const child of children) await walk(child, path + '/', depth + 1);
        }
      }
    }
    if (entries.length && entries.every(Boolean)) {
      if (entries.length !== 1) throw new Error(A.t('一次请拖入一个目录或压缩包', 'Drop one folder or archive at a time'));
      await walk(entries[0], '', 0);
      return { files, kind: entries[0].isDirectory ? 'dir' : 'zip' };
    }
    for (const file of fallback) add(file, file.webkitRelativePath || file.name);
    return { files, kind: files.some((item) => item.path.includes('/')) ? 'dir' : 'zip' };
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
          const path = await MyAgentPathPicker.pickPath(button.dataset.browseKind, input.value, false);
          if (path) {
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
          const { files, kind } = await droppedFiles(event.dataTransfer);
          if (!files.length) throw new Error(A.t('目录中没有可安装的文件', 'No installable files in this folder'));
          if (kind === 'zip' && (files.length !== 1 || !/\.(zip|tar|tar\.gz|tgz|tar\.bz2|tbz2|tar\.xz|txz)$/i.test(files[0].path))) {
            throw new Error(A.t('请拖入技能 / 插件目录或 ZIP、TAR 压缩包', 'Drop a package folder or ZIP/TAR archive'));
          }
          A.toast(A.t('正在解析并安装…', 'Parsing and installing…'));
          const form = new FormData();
          form.append('kind', kind);
          files.forEach(({ file, path }) => form.append('files', file, path));
          const response = await fetch('/api/' + zone.dataset.packageKind + '/install-upload', { method: 'POST', credentials: 'same-origin', body: form });
          const result = await response.json();
          if (!response.ok || !result.ok) throw new Error(result.error || A.t('安装失败', 'Installation failed'));
          A.toast(A.t('已安装', 'Installed'));
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
  window.MyAgentPackageImport = { bind };
})();
