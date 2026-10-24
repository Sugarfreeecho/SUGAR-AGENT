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

var workspaceImageMetadataCache = new class extends Map {
    get(key) {
        if (!this.has(key)) return undefined;
        const value = super.get(key);
        this.delete(key);
        this.set(key, value);
        return value;
    }
    set(key, value) {
        this.delete(key);
        super.set(key, value);
        if (this.size > 2048) this.delete(this.keys().next().value);
        return this;
    }
}();
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


// Blob previews share a fetch and URL while any visible node uses the image.
var durableImagePreviews = new Map();
var durableImageObserver = null;
var durableImageVisibilityObserver = null;
var durableImageDownloadQueue = [];
var durableImageDownloads = 0;
function sweepDurableImagePreviews() {
    durableImagePreviews.forEach(function (entry, key) {
        entry.nodes = entry.nodes.filter(function (node) {
            if (node.isConnected) return true;
            if (durableImageVisibilityObserver) durableImageVisibilityObserver.unobserve(node);
            return false;
        });
        if (entry.nodes.length) return;
        if (entry.controller) entry.controller.abort();
        if (entry.url) URL.revokeObjectURL(entry.url);
        durableImagePreviews.delete(key);
    });
    if (!durableImagePreviews.size && durableImageObserver) {
        durableImageObserver.disconnect();
        durableImageObserver = null;
    }
    durableImageDownloadQueue = durableImageDownloadQueue.filter(function (entry) {
        return durableImagePreviews.get(entry.id) === entry;
    });
    if (!durableImagePreviews.size && durableImageVisibilityObserver) {
        durableImageVisibilityObserver.disconnect();
        durableImageVisibilityObserver = null;
    }
}

function queueDurableImagePreview(entry, node) {
    if (entry.url) { node.src = entry.url; return; }
    node.dataset.attachmentDeferred = '1';
    if (entry.started || entry.queued) return;
    if (typeof IntersectionObserver === 'function') {
        if (!durableImageVisibilityObserver) {
            durableImageVisibilityObserver = new IntersectionObserver(function (changes) {
                changes.forEach(function (change) {
                    if (!change.isIntersecting) return;
                    var pending = durableImagePreviews.get(change.target.dataset.attachmentId);
                    durableImageVisibilityObserver.unobserve(change.target);
                    if (pending) enqueue(pending);
                });
            }, { rootMargin: '300px' });
        }
        durableImageVisibilityObserver.observe(node);
    } else enqueue(entry);
    function enqueue(pending) {
        if (pending.started || pending.queued) return;
        pending.queued = true;
        durableImageDownloadQueue.push(pending);
        drainDurableImagePreviews();
    }
}

function drainDurableImagePreviews() {
    // Originals can be large. Keep metadata, navigation and Stop usable while
    // rendering a long history containing many collapsed image/tool rows.
    while (durableImageDownloads < 2 && durableImageDownloadQueue.length) {
        var entry = durableImageDownloadQueue.shift();
        if (durableImagePreviews.get(entry.id) !== entry) continue;
        startDurableImagePreview(entry);
    }
}

function startDurableImagePreview(entry) {
    entry.started = true;
    durableImageDownloads++;
    var options = { credentials: 'same-origin' };
    if (entry.controller) options.signal = entry.controller.signal;
    var timeout = typeof setTimeout === 'function' ? setTimeout(function () {
        if (entry.controller) entry.controller.abort();
    }, 30000) : 0;
    fetch('/api/attachments/' + encodeURIComponent(entry.id), options)
        .then(function (response) { if (!response.ok) throw new Error('Attachment unavailable'); return response.blob(); })
        .then(function (blob) {
            sweepDurableImagePreviews();
            if (durableImagePreviews.get(entry.id) !== entry) return;
            entry.url = URL.createObjectURL(blob);
            entry.nodes.forEach(function (node) {
                delete node.dataset.attachmentDeferred;
                node.src = entry.url;
            });
        }).catch(function () {
            entry.nodes.forEach(function (node) {
                node.alt = '图片暂不可用';
                var card = node.closest && node.closest('.msg-attachment-card, .feed-attachment-card');
                if (card) card.classList.add('is-unavailable');
            });
            if (durableImagePreviews.get(entry.id) === entry) durableImagePreviews.delete(entry.id);
            sweepDurableImagePreviews();
        }).finally(function () {
            if (timeout) clearTimeout(timeout);
            durableImageDownloads--;
            drainDurableImagePreviews();
        });
}

