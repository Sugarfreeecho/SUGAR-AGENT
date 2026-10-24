'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const listeners = new Map();
let definitions = [], selected = '', closed = false, frame = null;
const style = {};
const sent = [];
const A = {
  registerSection() {},
  t: (zh) => zh, esc: (value) => String(value).replace(/</g, '&lt;').replace(/"/g, '&quot;'),
  W: {card: (...args) => args.join(''), row: (...args) => args.join(''), empty: (x) => x},
  api: async () => ({}), replacePluginSections: (rows) => { definitions = rows; },
  storedFontPx: () => 16, lang: 'zh',
  showSection: (id) => { selected = id; }, requestClose: () => { closed = true; },
};
let observer;
const window = {MyAgentSettings: A, location: {origin: 'http://127.0.0.1:8000'},
  addEventListener: (type, callback) => listeners.set(type, callback)};
const document = {querySelector: () => frame, documentElement: {classList: {contains: (x) => x === 'theme-dark'}}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname, '../../app/templates/static/settings/plugin_sections.js'), 'utf8'), {
  window, document, MutationObserver: class {constructor(fn) {observer = fn;} observe() {}},
});
const contribution = {slot: 'settings.section', plugin_id: 'demo', id: 'main', title: '<Demo>',
  target: 'plugin-page', href: '/plugins/demo', embedded: true};
A.syncPluginSections({ui_contributions: [contribution, {...contribution, id: 'evil', href: 'https://evil.example'}]});
assert.equal(definitions.length, 1);
const markup = definitions[0].render({});
assert.ok(markup.includes('data-plugin-settings-frame'));
assert.ok(markup.includes('src="/plugins/demo?embedded=1"'));
assert.ok(markup.includes('&lt;Demo>'));
assert.ok(!markup.includes('target="_blank"'));
frame = {style, contentWindow: {postMessage: (message, origin) => sent.push({message, origin})}, addEventListener() {}};
definitions[0].after({querySelector: () => frame});
assert.equal(sent.at(-1).message.theme, 'theme-dark');
assert.equal(sent.at(-1).origin, window.location.origin);
const message = (data, origin = window.location.origin, source = frame.contentWindow) => listeners.get('message')({data, origin, source});
message({type: 'myagent:plugin-settings-resize', height: 900}, 'https://evil.example');
message({type: 'myagent:plugin-settings-resize', height: 900}, window.location.origin, {});
assert.equal(style.height, undefined);
message({type: 'myagent:plugin-settings-resize', height: 900});
assert.equal(style.height, '900px');
message({type: 'myagent:plugin-settings-resize', height: Infinity});
assert.equal(style.height, '900px');
message({type: 'myagent:plugin-settings-resize', height: 1e9});
assert.equal(style.height, '20000px');
message({type: 'myagent:plugin-settings-navigate', section: 'https://evil.example'});
assert.equal(selected, '');
message({type: 'myagent:plugin-settings-navigate', section: 'models'});
assert.equal(selected, 'models');
message({type: 'myagent:plugin-settings-close'});
assert.equal(closed, true);
observer();
assert.ok(sent.length >= 2);
A.syncPluginSections({ui_contributions: [{...contribution, embedded: false}]});
assert.ok(definitions[0].render({}).includes('target="_blank"'), 'existing standalone declarations retain their behavior');
A.syncPluginSections({ui_contributions: [{...contribution, embedded: 'true'}]});
assert.ok(!definitions[0].render({}).includes('iframe'), 'embedding requires a literal boolean');
console.log('plugin settings embed runtime checks passed');
