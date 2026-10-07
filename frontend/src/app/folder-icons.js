/**
 * Shared directory and file-action icons used by the chat UI and path picker.
 * Keep these semantic variants in one place so identical actions look alike.
 */
const ICONS = Object.freeze({
    folder: {
        viewBox: '0 0 24 24',
        body: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path>',
    },
    'folder-open': {
        viewBox: '0 0 24 24',
        body: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v1"></path><path d="M3 9h18l-1.7 9.2a2 2 0 0 1-2 1.6H6.7a2 2 0 0 1-2-1.6L3 9z"></path>',
    },
    'folder-plus': {
        viewBox: '0 0 24 24',
        body: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path><path d="M12 11v6M9 14h6"></path>',
    },
    file: {
        viewBox: '0 0 24 24',
        body: '<path d="M13 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V10z"></path><path d="M13 3v7h7"></path>',
    },
    paperclip: {
        viewBox: '0 0 24 24',
        body: '<path d="m21.4 11.1-8.9 8.9a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5"></path>',
    },
});

function svg(name, className) {
    const icon = ICONS[name] || ICONS.folder;
    const classAttr = className ? ' class="' + String(className).replace(/[^a-zA-Z0-9 _-]/g, '') + '"' : '';
    return '<svg' + classAttr + ' width="18" height="18" viewBox="' + icon.viewBox + '" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + icon.body + '</svg>';
}

function mount(root) {
    const scope = root || document;
    if (!scope || !scope.querySelectorAll) return;
    const nodes = [];
    if (scope.matches && scope.matches('[data-app-icon]')) nodes.push(scope);
    scope.querySelectorAll('[data-app-icon]').forEach((node) => nodes.push(node));
    nodes.forEach((node) => {
        node.innerHTML = svg(node.getAttribute('data-app-icon'));
        node.removeAttribute('data-app-icon');
    });
}

if (typeof window !== 'undefined') {
    window.MyAgentIcons = Object.freeze({ svg, mount });
}

