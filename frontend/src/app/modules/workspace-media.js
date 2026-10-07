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


// Blob previews share a fetch and URL while any visible node uses the image.
var durableImagePreviews = new Map();
var durableImageObserver = null;
function sweepDurableImagePreviews() {
    durableImagePreviews.forEach(function (entry, key) {
        entry.nodes = entry.nodes.filter(function (node) { return node.isConnected; });
        if (entry.nodes.length) return;
        if (entry.controller) entry.controller.abort();
        if (entry.url) URL.revokeObjectURL(entry.url);
        durableImagePreviews.delete(key);
    });
    if (!durableImagePreviews.size && durableImageObserver) {
        durableImageObserver.disconnect();
        durableImageObserver = null;
    }
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
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'attachment-image-viewer-close';
    close.setAttribute('aria-label', '关闭图片预览');
    close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>';
    close.addEventListener('click', function () { dialog.close(); });
    header.appendChild(caption);
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
    var panel = document.createElement('div');
    panel.className = 'attachment-image-viewer-panel';
    panel.appendChild(header);
    panel.appendChild(stage);
    dialog.appendChild(panel);
    dialog.addEventListener('click', function (event) {
        if (event.target === dialog) dialog.close();
    });
    stage.addEventListener('wheel', function (event) {
        if (!dialog.open || !dialog._previewFitSize || !event.deltaY) return;
        event.preventDefault();
        var previousScale = Number(dialog._previewScale) || 1;
        var delta = event.deltaY * (event.deltaMode === 1 ? 16 : (event.deltaMode === 2 ? dialog._previewFitSize.viewportHeight : 1));
        var nextScale = Math.max(0.2, Math.min(8, previousScale * Math.exp(-delta * 0.0016)));
        if (nextScale === previousScale) return;
        dialog._previewScale = nextScale;
        if (dialog._previewZoomFrame) return;
        dialog._previewZoomFrame = window.requestAnimationFrame(function () {
            dialog._previewZoomFrame = 0;
            if (dialog.open && dialog._previewFitSize) {
                applyDurableAttachmentPreviewScale(dialog, dialog._previewScale);
            }
        });
    }, { passive: false });
    dialog.addEventListener('close', function () {
        dialog._previewGeneration = (Number(dialog._previewGeneration) || 0) + 1;
        cancelDurableAttachmentPreviewFrames(dialog);
        dialog._previewFitSize = null;
        image.onload = null;
        image.style.visibility = 'hidden';
    });
    if (typeof window.ResizeObserver === 'function') {
        dialog._previewResizeObserver = new window.ResizeObserver(function () {
            if (dialog.open && dialog._previewFitSize) scheduleDurableAttachmentPreviewFit(dialog);
        });
        dialog._previewResizeObserver.observe(canvas);
    }
    document.body.appendChild(dialog);
    dialog._previewImage = image;
    dialog._previewStage = stage;
    dialog._previewCanvas = canvas;
    dialog._previewCaption = caption;
    durableAttachmentPreviewDialog = dialog;
    return dialog;
}

function measureDurableAttachmentPreviewFit(dialog) {
    var image = dialog && dialog._previewImage;
    var canvas = dialog && dialog._previewCanvas;
    if (!image || !canvas || !image.naturalWidth || !image.naturalHeight) return null;
    var availableWidth = canvas.clientWidth;
    var availableHeight = canvas.clientHeight;
    if (availableWidth <= 0 || availableHeight <= 0) return null;
    var fitScale = Math.min(1, availableWidth / image.naturalWidth, availableHeight / image.naturalHeight);
    return { width: image.naturalWidth * fitScale, height: image.naturalHeight * fitScale, viewportHeight: availableHeight };
}

function applyDurableAttachmentPreviewScale(dialog, scale) {
    var image = dialog && dialog._previewImage;
    if (!image || !dialog._previewFitSize) return;
    // Keep the fitted bitmap size stable; only the centered compositor transform changes while zooming.
    image.style.transform = 'translate3d(-50%, -50%, 0) scale(' + scale + ')';
}