function durableAttachmentImageHost(container) {
    var userMessage = container.classList && container.classList.contains('msg-wrap--user')
        ? container
        : (container.closest ? container.closest('.msg-wrap--user') : null);
    var processRow = container.classList && container.classList.contains('feed-item')
        ? container
        : (container.closest ? container.closest('.feed-item') : null);
    if (!userMessage && !processRow) return { host: container, thumbnail: false, processRow: false };
    var host = userMessage || processRow;
    var selector = userMessage ? '.msg-user-attachment-strip' : '.feed-attachment-strip';
    var strip = host.querySelector(selector);
    if (!strip) {
        strip = document.createElement('div');
        strip.className = userMessage ? 'msg-user-attachment-strip' : (processRow ? 'feed-attachment-strip' : 'msg-attachment-strip');
        strip.setAttribute('role', 'group');
        strip.setAttribute('aria-label', '图片附件');
        if (userMessage) {
            var toolbar = userMessage.querySelector('.msg-toolbar');
            userMessage.insertBefore(strip, toolbar || null);
        } else if (processRow) {
            var feedRow = processRow.querySelector('.feed-row');
            if (feedRow && feedRow.parentNode === processRow) processRow.insertBefore(strip, feedRow.nextSibling);
            else processRow.appendChild(strip);
        }
    }
    return { host: strip, thumbnail: true, processRow: !!processRow };
}

function attachmentImageSizeLabel(item, ref) {
    var bytes = Number((ref && (ref.bytes || ref.size)) || (item && (item.size || item.bytes)) || 0);
    if (!Number.isFinite(bytes) || bytes <= 0) return '图片';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (Math.round(bytes / 102.4) / 10) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (Math.round(bytes / 104857.6) / 10) + ' MB';
    return (Math.round(bytes / 107374182.4) / 10) + ' GB';
}

function createDurableAttachmentCard(item, ref, processRow) {
    var card = document.createElement('figure');
    card.className = processRow ? 'feed-attachment-card' : 'msg-attachment-card';

    var name = String((item && item.name) || (ref && ref.name) || '图片附件');
    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'msg-attachment-preview-trigger';
    trigger.setAttribute('aria-label', '放大查看 ' + name);
    trigger.setAttribute('data-ui-tip', '点击放大查看');

    var img = document.createElement('img');
    img.className = 'msg-workspace-image msg-attachment-image msg-attachment-thumbnail';
    img.dataset.attachmentId = ref.attachmentId;
    img.alt = name;
    var width = Number(ref.width || (item && item.width) || 0);
    var height = Number(ref.height || (item && item.height) || 0);
    if (width > 0) img.width = width;
    if (height > 0) img.height = height;
    img.loading = 'lazy';
    img.decoding = 'async';
    trigger.appendChild(img);
    card.appendChild(trigger);

    var copy = document.createElement('figcaption');
    copy.className = 'msg-attachment-copy';
    var title = document.createElement('span');
    title.className = 'msg-attachment-name';
    title.textContent = name;
    var meta = document.createElement('small');
    meta.className = 'msg-attachment-meta';
    var mediaType = String(ref.mediaType || (item && item.mediaType) || 'image/png');
    var format = mediaType.split('/').pop().toUpperCase().replace('JPEG', 'JPG');
    meta.textContent = attachmentImageSizeLabel(item, ref) + ' · ' + format;
    copy.appendChild(title);
    copy.appendChild(meta);
    card.appendChild(copy);
    return { card: card, image: img };
}

