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
    var url = '/api/workspace-media?rel=' + encodeURIComponent(String(rel || ''));
    var metadata = workspaceImageMetadataCache.get(String(rel || ''));
    return metadata && metadata.version ? url + '&v=' + encodeURIComponent(metadata.version) : url;
}

var workspaceImageMetadataCache = new Map();
var workspaceImageMetadataRequestId = 0;
var pendingWorkspaceImages = new Set();

function queueWorkspaceImageRefresh(img) {
    pendingWorkspaceImages.add(img);
    if (pendingWorkspaceImages.size !== 1) return;
    // Coalesce images from messages rendered in the same turn, including history.
    Promise.resolve().then(function () {
        var images = Array.from(pendingWorkspaceImages);
        pendingWorkspaceImages.clear();
        return prepareWorkspaceImages(images);
    }).catch(function () { /* Keep the original image usable if metadata is unavailable. */ });
}

function normalizeWorkspaceImageMetadata(raw) {
    var width = Math.round(Number(raw && raw.width));
    var height = Math.round(Number(raw && raw.height));
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
    return {
        width: width,
        height: height,
        version: String(raw && raw.version || ''),
    };
}

function applyWorkspaceImageMetadata(img, metadata) {
    metadata = normalizeWorkspaceImageMetadata(metadata);
    if (!img || !metadata) return false;
    img.setAttribute('width', String(metadata.width));
    img.setAttribute('height', String(metadata.height));
    img.setAttribute('data-workspace-image-sized', '1');
    if (img.style) {
        var heightBoundWidth = Math.round(800000 * metadata.width / metadata.height) / 10000;
        img.style.setProperty('--msg-image-width', metadata.width + 'px');
        img.style.setProperty('--msg-image-height-bound-width', heightBoundWidth + 'vh');
        img.style.aspectRatio = metadata.width + ' / ' + metadata.height;
    }
    var rel = String(img.getAttribute('data-workspace-open') || '');
    if (rel && metadata.version) {
        var url = '/api/workspace-media?rel=' + encodeURIComponent(rel)
            + '&v=' + encodeURIComponent(metadata.version);
        // A changed URL also invalidates an already decoded, same-path image.
        if (img.getAttribute('src') !== url) img.setAttribute('src', url);
        var link = img.parentElement;
        if (link && link.classList.contains('msg-workspace-image-link')) link.href = url;
    }
    return true;
}

function workspaceImageMetadataHtmlAttrs(rel) {
    var metadata = normalizeWorkspaceImageMetadata(workspaceImageMetadataCache.get(String(rel || '')));
    if (!metadata) return '';
    var heightBoundWidth = Math.round(800000 * metadata.width / metadata.height) / 10000;
    return ' width="' + metadata.width
        + '" height="' + metadata.height
        + '" data-workspace-image-sized="1" style="--msg-image-width:'
        + metadata.width + 'px;--msg-image-height-bound-width:' + heightBoundWidth
        + 'vh;aspect-ratio:' + metadata.width + ' / ' + metadata.height + '"';
}

function prepareWorkspaceImageLayout(root) {
    if (!root) return Promise.resolve(false);
    return prepareWorkspaceImages(Array.prototype.slice.call(
        root.querySelectorAll('img.msg-workspace-image[data-workspace-open]')
    ));
}

function prepareWorkspaceImages(images) {
    if (!images.length || typeof fetch !== 'function') return Promise.resolve(true);
    var requestId = ++workspaceImageMetadataRequestId;
    var imagesByRel = new Map();
    images.forEach(function (img) {
        var rel = String(img.getAttribute('data-workspace-open') || '').trim();
        if (!rel) return;
        if (!imagesByRel.has(rel)) imagesByRel.set(rel, []);
        imagesByRel.get(rel).push(img);
        applyWorkspaceImageMetadata(img, workspaceImageMetadataCache.get(rel));
    });
    var rels = Array.from(imagesByRel.keys());
    if (!rels.length) return Promise.resolve(true);
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timeout = setTimeout(function () {
        if (controller) controller.abort();
    }, 1000);
    var requests = [];
    for (var offset = 0; offset < rels.length; offset += 128) {
        var requestOptions = {
            method: 'POST',
            cache: 'no-store',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rels: rels.slice(offset, offset + 128) }),
        };
        if (controller) requestOptions.signal = controller.signal;
        requests.push(fetch('/api/workspace-image-metadata', requestOptions).then(function (response) {
            if (!response.ok) return null;
            return response.json().catch(function () { return null; });
        }).catch(function () { return null; }));
    }
    return Promise.all(requests).then(function (responses) {
        var applied = false;
        responses.forEach(function (payload) {
            var entries = payload && payload.ok && Array.isArray(payload.images) ? payload.images : [];
            entries.forEach(function (entry) {
                var rel = String(entry && entry.rel || '');
                var metadata = normalizeWorkspaceImageMetadata(entry);
                if (!rel || !metadata) return;
                var cached = workspaceImageMetadataCache.get(rel);
                // An older request can finish after a newer render's request.
                if (cached && cached.requestId > requestId) {
                    metadata = cached;
                } else {
                    metadata.requestId = requestId;
                    workspaceImageMetadataCache.set(rel, metadata);
                }
                (imagesByRel.get(rel) || []).forEach(function (img) {
                    if (applyWorkspaceImageMetadata(img, metadata)) applied = true;
                });
            });
        });
        return applied;
    }).finally(function () {
        clearTimeout(timeout);
    });
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
    var dimensions = workspaceImageMetadataHtmlAttrs(rel);
    return '<img loading="lazy" decoding="async" src="'
        + escapeHtmlAttr(workspaceMediaUrl(rel))
        + '" alt="'
        + escapeHtmlAttr(alt)
        + '" class="msg-workspace-image" data-workspace-open="'
        + escapeHtmlAttr(rel)
        + '" data-workspace-media-kind="image"'
        + dimensions
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
    applyWorkspaceImageMetadata(img, workspaceImageMetadataCache.get(String(rel || '')));
    img.loading = 'lazy';
    img.decoding = 'async';
    img.src = workspaceMediaUrl(rel);
    img.setAttribute('data-workspace-open', rel);
    queueWorkspaceImageRefresh(img);
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
        // These links are emitted directly by the Markdown renderer after the
        // document-wide tooltip initialization has already run. Bind their
        // data-ui-tip here even when they are ordinary (non-media) files.
        bindUiHoverTip(link);
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
