/**
 * Inline previews for PDF and office documents in the details column.
 *
 * The document page used to give every non-text file a "open with a system
 * app" card. PDF now renders through the browser's own viewer, and Word /
 * PowerPoint / Excel documents are parsed by the backend into escaped HTML
 * plus a small layout payload (`/api/workspace-doc-preview`). Embedded images
 * are fetched one package part at a time (`/api/workspace-doc-media`), so a
 * large deck never arrives as one huge JSON body.
 *
 * Everything here is presentation only: the backend owns parsing, limits and
 * path checks. The renderers keep the column's existing page chrome (name,
 * reveal, refresh, open-in-system) and add their own navigation.
 */

/** Suffixes rendered by the browser's PDF viewer. */
const DOCK_PREVIEW_PDF_SUFFIXES = ['pdf'];

/** Suffixes parsed by the backend office previewer. */
const DOCK_PREVIEW_OFFICE_SUFFIXES = ['docx', 'pptx', 'xlsx', 'xlsm', 'csv', 'tsv'];

/** Note codes from the backend, mapped to their user-facing labels. */
const DOCK_PREVIEW_NOTE_LABELS = {
    'document-truncated': 'documentTruncated',
    'slides-truncated': 'slidesTruncated',
    'rows-truncated': 'rowsTruncated',
    'columns-truncated': 'columnsTruncated',
    'sheets-truncated': 'sheetsTruncated',
    'media-skipped': 'mediaSkipped',
};

/** Which inline preview a path uses: `pdf`, `docx`, `pptx`, `xlsx` or ''. */
function dockRightPreviewKind(path) {
    const suffix = dockRightSuffix(path);
    if (DOCK_PREVIEW_PDF_SUFFIXES.indexOf(suffix) >= 0) return 'pdf';
    if (DOCK_PREVIEW_OFFICE_SUFFIXES.indexOf(suffix) >= 0) {
        if (suffix === 'xlsm') return 'xlsx';
        if (suffix === 'tsv') return 'csv';
        return suffix;
    }
    return '';
}

/** Whether a workspace path opens inline instead of in a system app. */
function dockRightCanPreviewPath(path) {
    return !!dockRightPreviewKind(path);
}

/** Build a URL for one embedded package part. */
function dockRightDocMediaUrl(state, part) {
    return workspaceApiUrl('/api/workspace-doc-media', { rel: state.rel, part: String(part) }, state.context);
}

/** Point every `data-doc-part` image at the media endpoint. */
function dockRightHydrateParts(root, state) {
    const images = root.querySelectorAll('img[data-doc-part]');
    for (let i = 0; i < images.length; i += 1) {
        const image = images[i];
        const part = image.getAttribute('data-doc-part');
        if (!part) continue;
        image.addEventListener('error', () => image.classList.add('is-broken'), { once: true });
        image.src = dockRightDocMediaUrl(state, part);
    }
}

/** Footer with simplification/truncation notes. */
function dockRightPreviewFooter(payload, approximate) {
    const codes = Array.isArray(payload && payload.notes) ? payload.notes : [];
    const labels = [];
    for (let i = 0; i < codes.length; i += 1) {
        const key = DOCK_PREVIEW_NOTE_LABELS[codes[i]];
        if (key && labels.indexOf(key) < 0) labels.push(key);
    }
    if (!labels.length && !approximate) return null;
    const foot = document.createElement('div');
    foot.className = 'dock-preview-foot';
    foot.setAttribute('data-dock-preview-foot', '1');
    if (approximate) foot.appendChild(dockRightPreviewNote(dockRightText('previewApprox')));
    for (let i = 0; i < labels.length; i += 1) {
        foot.appendChild(dockRightPreviewNote(dockRightText(labels[i])));
    }
    return foot;
}

function dockRightPreviewNote(text) {
    const note = document.createElement('div');
    note.className = 'dock-preview-note';
    note.textContent = text;
    return note;
}

/** Error state: the reason plus the usual system-open card. */
function dockRightPreviewFailure(content, state, message) {
    const wrap = document.createElement('div');
    wrap.className = 'dock-preview-error';
    wrap.appendChild(dockRightNote(message));
    wrap.appendChild(dockRightSystemCard(state.rel, state.context));
    content.replaceChildren(wrap);
}

// ── PDF ─────────────────────────────────────────────────────────────────────

/**
 * PDF goes to the browser's built-in viewer inside the column. The asset route
 * serves it inline with the right media type; a browser without a PDF viewer
 * falls back to the system-open card.
 */