var durableAttachmentPreviewDialog = null;
function ensureDurableAttachmentPreviewDialog() {
    if (durableAttachmentPreviewDialog || !document.body) return durableAttachmentPreviewDialog;
    var dialog = document.createElement('dialog');
    dialog.className = 'attachment-image-viewer';
    dialog.setAttribute('aria-label', '图片预览');
    var header = document.createElement('div');
    header.className = 'attachment-image-viewer-head';
    var caption = document.createElement('span');
    caption.className = 'attachment-image-viewer-caption';
    var controls = document.createElement('div');
    controls.className = 'attachment-image-viewer-controls';
    var zoomOut = createDurableAttachmentPreviewButton('−', '缩小图片', function () {
        zoomDurableAttachmentPreview(dialog, dialog._previewScale / 1.25);
    });
    var zoomLabel = document.createElement('output');
    zoomLabel.className = 'attachment-image-viewer-zoom';
    zoomLabel.setAttribute('aria-label', '图片缩放比例');
    var zoomIn = createDurableAttachmentPreviewButton('+', '放大图片', function () {
        zoomDurableAttachmentPreview(dialog, dialog._previewScale * 1.25);
    });
    var actualSize = createDurableAttachmentPreviewButton('100%', '原始尺寸', function () {
        if (dialog._previewFitSize) zoomDurableAttachmentPreview(dialog, 1 / dialog._previewFitSize.scale, null, true);
    });
    var fit = createDurableAttachmentPreviewButton('适应窗口', '适应窗口', function () {
        zoomDurableAttachmentPreview(dialog, 1, null, true);
    });
    controls.appendChild(zoomOut);
    controls.appendChild(zoomLabel);
    controls.appendChild(zoomIn);
    controls.appendChild(actualSize);
    controls.appendChild(fit);
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'attachment-image-viewer-close';
    close.setAttribute('aria-label', '关闭图片预览');
    close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>';
    close.addEventListener('click', function () { dialog.close(); });
    header.appendChild(caption);
    header.appendChild(controls);
    header.appendChild(close);
    var stage = document.createElement('div');
    stage.className = 'attachment-image-viewer-stage';
    var canvas = document.createElement('div');
    canvas.className = 'attachment-image-viewer-canvas';
    var image = document.createElement('img');
    image.alt = '';
    image.decoding = 'async';
    image.draggable = false;
    canvas.appendChild(image);
    stage.appendChild(canvas);
    var status = document.createElement('div');
    status.className = 'attachment-image-viewer-status';
    status.setAttribute('role', 'status');
    stage.appendChild(status);
    var footer = document.createElement('div');
    footer.className = 'attachment-image-viewer-footer';
    var dimensions = document.createElement('span');
    var hint = document.createElement('span');
    hint.textContent = '滚轮缩放 · 拖拽移动 · 双击切换原始尺寸';
    footer.appendChild(dimensions);
    footer.appendChild(hint);
    var panel = document.createElement('div');
    panel.className = 'attachment-image-viewer-panel';
    panel.appendChild(header);
    panel.appendChild(stage);
    panel.appendChild(footer);
    dialog.appendChild(panel);
    /* 点遮罩关闭：按下点落在图片面板上时不算数。浏览器把 click 派发给按下/松开
       目标的最近公共祖先——在面板里按住、拖到遮罩上松开时祖先就是 dialog 本身，
       只看 event.target 会把拖拽误判成「点了遮罩」而关窗。 */
    var pressOnContent = false;
    dialog.addEventListener('pointerdown', function (event) {
        pressOnContent = event.target !== dialog;
    });
    dialog.addEventListener('pointercancel', function () { pressOnContent = false; });
    dialog.addEventListener('click', function (event) {
        var dismiss = event.target === dialog && !pressOnContent;
        pressOnContent = false;
        if (dismiss) dialog.close();
    });
    stage.addEventListener('wheel', function (event) {
        if (!dialog.open || !dialog._previewFitSize || !event.deltaY) return;
        event.preventDefault();
        var delta = event.deltaY * (event.deltaMode === 1 ? 16 : (event.deltaMode === 2 ? dialog._previewFitSize.viewportHeight : 1));
        zoomDurableAttachmentPreview(dialog, dialog._previewScale * Math.exp(-delta * 0.0016), event);
    }, { passive: false });
    stage.addEventListener('dblclick', function (event) {
        if (!dialog._previewFitSize) return;
        event.preventDefault();
        var actualScale = 1 / dialog._previewFitSize.scale;
        zoomDurableAttachmentPreview(dialog, Math.abs(dialog._previewScale - actualScale) < 0.001 ? 1 : actualScale, event);
    });
    stage.addEventListener('pointerdown', function (event) {
        var fitSize = dialog._previewFitSize;
        if (!fitSize || event.button !== 0 || !durableAttachmentPreviewCanPan(dialog)) return;
        event.preventDefault();
        dialog._previewDrag = { id: event.pointerId, x: event.clientX, y: event.clientY };
        stage.setPointerCapture(event.pointerId);
        stage.classList.add('is-dragging');
    });
    stage.addEventListener('pointermove', function (event) {
        var drag = dialog._previewDrag;
        if (!drag || drag.id !== event.pointerId) return;
        dialog._previewOffsetX += event.clientX - drag.x;
        dialog._previewOffsetY += event.clientY - drag.y;
        drag.x = event.clientX;
        drag.y = event.clientY;
        clampDurableAttachmentPreviewPan(dialog);
        scheduleDurableAttachmentPreviewRender(dialog);
    });
    var stopDrag = function () {
        var drag = dialog._previewDrag;
        dialog._previewDrag = null;
        stage.classList.remove('is-dragging');
        if (drag && stage.hasPointerCapture(drag.id)) stage.releasePointerCapture(drag.id);
    };
    stage.addEventListener('pointerup', stopDrag);
    stage.addEventListener('pointercancel', stopDrag);
    stage.addEventListener('lostpointercapture', stopDrag);
    dialog.addEventListener('keydown', function (event) {
        if (!dialog._previewFitSize || event.ctrlKey || event.metaKey || event.altKey) return;
        if (event.key === '+' || event.key === '=') zoomDurableAttachmentPreview(dialog, dialog._previewScale * 1.25);
        else if (event.key === '-') zoomDurableAttachmentPreview(dialog, dialog._previewScale / 1.25);
        else if (event.key === '0') zoomDurableAttachmentPreview(dialog, 1, null, true);
        else if (event.key === '1') zoomDurableAttachmentPreview(dialog, 1 / dialog._previewFitSize.scale, null, true);
        else return;
        event.preventDefault();
    });
    dialog.addEventListener('close', function () {
        dialog._previewGeneration = (Number(dialog._previewGeneration) || 0) + 1;
        cancelDurableAttachmentPreviewFrames(dialog);
        dialog._previewFitSize = null;
        stopDrag();
        image.onload = null;
        image.onerror = null;
        image.style.visibility = 'hidden';
    });
    if (typeof window.ResizeObserver === 'function') {
        dialog._previewResizeObserver = new window.ResizeObserver(function () {
            if (dialog.open && dialog._previewFitSize) scheduleDurableAttachmentPreviewFit(dialog);
        });
        dialog._previewResizeObserver.observe(canvas);
    }
    window.addEventListener('resize', function () {
        if (dialog.open && dialog._previewFitSize) scheduleDurableAttachmentPreviewFit(dialog);
    });
    document.body.appendChild(dialog);
    dialog._previewImage = image;
    dialog._previewStage = stage;
    dialog._previewCanvas = canvas;
    dialog._previewCaption = caption;
    dialog._previewZoomLabel = zoomLabel;
    dialog._previewControls = [zoomOut, zoomIn, actualSize, fit];
    dialog._previewStatus = status;
    dialog._previewDimensions = dimensions;
    durableAttachmentPreviewDialog = dialog;
    return dialog;
}