function cancelDurableAttachmentPreviewFrames(dialog) {
    if (dialog._previewZoomFrame) window.cancelAnimationFrame(dialog._previewZoomFrame);
    if (dialog._previewFitFrame) window.cancelAnimationFrame(dialog._previewFitFrame);
    dialog._previewZoomFrame = 0;
    dialog._previewFitFrame = 0;
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
        dialog._previewImage.style.width = fitSize.width + 'px';
        dialog._previewImage.style.height = fitSize.height + 'px';
        applyDurableAttachmentPreviewScale(dialog, Number(dialog._previewScale) || 1);
        dialog._previewImage.style.visibility = '';
    });
}

function resetDurableAttachmentPreviewZoom(dialog) {
    var image = dialog && dialog._previewImage;
    if (!image) return;
    cancelDurableAttachmentPreviewFrames(dialog);
    var generation = (Number(dialog._previewGeneration) || 0) + 1;
    dialog._previewGeneration = generation;
    dialog._previewScale = 1;
    dialog._previewFitSize = null;
    image.style.visibility = 'hidden';
    var fitWhenReady = function () {
        if (dialog._previewGeneration === generation) scheduleDurableAttachmentPreviewFit(dialog);
    };
    if (typeof image.decode === 'function') {
        image.onload = null;
        image.decode().then(fitWhenReady, function () {
            if (dialog._previewGeneration !== generation) return;
            image.onload = fitWhenReady;
            if (image.complete && image.naturalWidth) fitWhenReady();
        });
    } else {
        image.onload = fitWhenReady;
        if (image.complete && image.naturalWidth) fitWhenReady();
    }
}

function openChatImagePreview(thumbnail) {
    if (!thumbnail) return;
    var dialog = ensureDurableAttachmentPreviewDialog();
    if (!dialog) return;
    var source = thumbnail.currentSrc || thumbnail.src;
    if (!source) return;
    if (dialog._previewImage.src !== source) dialog._previewImage.src = source;
    dialog._previewImage.alt = thumbnail.alt || '图片预览';
    dialog._previewCaption.textContent = thumbnail.alt || '图片预览';
    resetDurableAttachmentPreviewZoom(dialog);
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
    // The decode fallback can be ready synchronously, before showModal lays out the viewport.
    if (typeof dialog._previewImage.decode !== 'function' && dialog._previewImage.complete && dialog._previewImage.naturalWidth) {
        scheduleDurableAttachmentPreviewFit(dialog);
    }
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
            if (entry.url) previewImage.src = entry.url;
            return;
        }
        entry = { nodes: [previewImage], url: '', controller: typeof AbortController === 'function' ? new AbortController() : null };
        durableImagePreviews.set(ref.attachmentId, entry);
        if (!durableImageObserver) {
            durableImageObserver = new MutationObserver(sweepDurableImagePreviews);
            durableImageObserver.observe(document.body, { childList: true, subtree: true });
        }
        var options = { credentials: 'same-origin' };
        if (entry.controller) options.signal = entry.controller.signal;
        fetch('/api/attachments/' + encodeURIComponent(ref.attachmentId), options)
            .then(function (response) { if (!response.ok) throw new Error('Attachment unavailable'); return response.blob(); })
            .then(function (blob) {
                sweepDurableImagePreviews();
                if (durableImagePreviews.get(ref.attachmentId) !== entry) return;
                entry.url = URL.createObjectURL(blob);
                entry.nodes.forEach(function (node) { node.src = entry.url; });
            }).catch(function () {
                entry.nodes.forEach(function (node) {
                    node.alt = '图片暂不可用';
                    var card = node.closest('.msg-attachment-card, .feed-attachment-card');
                    if (card) card.classList.add('is-unavailable');
                });
                if (durableImagePreviews.get(ref.attachmentId) === entry) durableImagePreviews.delete(ref.attachmentId);
                sweepDurableImagePreviews();
            });
    });
}
