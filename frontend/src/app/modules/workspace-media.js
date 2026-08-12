var WORKSPACE_MEDIA_EXTENSIONS = Object.freeze({
    image: Object.freeze(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tif', 'tiff', 'avif', 'jfif']),
    audio: Object.freeze(['mp3', 'wav', 'ogg', 'oga', 'opus', 'm4a', 'aac', 'flac']),
    video: Object.freeze(['mp4', 'webm', 'ogv', 'mov']),
});

function workspaceMediaKind(path) {
    var clean = String(path || '').replace(/[?#].*$/, '').replace(/\\/g, '/');
    var match = /\.([A-Za-z0-9]+)$/.exec(clean);
    var ext = match ? match[1].toLowerCase() : '';
    if (!ext) return '';
    var kinds = Object.keys(WORKSPACE_MEDIA_EXTENSIONS);
    for (var i = 0; i < kinds.length; i += 1) {
        var kind = kinds[i];
        if (WORKSPACE_MEDIA_EXTENSIONS[kind].indexOf(ext) >= 0) return kind;
    }
    return '';
}

function workspaceMediaUrl(rel) {
    return '/api/workspace-media?rel=' + encodeURIComponent(String(rel || ''));
}

function workspaceMediaRelFromMarker(value, expectedKind) {
    var raw = String(value || '').trim();
    var marker = /^#ga-workspace-path=(.+)$/i.exec(raw);
    if (marker) {
        var markerValue = marker[1];
        var rawIdx = markerValue.indexOf('&raw=');
        if (rawIdx >= 0) markerValue = markerValue.slice(0, rawIdx);
        try { raw = decodeURIComponent(markerValue); } catch (e) { raw = markerValue; }
    }
    var rel = markdownHrefToWorkspaceOpenRel(raw);
    var kind = workspaceMediaKind(rel);
    if (!rel || !kind || (expectedKind && kind !== expectedKind)) return '';
    return rel;
}

function workspaceMarkdownLinkHtml(token, parser) {
    var href = String(token && token.href || '');
    var rel = markdownHrefToWorkspaceOpenRel(href);
    if (!rel) return false;
    var label = parser.parseInline((token && token.tokens) || []);
    var title = token && token.title
        ? ' title="' + escapeHtmlAttr(String(token.title)) + '"'
        : '';
    return '<a href="#" class="msg-link-workspace-open" data-workspace-open="'
        + escapeHtmlAttr(rel)
        + '" data-workspace-markdown-link="1" data-ui-tip="'
        + escapeHtmlAttr(workspaceOpenTipPath(href, rel))
        + '"'
        + title
        + '>'
        + label
        + '</a>';
}

function workspaceMarkdownImageHtml(token) {
    var href = String(token && token.href || '');
    var rel = markdownHrefToWorkspaceOpenRel(href);
    if (!rel || workspaceMediaKind(rel) !== 'image') return false;
    var alt = String(token && token.text || '');
    var title = token && token.title
        ? ' title="' + escapeHtmlAttr(String(token.title)) + '"'
        : '';
    return '<img src="'
        + escapeHtmlAttr(workspaceMediaUrl(rel))
        + '" alt="'
        + escapeHtmlAttr(alt)
        + '" class="msg-workspace-image" data-workspace-open="'
        + escapeHtmlAttr(rel)
        + '" data-workspace-media-kind="image"'
        + title
        + '>';
}

function configureWorkspaceMarkdownRenderer(markdownParser) {
    if (!markdownParser || typeof markdownParser.use !== 'function') return;
    markdownParser.use({
        renderer: {
            link: function (token) {
                return workspaceMarkdownLinkHtml(token, this.parser);
            },
            image: function (token) {
                return workspaceMarkdownImageHtml(token);
            },
        },
    });
}

function wrapWorkspaceImageElement(img, rel) {
    if (!img || !rel || img.dataset.workspaceImageReady === '1') return;
    img.dataset.workspaceImageReady = '1';
    img.classList.add('msg-workspace-image');
    img.loading = 'lazy';
    img.decoding = 'async';
    img.src = workspaceMediaUrl(rel);
    img.setAttribute('data-workspace-open', rel);
    img.setAttribute('data-ui-tip', '点击查看图片');
    bindUiHoverTip(img);
    var parent = img.parentElement;
    if (!parent || (parent.tagName === 'A' && parent.classList.contains('msg-workspace-image-link'))) return;
    var link = document.createElement('a');
    link.href = workspaceMediaUrl(rel);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'msg-workspace-image-link';
    link.setAttribute('data-workspace-open', rel);
    if (img.parentNode) img.parentNode.insertBefore(link, img);
    link.appendChild(img);
}

function standaloneExplicitMediaLinkHost(link) {
    if (!link || link.getAttribute('data-workspace-markdown-link') !== '1') return null;
    var host = link.parentElement;
    if (!host || !/^(P|DIV|LI)$/i.test(host.tagName || '')) return null;
    var linkText = String(link.textContent || '').trim();
    var hostText = String(host.textContent || '').trim();
    if (!linkText || hostText !== linkText) return null;
    return host;
}

function createWorkspaceMediaPreview(rel, label, kind) {
    var figure = document.createElement('figure');
    figure.className = 'msg-workspace-media-figure msg-workspace-media-' + kind;
    figure.setAttribute('data-workspace-media-kind', kind);

    var player = document.createElement(kind);
    player.className = 'msg-workspace-media-player';
    player.controls = true;
    player.preload = 'metadata';
    player.autoplay = false;
    if (kind === 'video') player.playsInline = true;
    player.src = workspaceMediaUrl(rel);
    player.setAttribute('aria-label', String(label || rel || kind));
    figure.appendChild(player);

    var error = document.createElement('div');
    error.className = 'msg-workspace-media-error';
    error.hidden = true;
    error.textContent = '无法在浏览器中播放此媒体，可使用系统应用打开。';
    figure.appendChild(error);

    var caption = document.createElement('figcaption');
    var openLink = document.createElement('a');
    openLink.href = '#';
    openLink.className = 'msg-link-workspace-open msg-workspace-media-open';
    openLink.setAttribute('data-workspace-open', rel);
    openLink.setAttribute('data-ui-tip', '使用系统应用打开');
    openLink.textContent = String(label || rel || '使用系统应用打开');
    bindUiHoverTip(openLink);
    caption.appendChild(openLink);
    figure.appendChild(caption);

    player.addEventListener('error', function () {
        player.hidden = true;
        error.hidden = false;
        figure.classList.add('is-error');
    });
    return figure;
}

function upgradeWorkspaceMedia(root) {
    if (!root) return;
    root.querySelectorAll('img[data-workspace-media-kind="image"][data-workspace-open]').forEach(function (img) {
        var rel = img.getAttribute('data-workspace-open') || '';
        if (workspaceMediaKind(rel) === 'image') wrapWorkspaceImageElement(img, rel);
    });
    root.querySelectorAll('img[src^="#ga-workspace-path="]').forEach(function (img) {
        var rel = workspaceMediaRelFromMarker(img.getAttribute('src') || '', 'image');
        if (rel) wrapWorkspaceImageElement(img, rel);
    });
    root.querySelectorAll('a[data-workspace-markdown-link="1"][data-workspace-open]').forEach(function (link) {
        if (link.dataset.workspaceMediaPreview === '1') return;
        var rel = link.getAttribute('data-workspace-open') || '';
        var kind = workspaceMediaKind(rel);
        if (kind !== 'audio' && kind !== 'video') return;
        var host = standaloneExplicitMediaLinkHost(link);
        if (!host || !host.parentNode) return;
        link.dataset.workspaceMediaPreview = '1';
        var figure = createWorkspaceMediaPreview(rel, link.textContent || rel, kind);
        if (String(host.tagName || '').toUpperCase() === 'LI' && typeof host.replaceChildren === 'function') {
            host.replaceChildren(figure);
        } else {
            host.parentNode.replaceChild(figure, host);
        }
    });
}