function createDurableAttachmentPreviewButton(label, title, onClick) {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'attachment-image-viewer-action';
    button.textContent = label;
    button.title = title;
    button.setAttribute('aria-label', title);
    button.addEventListener('click', onClick);
    return button;
}

function measureDurableAttachmentPreviewFit(dialog) {
    var image = dialog && dialog._previewImage;
    var canvas = dialog && dialog._previewCanvas;
    if (!image || !canvas || !image.naturalWidth || !image.naturalHeight) return null;
    var rect = canvas.getBoundingClientRect();
    var availableWidth = rect.width;
    var availableHeight = rect.height;
    if (availableWidth <= 0 || availableHeight <= 0) return null;
    var fitScale = Math.min(1, availableWidth / image.naturalWidth, availableHeight / image.naturalHeight);
    return { width: image.naturalWidth * fitScale, height: image.naturalHeight * fitScale,
        scale: fitScale, viewportWidth: availableWidth, viewportHeight: availableHeight, left: rect.left, top: rect.top };
}

function durableAttachmentPreviewCanPan(dialog) {
    var fitSize = dialog._previewFitSize;
    return fitSize && (fitSize.width * dialog._previewScale > fitSize.viewportWidth
        || fitSize.height * dialog._previewScale > fitSize.viewportHeight);
}