function dockRightRenderPdfPreview(content, state, refresh) {
    content.style.padding = '0';
    const frame = document.createElement('iframe');
    frame.className = 'dock-doc-frame dock-doc-pdf';
    frame.setAttribute('data-dock-doc-pdf', '1');
    frame.setAttribute('title', dockRightText('pdfPreview'));
    const base = workspaceAssetUrl(state.rel, state.context);
    const load = () => {
        try { frame.src = base + '?_=' + String(Date.now()); } catch (error) { /* ignore */ }
    };
    content.replaceChildren(frame);
    load();
    refresh.addEventListener('click', load);
}

// ── office documents ────────────────────────────────────────────────────────

/** Fetch and render one Word / PowerPoint / Excel document. */
function dockRightRenderOfficePreview(content, state, refresh) {
    content.style.padding = '0';
    const load = () => {
        if (state.abort) {
            try { state.abort.abort(); } catch (error) { /* ignore */ }
        }
        content.replaceChildren(dockRightNote(dockRightText('loading')));
        const controller = typeof AbortController === 'function' ? new AbortController() : null;
        state.abort = controller;
        fetch(workspaceApiUrl('/api/workspace-doc-preview', {
            rel: state.rel,
            _: String(Date.now()),
        }, state.context), controller ? { signal: controller.signal } : undefined)
            .then((response) => response.json().catch(() => null).then((data) => {
                if (state.released) return;
                if (!response.ok || !data || data.ok !== true) {
                    if (response.status === 404 || response.status === 405 || response.status === 501) {
                        throw new Error(dockRightText('previewUnavailable'));
                    }
                    throw new Error((data && data.error) || ('HTTP ' + response.status));
                }
                dockRightRenderPreviewPayload(content, data, state);
            }))
            .catch((error) => {
                if (state.released || (error && error.name === 'AbortError')) return;
                dockRightPreviewFailure(content, state,
                    dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error));
            });
    };
    refresh.addEventListener('click', load);
    load();
}

/** Dispatch a preview payload to its renderer. */
function dockRightRenderPreviewPayload(content, payload, state) {
    content.replaceChildren();
    if (payload.kind === 'docx') {
        dockRightRenderRichText(content, payload, state);
    } else if (payload.kind === 'pptx') {
        dockRightRenderDeck(content, payload, state);
    } else if (payload.kind === 'xlsx') {
        dockRightRenderWorkbook(content, payload, state);
    } else if (payload.kind === 'csv') {
        dockRightRenderCsv(content, payload, state);
    } else {
        dockRightPreviewFailure(content, state, dockRightText('previewUnavailable'));
    }
}

/** Word: a reflowed document body with inline images. */
function dockRightRenderRichText(content, payload, state) {
    const document_ = payload.document || {};
    if (!String(document_.html || '').trim()) {
        content.replaceChildren(dockRightNote(dockRightText('emptyDocument')));
        return;
    }
    const body = document.createElement('div');
    body.className = 'dock-doc-richtext';
    body.setAttribute('data-dock-doc-richtext', '1');
    body.innerHTML = String(document_.html || '');
    // Tables scroll horizontally inside the column instead of widening it.
    const tables = body.querySelectorAll('table');
    for (let i = 0; i < tables.length; i += 1) {
        const table = tables[i];
        if (table.parentElement && table.parentElement.classList.contains('dp-table-wrap')) continue;
        const wrap = document.createElement('div');
        wrap.className = 'dp-table-wrap';
        if (table.parentNode) table.parentNode.insertBefore(wrap, table);
        wrap.appendChild(table);
    }
    dockRightHydrateParts(body, state);
    content.appendChild(body);
    const foot = dockRightPreviewFooter(payload, true);
    if (foot) content.appendChild(foot);
}

