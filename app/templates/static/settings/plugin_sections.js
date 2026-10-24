/* Settings extension contract: ui.settings.section, backed by the validated plugin schema. */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, W, api } = A;
  const pluginPattern = /^[a-z0-9][a-z0-9._-]{0,127}$/;
  const sectionPattern = /^[a-z][a-z0-9._-]{0,63}$/;
  let registryGeneration = 0;

  function settingsRenderer(item) {
    if (item.target !== 'renderer' || !item.renderer) return null;
    const prefix = '/plugin-assets/' + item.plugin_id + '/';
    const valid = ['module', 'style'].every(key => {
      const value = item.renderer[key];
      return typeof value === 'string' && value.startsWith(prefix) && !value.includes('..') && !value.includes('\\')
        && value.split('?')[0].endsWith(key === 'module' ? '.js' : '.css');
    });
    return valid ? item.renderer : null;
  }
  async function mountSettingsRenderer(root, item, renderer) {
    const target = root.querySelector('[data-plugin-settings-renderer]');
    if (!target || !target.isConnected) return;
    let link = document.querySelector('link[data-plugin-settings-style="' + item.plugin_id + ':' + item.id + '"]');
    if (!link) {
      link = document.createElement('link'); link.rel = 'stylesheet'; link.href = renderer.style;
      link.dataset.pluginSettingsStyle = item.plugin_id + ':' + item.id; document.head.append(link);
    }
    try {
      const styleReady = link.sheet ? Promise.resolve() : new Promise(resolve => {
        const timer = setTimeout(done, 8000);
        function done() { clearTimeout(timer); link.removeEventListener('load', done); link.removeEventListener('error', done); resolve(); }
        link.addEventListener('load', done, { once: true }); link.addEventListener('error', done, { once: true });
      });
      const [module] = await Promise.all([import(renderer.module), styleReady]);
      if (target.isConnected && typeof module.mountSettings === 'function') {
        return await module.mountSettings({ root: target, settings: A });
      }
    } catch (error) { target.textContent = t('插件设置加载失败：', 'Plugin settings failed: ') + error.message; }
  }

  function currentFrame() { return document.querySelector('[data-plugin-settings-frame]'); }
  function sendFrameContext(frame) {
    if (!frame || !frame.contentWindow) return;
    const root = document.documentElement;
    frame.contentWindow.postMessage({
      type: 'myagent:plugin-settings-context',
      theme: root.classList.contains('theme-dark') ? 'theme-dark' :
        root.classList.contains('theme-purple') ? 'theme-purple' : 'theme-light',
      lang: A.lang, fontPx: A.storedFontPx(),
    }, window.location.origin);
  }
  window.addEventListener('message', (event) => {
    const frame = currentFrame();
    if (!frame || event.origin !== window.location.origin || event.source !== frame.contentWindow) return;
    const data = event.data || {};
    if (data.type === 'myagent:plugin-settings-ready') sendFrameContext(frame);
    if (data.type === 'myagent:plugin-settings-resize' && Number.isFinite(data.height)) {
      frame.style.height = Math.max(320, Math.min(20000, Math.ceil(data.height))) + 'px';
    }
    if (data.type === 'myagent:plugin-settings-navigate' && data.section === 'models') A.showSection('models');
    if (data.type === 'myagent:plugin-settings-close') A.requestClose();
  });
  new MutationObserver(() => sendFrameContext(currentFrame())).observe(document.documentElement, {
    attributes: true, attributeFilter: ['class', 'lang', 'style'],
  });

  A.pluginSettingsMarkup = (settings) => (settings.fields || []).map((field) => {
    const attrs = ' data-field="' + esc(field.id) + '" aria-label="' + esc(field.title || field.id) + '"' + (field.required ? ' required aria-required="true"' : '');
    const value = field.value == null ? '' : field.value;
    let control;
    if (field.format === 'secret') {
      control = '<span class="st-muted">' + (field.configured ? t('已配置', 'Configured') : t('未配置', 'Not set')) + '</span>';
    } else if (Array.isArray(field.enum)) {
      control = '<select class="st-input"' + attrs + '><option value="">' + t('使用默认值', 'Use default') + '</option>' +
        field.enum.map((item) => '<option value="' + esc(item) + '"' + (item === value ? ' selected' : '') + '>' + esc(item) + '</option>').join('') + '</select>';
    } else if (field.type === 'boolean') {
      control = '<select class="st-input"' + attrs + '><option value="">' + t('使用默认值', 'Use default') + '</option>' +
        [true, false].map((item) => '<option value="' + item + '"' + (value === item ? ' selected' : '') + '>' + item + '</option>').join('') + '</select>';
    } else if (field.format === 'multiline') {
      control = '<textarea class="st-input"' + attrs + '>' + esc(value) + '</textarea>';
    } else {
      control = '<input class="st-input"' + attrs +
        (['file', 'directory'].includes(field.format) ? ' data-path-kind="' + field.format + '"' : '') +
        (['number', 'integer'].includes(field.type) ? ' type="number" step="' + (field.type === 'integer' ? '1' : 'any') + '"' : '') +
        ' value="' + esc(value) + '" placeholder="' + esc(field.default == null ? '' : field.default) + '">';
    }
    return W.row(esc(field.title || field.id) + ' <span class="st-field-status ' + (field.required ? 'required' : 'optional') + '">' +
      (field.required ? t('必填', 'Required') : t('选填', 'Optional')) + '</span>', esc(field.description || ''), control);
  }).join('');

  A.pluginSettingsValues = (root, settings) => {
    const fields = new Map((settings.fields || []).map((field) => [field.id, field]));
    const values = Object.create(null);
    root.querySelectorAll('[data-field]').forEach((input) => {
      const field = fields.get(input.dataset.field);
      if (!field || field.format === 'secret') return;
      const raw = input.value;
      if (raw === '') values[field.id] = null;
      else if (field.type === 'boolean') values[field.id] = raw === 'true';
      else if (['integer', 'number'].includes(field.type)) values[field.id] = Number(raw);
      else values[field.id] = raw;
    });
    return values;
  };

  A.syncPluginSections = (snapshot) => {
    registryGeneration++;
    const seen = new Set();
    const definitions = [];
    (snapshot.ui_contributions || []).slice(0, 256).forEach((item) => {
      if (item.slot !== 'settings.section' || !pluginPattern.test(item.plugin_id) || !sectionPattern.test(item.id)) return;
      const id = 'plugin:' + item.plugin_id + ':' + item.id;
      if (seen.has(id)) return;
      const endpoint = '/api/plugins/' + item.plugin_id + '/settings';
      const href = '/plugins/' + item.plugin_id;
      const isForm = item.target === 'plugin-settings' && item.endpoint === endpoint;
      const renderer = settingsRenderer(item);
      if (!isForm && !renderer && !(item.target === 'plugin-page' && item.href === href)) return;
      const isEmbedded = item.target === 'plugin-page' && item.embedded === true;
      const title = String(item.title || item.label || item.plugin_id);
      seen.add(id);
      definitions.push({
        id, pluginOwned: true, embeddedPage: isEmbedded, icon: 'plugins', zh: title, en: title,
        zhSub: String(item.description || ''), enSub: String(item.description || ''),
        mode: isForm ? 'explicit' : 'instant',
        dirtyMessage: ['有未保存的插件设置', 'Unsaved plugin settings'],
        async load() { return isForm ? (await api(endpoint)).settings || {} : {}; },
        render(settings) {
          if (isForm) return W.card(esc(settings.title || title), esc(settings.description || ''),
            A.pluginSettingsMarkup(settings) || W.empty(t('该插件没有可配置项', 'No configurable fields')));
          if (renderer) return '<section data-plugin-settings-renderer></section>';
          if (isEmbedded) return '<iframe class="st-plugin-settings-frame" data-plugin-settings-frame' +
            ' title="' + esc(title) + '" src="' + href + '?embedded=1" referrerpolicy="same-origin"></iframe>';
          return W.card(esc(title), esc(item.description || ''),
            W.row(t('插件独立页面', 'Plugin page'), t('打开插件提供的完整界面', 'Open the full plugin interface'),
              '<a class="st-btn" href="' + href + '" target="_blank" rel="noopener">' + t('打开', 'Open') + '</a>'));
        },
        after(root) {
          if (renderer) return mountSettingsRenderer(root, item, renderer);
          if (!isEmbedded) return;
          const frame = root.querySelector('[data-plugin-settings-frame]');
          if (frame) {
            frame.addEventListener('load', () => sendFrameContext(frame));
            sendFrameContext(frame);
          }
        },
        async save(settings) {
          await api(endpoint, { method: 'PATCH', body: { values: A.pluginSettingsValues(document.getElementById('st-body'), settings) } });
        },
      });
    });
    A.replacePluginSections(definitions);
  };
  A.loadPluginSections = async () => {
    const started = window.performance?.now();
    const cached = window.MyAgentResourceCache?.peek?.('/api/plugins/catalog');
    if (cached) A.syncPluginSections(cached);
    const generation = ++registryGeneration;
    const snapshot = await api('/api/plugins/catalog');
    if (generation === registryGeneration) {
      A.syncPluginSections(snapshot);
      if (started !== undefined) window.performance.measure('settings.plugin-tabs', { start: started });
    }
  };
})();
