const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend/src/app/modules/workspace-media.js'),
  'utf8',
);

class FakeElement {
  constructor(tagName) {
    this.tagName = String(tagName || '').toUpperCase();
    this.children = [];
    this.attributes = Object.create(null);
    this.dataset = Object.create(null);
    this.className = '';
    this.classList = { add: (...names) => {
      const tokens = new Set(this.className.split(/\s+/).filter(Boolean));
      names.forEach((name) => tokens.add(name));
      this.className = Array.from(tokens).join(' ');
    } };
    this.parentElement = null;
    this.parentNode = null;
    this.textContent = '';
    this.hidden = false;
    this.listeners = Object.create(null);
  }
  appendChild(child) {
    child.parentElement = this;
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name.startsWith('data-')) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      this.dataset[key] = String(value);
    }
  }
  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name]
      : '';
  }
  addEventListener(name, handler) {
    this.listeners[name] = handler;
  }
}

const context = vm.createContext({
  console,
  document: { createElement: (tagName) => new FakeElement(tagName) },
  bindUiHoverTip() {},
  escapeHtmlAttr(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },
  markdownHrefToWorkspaceOpenRel(value) {
    const text = String(value || '');
    if (!text || /^(?:https?|mailto|tel|data|blob):/i.test(text)) return '';
    return text.replace(/\\/g, '/');
  },
  workspaceOpenTipPath(raw, rel) { return String(raw || rel || ''); },
});
vm.runInContext(source, context);

async function main() {
  const markedUrl = pathToFileURL(
    path.join(root, 'frontend/node_modules/marked/lib/marked.esm.js'),
  ).href;
  const { marked } = await import(markedUrl);
  context.configureWorkspaceMarkdownRenderer(marked);

  const gif = marked.parse('![预览](media/demo.gif "动画")');
  assert.match(gif, /<img [^>]*class="msg-workspace-image"/);
  assert.match(gif, /data-workspace-media-kind="image"/);
  assert.match(gif, /alt="预览"/);
  assert.match(gif, /title="动画"/);
  assert.match(gif, /\/api\/workspace-media\?rel=media%2Fdemo\.gif/);
  assert.doesNotMatch(gif, /!<img/);

  const external = marked.parse('![外部](https://example.com/demo.gif)');
  assert.match(external, /<img src="https:\/\/example\.com\/demo\.gif" alt="外部">/);
  assert.doesNotMatch(external, /data-workspace-media-kind/);

  const audioLink = marked.parse('[试听](media/demo.mp3)');
  assert.match(audioLink, /data-workspace-markdown-link="1"/);
  assert.match(audioLink, /data-workspace-open="media\/demo\.mp3"/);

  const inlineCode = marked.parse('`[试听](media/demo.mp3)`');
  const fencedCode = marked.parse('```md\n[试听](media/demo.mp3)\n```');
  assert.doesNotMatch(inlineCode, /data-workspace-markdown-link/);
  assert.doesNotMatch(fencedCode, /data-workspace-markdown-link/);

  assert.equal(context.workspaceMediaKind('x.GIF?cache=1'), 'image');
  assert.equal(context.workspaceMediaKind('x.mp3'), 'audio');
  assert.equal(context.workspaceMediaKind('x.mp4'), 'video');
  assert.equal(context.workspaceMediaKind('x.avi'), '');

  const standaloneHost = new FakeElement('p');
  const standaloneLink = new FakeElement('a');
  standaloneLink.textContent = '演示视频';
  standaloneLink.setAttribute('data-workspace-markdown-link', '1');
  standaloneHost.textContent = '演示视频';
  standaloneHost.appendChild(standaloneLink);
  assert.equal(context.standaloneExplicitMediaLinkHost(standaloneLink), standaloneHost);

  const inlineHost = new FakeElement('p');
  const inlineLink = new FakeElement('a');
  inlineLink.textContent = '演示视频';
  inlineLink.setAttribute('data-workspace-markdown-link', '1');
  inlineHost.textContent = '查看演示视频详情';
  inlineHost.appendChild(inlineLink);
  assert.equal(context.standaloneExplicitMediaLinkHost(inlineLink), null);

  const bareLink = new FakeElement('a');
  bareLink.textContent = 'media/demo.mp4';
  const bareHost = new FakeElement('p');
  bareHost.textContent = bareLink.textContent;
  bareHost.appendChild(bareLink);
  assert.equal(context.standaloneExplicitMediaLinkHost(bareLink), null);

  const videoFigure = context.createWorkspaceMediaPreview('media/demo.mp4', '演示视频', 'video');
  const video = videoFigure.children[0];
  const error = videoFigure.children[1];
  assert.equal(video.tagName, 'VIDEO');
  assert.equal(video.controls, true);
  assert.equal(video.preload, 'metadata');
  assert.equal(video.autoplay, false);
  assert.equal(video.playsInline, true);
  assert.match(video.src, /\/api\/workspace-media\?rel=media%2Fdemo\.mp4$/);
  assert.equal(error.hidden, true);
  video.listeners.error();
  assert.equal(video.hidden, true);
  assert.equal(error.hidden, false);

  const audioFigure = context.createWorkspaceMediaPreview('media/demo.mp3', '试听', 'audio');
  const audio = audioFigure.children[0];
  assert.equal(audio.tagName, 'AUDIO');
  assert.equal(audio.controls, true);
  assert.equal(audio.preload, 'metadata');
  assert.equal(audio.autoplay, false);

  console.log('workspace media runtime checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