function clampDurableAttachmentPreviewPan(dialog) {
    var fitSize = dialog._previewFitSize;
    if (!fitSize) return;
    var maxX = Math.max(0, (fitSize.width * dialog._previewScale - fitSize.viewportWidth) / 2);
    var maxY = Math.max(0, (fitSize.height * dialog._previewScale - fitSize.viewportHeight) / 2);
    dialog._previewOffsetX = Math.max(-maxX, Math.min(maxX, dialog._previewOffsetX || 0));
    dialog._previewOffsetY = Math.max(-maxY, Math.min(maxY, dialog._previewOffsetY || 0));
}

function zoomDurableAttachmentPreview(dialog, scale, anchor, center) {
    var fitSize = dialog._previewFitSize;
    if (!dialog.open || !fitSize) return;
    var previousScale = dialog._previewScale || 1;
    // Even a very large original must be reachable at 100%, with up to 400% for inspecting pixels.
    var nextScale = Math.max(0.2, Math.min(Math.max(8, 4 / fitSize.scale), scale));
    var ratio = nextScale / previousScale;
    var anchorX = anchor && Number.isFinite(anchor.clientX) ? anchor.clientX - fitSize.left - fitSize.viewportWidth / 2 : 0;
    var anchorY = anchor && Number.isFinite(anchor.clientY) ? anchor.clientY - fitSize.top - fitSize.viewportHeight / 2 : 0;
    dialog._previewOffsetX = center ? 0 : anchorX - (anchorX - dialog._previewOffsetX) * ratio;
    dialog._previewOffsetY = center ? 0 : anchorY - (anchorY - dialog._previewOffsetY) * ratio;
    dialog._previewScale = nextScale;
    clampDurableAttachmentPreviewPan(dialog);
    scheduleDurableAttachmentPreviewRender(dialog, !!center);
}

function scheduleDurableAttachmentPreviewRender(dialog, sharp) {
    dialog._previewRenderSharp = !!sharp;
    if (!dialog.open || dialog._previewZoomFrame) return;
    dialog._previewZoomFrame = window.requestAnimationFrame(function () {
        dialog._previewZoomFrame = 0;
        if (dialog.open && dialog._previewFitSize) {
            applyDurableAttachmentPreviewScale(dialog, dialog._previewScale, dialog._previewRenderSharp);
        }
    });
}

