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
const renderingSource = fs.readFileSync(
  path.join(root, 'frontend/src/app/modules/message-rendering.js'),
  'utf8',
);

function between(sourceText, startMarker, endMarker) {
  const start = sourceText.indexOf(startMarker);
  const end = sourceText.indexOf(endMarker, start);
  assert.ok(start >= 0 && end > start, `missing source section: ${startMarker}`);
  return sourceText.slice(start, end);
}

class FakeElement {
  constructor(tagName) {
    this.tagName = String(tagName || '').toUpperCase();
    this.children = [];
    this.attributes = Object.create(null);
    this.dataset = Object.create(null);
    this.className = '';
    this.classList = { contains: (name) => this.className.split(/\s+/).includes(name), add: (...names) => {
      const tokens = new Set(this.className.split(/\s+/).filter(Boolean));
      names.forEach((name) => tokens.add(name));
      this.className = Array.from(tokens).join(' ');
    } };
    this.parentElement = null;
    this.parentNode = null;
    this.textContent = '';
    this.hidden = false;
    this.listeners = Object.create(null);
    this.srcWrites = 0;
    this.style = {
      aspectRatio: '',
      values: Object.create(null),
      setProperty: (name, value) => { this.style.values[name] = String(value); },
    };
  }
  appendChild(child) {
    child.parentElement = this;
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  setAttribute(name, value) {
    if (name === 'src') this.srcWrites += 1;
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
  set src(value) { this.setAttribute('src', value); }
  get src() { return this.getAttribute('src'); }
  addEventListener(name, handler) {
    this.listeners[name] = handler;
  }
  removeEventListener(name, handler) {
    if (this.listeners[name] === handler) delete this.listeners[name];
  }
}

const hoverTipBindings = [];
let historyImageTimeout = null;
const context = vm.createContext({
  console,
  document: { createElement: (tagName) => new FakeElement(tagName) },
  currentSessionId: 'history-session',
  requestAnimationFrame(callback) { callback(); return 1; },
  setTimeout(callback, delay) {
    assert.ok(delay === 1000 || delay === 2400);
    if (delay === 2400) historyImageTimeout = callback;
    return delay;
  },
  clearTimeout(timer) {
    if (timer === 2400) historyImageTimeout = null;
  },
  bindUiHoverTip(element) { hoverTipBindings.push(element); },
  escapeHtmlAttr(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },
  markdownHrefToWorkspaceOpenRel(value) {
    let text = String(value || '');
    if (!text || /^(?:https?|mailto|tel|data|blob):/i.test(text)) return '';
    try { text = decodeURIComponent(text); } catch (_error) { /* keep raw */ }
    return text.replace(/\\/g, '/');
  },
  workspaceOpenTipPath(raw, rel) { return String(raw || rel || ''); },
});
vm.runInContext(source, context);
context.LINKIFY_EXT_FRAGMENT = 'md|png|gif|mp3|mp4';
vm.runInContext(
  between(
    renderingSource,
    'function trimTrailingPathPunct',
    '/** 可链转「工作区下文件」的已知后缀',
  ),
  context,
);
vm.runInContext(
  between(
    renderingSource,
    'function waitForHistoryImageLayout',
    'function waitForChatScrollAfterHistoryLoad',
  ),
  context,
);
vm.runInContext(
  between(
    renderingSource,
    'function stripMarkdownPathLinkWrapper',
    'function escapeMarkdownSingleTildes',
  ),
  context,
);

async function main() {
  const markedUrl = pathToFileURL(
    path.join(root, 'frontend/node_modules/marked/lib/marked.esm.js'),
  ).href;
  const { marked } = await import(markedUrl);
  context.configureWorkspaceMarkdownRenderer(marked);

  const normalize = (markdown) => context.normalizeExplicitMarkdownPathLinksOutsideFences(markdown);
  const encodedMarkdownPath = (value) => String(value).replace(/\\/g, '%5C');

  const parenthesizedDirectory = String.raw`D:\AI\AI Agent\MyAgent Developer\docs\Change Request（CR）`;
  assert.equal(context.cleanPathTokenForLink(`"${parenthesizedDirectory}"`), parenthesizedDirectory);
  assert.equal(context.cleanPathTokenForLink(parenthesizedDirectory), parenthesizedDirectory);
  assert.equal(context.cleanPathTokenForLink(String.raw`D:\docs\Change Request(CR)`), String.raw`D:\docs\Change Request(CR)`);
  assert.equal(context.cleanPathTokenForLink(String.raw`D:\docs\report.md)`), String.raw`D:\docs\report.md`);
  assert.equal(context.cleanPathTokenForLink(String.raw`D:\docs\report.md。`), String.raw`D:\docs\report.md`);

  const windowsPath = String.raw`D:\AI\AI Agent\MyAgent Developer\workspace\C盘清理扫描\C盘清理报告.md`;
  const windowsLink = normalize(`[C盘清理扫描/C盘清理报告.md]("${windowsPath}")`);
  assert.equal(windowsLink, `[C盘清理扫描/C盘清理报告.md](<${encodedMarkdownPath(windowsPath)}>)`);
  const windowsHtml = marked.parse(windowsLink);
  assert.match(windowsHtml, /data-workspace-markdown-link="1"/);
  assert.match(windowsHtml, /data-workspace-open="D:\/AI\/AI Agent\/MyAgent Developer\/workspace\/C盘清理扫描\/C盘清理报告\.md"/);
  assert.doesNotMatch(windowsHtml, /C盘清理报告\.md\)<\/a>/);

  const relativeLink = normalize('[报告]("workspace/C盘清理扫描/清理 报告.md")');
  assert.equal(relativeLink, '[报告](<workspace/C盘清理扫描/清理 报告.md>)');
  assert.match(marked.parse(relativeLink), /data-workspace-open="workspace\/C盘清理扫描\/清理 报告\.md"/);

  const parenthesizedPath = String.raw`D:\reports\C盘清理(最终版).md`;
  const parenthesizedLink = normalize(`[报告]("${parenthesizedPath}")`);
  assert.equal(parenthesizedLink, `[报告](<${encodedMarkdownPath(parenthesizedPath)}>)`);
  assert.match(marked.parse(parenthesizedLink), /data-workspace-open="D:\/reports\/C盘清理\(最终版\)\.md"/);

  const uncPath = String.raw`\\fileserver\shared reports\清理报告.md`;
  const uncLink = normalize(`[共享报告]("${uncPath}")`);
  assert.equal(uncLink, `[共享报告](<${encodedMarkdownPath(uncPath)}>)`);
  assert.match(marked.parse(uncLink), /data-workspace-open="\/\/fileserver\/shared reports\/清理报告\.md"/);

  const apostrophePath = String.raw`D:\Team's Files\report.md`;
  assert.equal(
    normalize(`[报告](${apostrophePath})`),
    `[报告](<${encodedMarkdownPath(apostrophePath)}>)`,
  );

  const spacedImage = normalize('![预览]("media/清理 报告.gif")');
  assert.equal(spacedImage, '![预览](<media/清理 报告.gif>)');
  assert.match(marked.parse(spacedImage), /class="msg-workspace-image"/);

  const titledImage = normalize('![预览](media/demo.gif "动画")');
  assert.equal(titledImage, '![预览](media/demo.gif "动画")');
  assert.equal(normalize('[站点](https://example.com/a_(b).md)'), '[站点](https://example.com/a_(b).md)');
  assert.equal(
    normalize('```md\n[报告]("workspace/清理 报告.md")\n```'),
    '```md\n[报告]("workspace/清理 报告.md")\n```',
  );

  const gif = marked.parse('![预览](media/demo.gif "动画")');
  assert.match(gif, /<img [^>]*class="msg-workspace-image"/);
  assert.match(gif, /data-workspace-media-kind="image"/);
  assert.match(gif, /loading="lazy"/);
  assert.match(gif, /decoding="async"/);
  assert.match(gif, /alt="预览"/);
  assert.match(gif, /title="动画"/);
  assert.match(gif, /\/api\/workspace-media\?rel=media%2Fdemo\.gif/);
  assert.doesNotMatch(gif, /!<img/);

  const external = marked.parse('![外部](https://example.com/demo.gif)');
  assert.match(external, /<img src="https:\/\/example\.com\/demo\.gif" alt="外部">/);
  assert.doesNotMatch(external, /data-workspace-media-kind/);

  const metadataImage = new FakeElement('img');
  metadataImage.className = 'msg-workspace-image';
  metadataImage.setAttribute('data-workspace-open', 'media/sized.png');
  context.fetch = async (url, options) => {
    assert.equal(url, '/api/workspace-image-metadata');
    assert.equal(options.method, 'POST');
    assert.equal(options.cache, 'no-store');
    assert.deepEqual(JSON.parse(options.body), { rels: ['media/sized.png'] });
    return {
      ok: true,
      async json() {
        return {
          ok: true,
          images: [{ rel: 'media/sized.png', width: 800, height: 600, version: 'v1' }],
        };
      },
    };
  };
  assert.equal(await context.prepareWorkspaceImageLayout({
    querySelectorAll(selector) {
      assert.equal(selector, 'img.msg-workspace-image[data-workspace-open]');
      return [metadataImage];
    },
  }), true);
  assert.equal(metadataImage.getAttribute('width'), '800');
  assert.equal(metadataImage.getAttribute('height'), '600');
  assert.equal(metadataImage.getAttribute('data-workspace-image-sized'), '1');
  assert.equal(metadataImage.style.values['--msg-image-width'], '800px');
  assert.equal(metadataImage.style.values['--msg-image-height-bound-width'], '106.6667vh');
  assert.equal(metadataImage.style.aspectRatio, '800 / 600');
  const cachedSizedImage = context.workspaceMarkdownImageHtml({
    href: 'media/sized.png', text: '尺寸图', title: null,
  });
  assert.match(cachedSizedImage, /width="800" height="600"/);
  assert.match(cachedSizedImage, /data-workspace-image-sized="1"/);
  assert.match(cachedSizedImage, /&amp;v=v1/);
  assert.equal(metadataImage.src, '/api/workspace-media?rel=media%2Fsized.png&v=v1');

  // Reusing a filename and dimensions must still refresh both inline and full-size URLs.
  const fullSizeLink = new FakeElement('a');
  fullSizeLink.className = 'msg-workspace-image-link';
  fullSizeLink.appendChild(metadataImage);
  const imageRoot = { querySelectorAll() { return [metadataImage]; } };
  const requests = [];
  context.fetch = (_url, options) => new Promise((resolve) => requests.push({ options, resolve }));
  const older = context.prepareWorkspaceImageLayout(imageRoot);
  const newer = context.prepareWorkspaceImageLayout(imageRoot);
  const respond = (request, version) => request.resolve({
    ok: true,
    json: async () => ({ ok: true, images: [{ rel: 'media/sized.png', width: 800, height: 600, version }] }),
  });
  respond(requests[1], 'v3');
  await newer;
  assert.equal(metadataImage.src, '/api/workspace-media?rel=media%2Fsized.png&v=v3');
  assert.equal(fullSizeLink.href, metadataImage.src);
  const writesAfterNewVersion = metadataImage.srcWrites;
  respond(requests[0], 'v2');
  await older;
  assert.equal(metadataImage.srcWrites, writesAfterNewVersion, 'late metadata must not reload or roll back an image');
  assert.equal(context.workspaceMediaUrl('media/sized.png'), metadataImage.src);

  // Live Markdown images request fresh metadata, coalesced across new elements.
  requests.length = 0;
  const liveImages = [new FakeElement('img'), new FakeElement('img')];
  liveImages.forEach((img) => {
    const link = new FakeElement('a');
    link.className = 'msg-workspace-image-link';
    link.appendChild(img);
    context.wrapWorkspaceImageElement(img, 'media/sized.png');
  });
  await Promise.resolve();
  assert.equal(requests.length, 1);
  assert.deepEqual(JSON.parse(requests[0].options.body), { rels: ['media/sized.png'] });
  respond(requests[0], 'v4');
  await new Promise((resolve) => setImmediate(resolve));
  liveImages.forEach((img) => {
    assert.equal(img.src, '/api/workspace-media?rel=media%2Fsized.png&v=v4');
    assert.equal(img.parentElement.href, img.src);
  });

  context.fetch = async () => { throw new Error('offline'); };
  const usableSrc = liveImages[0].src;
  await context.prepareWorkspaceImageLayout({ querySelectorAll() { return liveImages; } });
  assert.equal(liveImages[0].src, usableSrc, 'metadata failure preserves the preview');

  const audioLink = marked.parse('[试听](media/demo.mp3)');
  assert.match(audioLink, /data-workspace-markdown-link="1"/);
  assert.match(audioLink, /data-workspace-open="media\/demo\.mp3"/);

  const markdownFileLink = new FakeElement('a');
  markdownFileLink.setAttribute('data-workspace-markdown-link', '1');
  markdownFileLink.setAttribute('data-workspace-open', 'docs/report.md');
  markdownFileLink.setAttribute('data-ui-tip', 'docs/report.md');
  context.upgradeWorkspaceMedia({
    querySelectorAll(selector) {
      if (selector === 'a[data-workspace-markdown-link="1"][data-workspace-open]') {
        return [markdownFileLink];
      }
      return [];
    },
  });
  assert.ok(
    hoverTipBindings.includes(markdownFileLink),
    'standard Markdown file links must bind their hover tooltip after rendering',
  );

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

  const pendingImage = new FakeElement('img');
  pendingImage.complete = false;
  const pendingLayout = context.waitForHistoryImageLayout('history-session', 'smooth-bottom', {
    querySelectorAll(selector) {
      assert.equal(selector, '.message img');
      return [pendingImage];
    },
  });
  assert.equal(pendingImage.loading, 'eager');
  assert.equal(typeof pendingImage.listeners.load, 'function');
  pendingImage.complete = true;
  pendingImage.listeners.load();
  assert.equal(await pendingLayout, true);
  assert.equal(historyImageTimeout, null);

  const slowImage = new FakeElement('img');
  slowImage.complete = false;
  const timedOutLayout = context.waitForHistoryImageLayout('history-session', 'smooth-bottom', {
    querySelectorAll() { return [slowImage]; },
  });
  assert.equal(typeof historyImageTimeout, 'function');
  historyImageTimeout();
  assert.equal(await timedOutLayout, false);
  assert.equal(slowImage.listeners.load, undefined);
  assert.equal(slowImage.getAttribute('data-history-image-fallback'), '1');

  console.log('workspace media runtime checks passed');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