/** PowerPoint: a fit-to-width slide canvas with a page strip. */
function dockRightRenderDeck(content, payload, state) {
    const deck = payload.deck || {};
    const slides = Array.isArray(deck.slides) ? deck.slides : [];
    if (!slides.length) {
        content.replaceChildren(dockRightNote(dockRightText('emptyDocument')));
        return;
    }
    const width = Number(deck.width) || 960;
    const height = Number(deck.height) || 540;
    const root = document.createElement('div');
    root.className = 'dock-deck';
    root.setAttribute('data-dock-deck', '1');

    const bar = document.createElement('div');
    bar.className = 'dock-deck-bar';
    const prev = document.createElement('button');
    prev.type = 'button';
    prev.className = 'dock-link-button dock-deck-step';
    prev.textContent = '‹';
    prev.setAttribute('aria-label', dockRightText('previousSlide'));
    prev.title = dockRightText('previousSlide');
    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'dock-link-button dock-deck-step';
    next.textContent = '›';
    next.setAttribute('aria-label', dockRightText('nextSlide'));
    next.title = dockRightText('nextSlide');
    const select = document.createElement('select');
    select.className = 'dock-deck-select';
    select.setAttribute('aria-label', dockRightText('jumpSlide'));
    for (let i = 0; i < slides.length; i += 1) {
        const option = document.createElement('option');
        option.value = String(i);
        option.textContent = String(i + 1);
        select.appendChild(option);
    }
    const counter = document.createElement('span');
    counter.className = 'dock-deck-counter';
    counter.textContent = '1 / ' + slides.length;
    bar.appendChild(prev);
    bar.appendChild(select);
    bar.appendChild(counter);
    bar.appendChild(next);

    const stageWrap = document.createElement('div');
    stageWrap.className = 'dock-deck-stagewrap';
    stageWrap.tabIndex = 0;
    stageWrap.setAttribute('role', 'group');
    stageWrap.setAttribute('aria-label', dockRightText('slidePreview'));
    const scaler = document.createElement('div');
    scaler.className = 'dock-deck-scaler';
    const stage = document.createElement('div');
    stage.className = 'dock-deck-stage';
    stage.style.width = width + 'px';
    stage.style.height = height + 'px';
    const canvas = document.createElement('div');
    canvas.className = 'dock-deck-slide';
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    stage.appendChild(canvas);
    scaler.appendChild(stage);
    stageWrap.appendChild(scaler);

    let current = 0;
    let observer = null;
    const fit = () => {
        if (!content.isConnected) {
            if (observer) { observer.disconnect(); observer = null; }
            window.removeEventListener('resize', fit);
            return;
        }
        const available = stageWrap.clientWidth - 20;
        if (!available || available < 80) return;
        const scale = Math.max(0.2, Math.min(1, available / width));
        stage.style.transform = 'scale(' + scale.toFixed(4) + ')';
        scaler.style.width = Math.round(width * scale) + 'px';
        scaler.style.height = Math.round(height * scale) + 'px';
    };
    const show = (index) => {
        current = Math.max(0, Math.min(slides.length - 1, index));
        const slide = slides[current] || {};
        canvas.style.background = slide.background || '#ffffff';
        canvas.innerHTML = String(slide.html || '');
        dockRightHydrateParts(canvas, state);
        select.value = String(current);
        counter.textContent = (current + 1) + ' / ' + slides.length;
        prev.disabled = current === 0;
        next.disabled = current === slides.length - 1;
        if (stageWrap.scrollTop) stageWrap.scrollTop = 0;
    };
    prev.addEventListener('click', () => show(current - 1));
    next.addEventListener('click', () => show(current + 1));
    select.addEventListener('change', () => show(Number(select.value) || 0));
    stageWrap.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
            event.preventDefault(); show(current - 1);
        } else if (event.key === 'ArrowRight' || event.key === 'PageDown') {
            event.preventDefault(); show(current + 1);
        } else if (event.key === 'Home') {
            event.preventDefault(); show(0);
        } else if (event.key === 'End') {
            event.preventDefault(); show(slides.length - 1);
        }
    });
    root.appendChild(bar);
    root.appendChild(stageWrap);
    const foot = dockRightPreviewFooter(payload, true);
    if (foot) root.appendChild(foot);
    content.appendChild(root);
    show(0);
    fit();
    if (typeof ResizeObserver === 'function') {
        observer = new ResizeObserver(fit);
        observer.observe(stageWrap);
    }
    window.addEventListener('resize', fit);
}