function applyDurableAttachmentPreviewScale(dialog, scale, sharp) {
    var image = dialog && dialog._previewImage;
    var fitSize = dialog && dialog._previewFitSize;
    if (!image || !fitSize) return;
    var width = fitSize.width * scale;
    var height = fitSize.height * scale;
    var pixelRatio = window.devicePixelRatio || 1;
    var left = (fitSize.viewportWidth - width) / 2 + dialog._previewOffsetX;
    var top = (fitSize.viewportHeight - height) / 2 + dialog._previewOffsetY;
    // Align in screen coordinates: the centered panel itself can start on a fractional pixel.
    left = Math.round((fitSize.left + left) * pixelRatio) / pixelRatio - fitSize.left;
    top = Math.round((fitSize.top + top) * pixelRatio) / pixelRatio - fitSize.top;
    var raster = dialog._previewRasterSize;
    if (dialog._previewSettleTimer) window.clearTimeout(dialog._previewSettleTimer);
    dialog._previewSettleTimer = 0;
    if (sharp || !raster) {
        // Commit original detail once interaction stops, instead of resizing and painting every frame.
        image.style.width = width + 'px';
        image.style.height = height + 'px';
        image.style.left = left + 'px';
        image.style.top = top + 'px';
        image.style.transform = 'none';
        image.style.willChange = '';
        dialog._previewRasterSize = { width: width, height: height, left: left, top: top };
    } else {
        // Keep the last sharp raster stable during input; the compositor handles the movement.
        if (image.style.willChange !== 'transform') image.style.willChange = 'transform';
        image.style.transform = 'translate3d(' + (left - raster.left) + 'px, ' + (top - raster.top)
            + 'px, 0) scale(' + (width / raster.width) + ')';
        var generation = dialog._previewGeneration;
        dialog._previewSettleTimer = window.setTimeout(function () {
            dialog._previewSettleTimer = 0;
            if (dialog.open && dialog._previewGeneration === generation) scheduleDurableAttachmentPreviewRender(dialog, true);
        }, 120);
    }
    var zoomText = Math.round(fitSize.scale * scale * 100) + '%';
    var now = Date.now();
    // Text replacement also invalidates layout. Keep the live indicator responsive at 10 Hz.
    if (sharp || !raster || now - (dialog._previewZoomLabelUpdatedAt || 0) >= 100) {
        if (dialog._previewZoomLabel.textContent !== zoomText) dialog._previewZoomLabel.textContent = zoomText;
        dialog._previewZoomLabelUpdatedAt = now;
    }
    dialog._previewStage.classList.toggle('can-pan', !!durableAttachmentPreviewCanPan(dialog));
}

function cancelDurableAttachmentPreviewFrames(dialog) {
    if (dialog._previewZoomFrame) window.cancelAnimationFrame(dialog._previewZoomFrame);
    if (dialog._previewFitFrame) window.cancelAnimationFrame(dialog._previewFitFrame);
    if (dialog._previewSettleTimer) window.clearTimeout(dialog._previewSettleTimer);
    dialog._previewZoomFrame = 0;
    dialog._previewFitFrame = 0;
    dialog._previewSettleTimer = 0;
    dialog._previewImage.style.willChange = '';
}

function scheduleDurableAttachmentPreviewFit(dialog) {
    if (!dialog.open || dialog._previewFitFrame) return;
    var generation = dialog._previewGeneration;
    dialog._previewFitFrame = window.requestAnimationFrame(function () {
        dialog._previewFitFrame = 0;
        if (dialog._previewGeneration !== generation || !dialog.open) return;
        var fitSize = measureDurableAttachmentPreviewFit(dialog);
        if (!fitSize) return;
        dialog._previewFitSize = fitSize;
        clampDurableAttachmentPreviewPan(dialog);
        applyDurableAttachmentPreviewScale(dialog, Number(dialog._previewScale) || 1, true);
        dialog._previewImage.style.visibility = '';
        dialog._previewStatus.hidden = true;
        dialog._previewDimensions.textContent = dialog._previewImage.naturalWidth + ' × ' + dialog._previewImage.naturalHeight;
        dialog._previewControls.forEach(function (button) { button.disabled = false; });
    });
}

function resetDurableAttachmentPreviewZoom(dialog) {
    var image = dialog && dialog._previewImage;
    if (!image) return;
    cancelDurableAttachmentPreviewFrames(dialog);
    var generation = (Number(dialog._previewGeneration) || 0) + 1;
    dialog._previewGeneration = generation;
    dialog._previewScale = 1;
    dialog._previewOffsetX = 0;
    dialog._previewOffsetY = 0;
    dialog._previewFitSize = null;
    dialog._previewRasterSize = null;
    image.style.transform = 'none';
    image.style.visibility = 'hidden';
    dialog._previewZoomLabel.textContent = '—';
    dialog._previewDimensions.textContent = '';
    dialog._previewStatus.hidden = false;
    dialog._previewStatus.textContent = '正在加载原图…';
    dialog._previewControls.forEach(function (button) { button.disabled = true; });
    dialog._previewStage.classList.remove('can-pan');
    var showError = function () {
        if (dialog._previewGeneration !== generation || !dialog.open) return;
        dialog._previewStatus.textContent = '图片加载失败，请关闭后重试';
    };
    image.onerror = showError;
    var fitWhenReady = function () {
        if (dialog._previewGeneration === generation) scheduleDurableAttachmentPreviewFit(dialog);
    };
    if (typeof image.decode === 'function') {
        image.onload = null;
        image.decode().then(fitWhenReady, function () {
            if (dialog._previewGeneration !== generation) return;
            image.onload = fitWhenReady;
            if (image.complete && image.naturalWidth) fitWhenReady();
            else if (image.complete) showError();
        });
    } else {
        image.onload = fitWhenReady;
        if (image.complete && image.naturalWidth) fitWhenReady();
        else if (image.complete) showError();
    }
}

