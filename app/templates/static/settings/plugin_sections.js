/* Settings extension contract: ui.settings.section, backed by the validated plugin schema. */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, W, api } = A;
  const pluginPattern = /^[a-z0-9][a-z0-9._-]{0,127}$/;
  const sectionPattern = /^[a-z][a-z0-9._-]{0,63}$/;
  let registryGeneration = 0;

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
      if (!isForm && !(item.target === 'plugin-page' && item.href === href)) return;
      const title = String(item.title || item.label || item.plugin_id);
      seen.add(id);
      definitions.push({
        id, pluginOwned: true, icon: 'plugins', zh: title, en: title,
        zhSub: String(item.description || ''), enSub: String(item.description || ''),
        mode: isForm ? 'explicit' : 'instant',
        dirtyMessage: ['有未保存的插件设置', 'Unsaved plugin settings'],
        async load() { return isForm ? (await api(endpoint)).settings || {} : {}; },
        render(settings) {
          if (isForm) return W.card(esc(settings.title || title), esc(settings.description || ''),
            A.pluginSettingsMarkup(settings) || W.empty(t('该插件没有可配置项', 'No configurable fields')));
          return W.card(esc(title), esc(item.description || ''),
            W.row(t('插件独立页面', 'Plugin page'), t('打开插件提供的完整界面', 'Open the full plugin interface'),
              '<a class="st-btn" href="' + href + '" target="_blank" rel="noopener">' + t('打开', 'Open') + '</a>'));
        },
        async save(settings) {
          await api(endpoint, { method: 'PATCH', body: { values: A.pluginSettingsValues(document.getElementById('st-body'), settings) } });
        },
      });
    });
    A.replacePluginSections(definitions);
  };
  A.loadPluginSections = async () => {
    const generation = ++registryGeneration;
    const snapshot = await api('/api/extensions');
    if (generation === registryGeneration) A.syncPluginSections(snapshot);
  };
})();