/** Excel: one table per sheet with a tab strip. */
function dockRightRenderWorkbook(content, payload, state) {
    const workbook = payload.workbook || {};
    const sheets = Array.isArray(workbook.sheets) ? workbook.sheets : [];
    if (!sheets.length) {
        content.replaceChildren(dockRightNote(dockRightText('emptyDocument')));
        return;
    }
    const root = document.createElement('div');
    root.className = 'dock-workbook';
    root.setAttribute('data-dock-workbook', '1');
    const tabs = document.createElement('div');
    tabs.className = 'dock-sheet-tabs';
    tabs.setAttribute('role', 'tablist');
    const body = document.createElement('div');
    body.className = 'dock-sheet-body';
    let active = sheets.findIndex((sheet) => sheet && sheet.name === workbook.active);
    if (active < 0) active = 0;
    const buttons = [];
    const show = (index) => {
        active = Math.max(0, Math.min(sheets.length - 1, index));
        for (let i = 0; i < buttons.length; i += 1) {
            const on = i === active;
            buttons[i].classList.toggle('is-active', on);
            buttons[i].setAttribute('aria-selected', on ? 'true' : 'false');
            buttons[i].tabIndex = on ? 0 : -1;
        }
        body.innerHTML = String((sheets[active] && sheets[active].html) || '');
        body.scrollTop = 0;
        body.scrollLeft = 0;
    };
    for (let i = 0; i < sheets.length; i += 1) {
        const sheet = sheets[i] || {};
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'dock-sheet-tab';
        button.setAttribute('role', 'tab');
        if (sheet.hidden) {
            button.classList.add('is-hidden');
            button.title = dockRightText('hiddenSheet');
        }
        button.textContent = String(sheet.name || ('Sheet ' + (i + 1)));
        button.addEventListener('click', () => show(i));
        button.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowLeft') { event.preventDefault(); show(i - 1); buttons[Math.max(0, i - 1)].focus(); }
            else if (event.key === 'ArrowRight') { event.preventDefault(); show(i + 1); buttons[Math.min(sheets.length - 1, i + 1)].focus(); }
        });
        buttons.push(button);
        tabs.appendChild(button);
    }
    root.appendChild(tabs);
    root.appendChild(body);
    const foot = dockRightPreviewFooter(payload, true);
    if (foot) root.appendChild(foot);
    content.appendChild(root);
    show(active);
}

/** CSV / TSV: one table, with a one-click switch to the raw text. */
function dockRightRenderCsv(content, payload, state) {
    const table = payload.table || {};
    const root = document.createElement('div');
    root.className = 'dock-workbook dock-csv';
    root.setAttribute('data-dock-csv', '1');
    const bar = document.createElement('div');
    bar.className = 'dock-csv-bar';
    const meta = document.createElement('span');
    meta.className = 'dock-csv-meta';
    const suffix = String(payload.name || '').split('.').pop().toUpperCase();
    meta.textContent = [suffix, (Number(table.rows) || 0) + ' × ' + (Number(table.cols) || 0),
        String(table.encoding || '')].filter(Boolean).join(' · ');
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'dock-link-button dock-csv-toggle';
    toggle.setAttribute('data-dock-csv-toggle', '1');
    const body = document.createElement('div');
    body.className = 'dock-sheet-body dock-csv-body';
    let mode = 'table';
    const showTable = () => {
        mode = 'table';
        body.classList.remove('is-source');
        toggle.textContent = dockRightText('viewSource');
        if (String(table.html || '').trim()) body.innerHTML = String(table.html || '');
        else body.replaceChildren(dockRightNote(dockRightText('emptyDocument')));
    };
    const showSource = () => {
        mode = 'source';
        body.classList.add('is-source');
        toggle.textContent = dockRightText('previewTable');
        void dockRightLoadCsvSource(body, state);
    };
    toggle.addEventListener('click', () => (mode === 'table' ? showSource() : showTable()));
    bar.appendChild(meta);
    bar.appendChild(toggle);
    root.appendChild(bar);
    root.appendChild(body);
    const foot = dockRightPreviewFooter(payload, true);
    if (foot) root.appendChild(foot);
    content.appendChild(root);
    showTable();
}

/** The raw text behind a CSV preview, kept inside the same toolbar shell. */
function dockRightLoadCsvSource(body, state) {
    body.replaceChildren(dockRightNote(dockRightText('loading')));
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    fetch(workspaceApiUrl('/api/workspace-file-text', {
        rel: state.rel,
        max_bytes: String(DOCK_RIGHT_TEXT_MAX_BYTES),
    }, state.context), controller ? { signal: controller.signal } : undefined)
        .then((response) => response.json().catch(() => null).then((data) => {
            if (!response.ok || !data || data.ok !== true) {
                throw new Error((data && data.error) || ('HTTP ' + response.status));
            }
            const pre = document.createElement('pre');
            pre.className = 'dock-doc-text dock-csv-source';
            pre.textContent = String(data.text || '');
            const nodes = [pre];
            if (data.truncated) nodes.push(dockRightNote(dockRightText('truncated')));
            body.replaceChildren.apply(body, nodes);
        }))
        .catch((error) => {
            if (error && error.name === 'AbortError') return;
            body.replaceChildren(dockRightNote(
                dockRightText('loadFailed') + ': ' + (error && error.message ? error.message : error)));
        });
}