function openChatImagePreview(thumbnail) {
    if (!thumbnail) return;
    var dialog = ensureDurableAttachmentPreviewDialog();
    if (!dialog) return;
    var source = thumbnail.src || thumbnail.currentSrc;
    if (!source) return;
    if (dialog._previewImage.src !== source) dialog._previewImage.src = source;
    dialog._previewImage.alt = thumbnail.alt || '图片预览';
    dialog._previewCaption.textContent = thumbnail.alt || '图片预览';
    if (!dialog.open) {
        if (typeof dialog.showModal === 'function') dialog.showModal();
        else dialog.setAttribute('open', '');
    }
    resetDurableAttachmentPreviewZoom(dialog);
}

if (typeof document !== 'undefined' && typeof window !== 'undefined' && !window.__durableAttachmentPreviewBound) {
    window.__durableAttachmentPreviewBound = true;
    document.addEventListener('click', function (event) {
        var target = event.target;
        if (!target || !target.closest) return;
        var trigger = target.closest('.msg-attachment-preview-trigger');
        var image = target.closest('img') || (trigger && trigger.querySelector('img'));
        if (!image || image.closest('.attachment-image-viewer')) return;
        var inChatContent = !!image.closest('.message, .feed-item');
        var durableAttachment = image.classList.contains('msg-attachment-image');
        var composerAttachment = !!image.closest('.composer-attachment-preview');
        if (!inChatContent && !durableAttachment && !composerAttachment && !trigger) return;
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        event.stopPropagation();
        openChatImagePreview(image);
    }, true);
}

function renderDurableAttachmentImages(container, references) {
    if (!container || !Array.isArray(references) || !references.length) return;
    var imageReferences = references.filter(function (item) {
        var ref = item && (item.attachment || item);
        return !!(ref && /^sha256:[a-f0-9]{64}$/.test(ref.attachmentId || ''));
    });
    if (!imageReferences.length) return;
    var imageHost = durableAttachmentImageHost(container);
    imageReferences.forEach(function (item) {
        var ref = item && (item.attachment || item);
        if (imageHost.host.querySelector('[data-attachment-id="' + ref.attachmentId + '"]')) return;
        var previewImage;
        if (imageHost.thumbnail) {
            var attachmentCard = createDurableAttachmentCard(item, ref, imageHost.processRow);
            imageHost.host.appendChild(attachmentCard.card);
            previewImage = attachmentCard.image;
        } else {
            previewImage = document.createElement('img');
            previewImage.className = 'msg-workspace-image msg-attachment-image';
            previewImage.dataset.attachmentId = ref.attachmentId;
            previewImage.alt = ref.name || 'Image attachment';
            previewImage.width = ref.width;
            previewImage.height = ref.height;
            previewImage.style.maxWidth = '100%';
            previewImage.style.height = 'auto';
            previewImage.style.maxHeight = '60vh';
            previewImage.style.objectFit = 'contain';
            previewImage.loading = 'lazy';
            previewImage.decoding = 'async';
            imageHost.host.appendChild(previewImage);
        }
        var entry = durableImagePreviews.get(ref.attachmentId);
        if (entry) {
            entry.nodes.push(previewImage);
            queueDurableImagePreview(entry, previewImage);
            return;
        }
        entry = { id: ref.attachmentId, nodes: [previewImage], url: '', controller: typeof AbortController === 'function' ? new AbortController() : null };
        durableImagePreviews.set(ref.attachmentId, entry);
        if (!durableImageObserver) {
            durableImageObserver = new MutationObserver(sweepDurableImagePreviews);
            durableImageObserver.observe(document.body, { childList: true, subtree: true });
        }
        queueDurableImagePreview(entry, previewImage);
    });
}
