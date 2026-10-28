/* The console owns its document, including the terminal's context menu. */
let active = null;
function close() {
    if (!active) return;
    active.menu.remove();
    active = null;
}
globalThis.MyAgentContextMenu = {
    copy: text => navigator.clipboard.writeText(String(text || '')),
    isOpenFor: root => Boolean(active && (root === active.root || root.contains(active.root))),
    bind(root, provider) {
        function show(event) {
            event.preventDefault(); close();
            const menu = document.createElement('div');
            menu.className = 'execution-context-menu'; menu.setAttribute('role', 'menu');
            active = { root, menu };
            provider().forEach(item => {
                if (!item) { menu.append(document.createElement('hr')); return; }
                const button = document.createElement('button');
                button.type = 'button'; button.textContent = item.label;
                button.disabled = item.disabled === true; button.setAttribute('role', 'menuitem');
                button.onclick = async () => { close(); try { await item.action(); } catch (error) { alert(error.message); } };
                menu.append(button);
            });
            document.body.append(menu);
            menu.style.left = Math.max(4, Math.min(event.clientX, innerWidth - menu.offsetWidth - 4)) + 'px';
            menu.style.top = Math.max(4, Math.min(event.clientY, innerHeight - menu.offsetHeight - 4)) + 'px';
            menu.querySelector('button:not(:disabled)')?.focus();
        }
        root.addEventListener('contextmenu', show);
        return () => { root.removeEventListener('contextmenu', show); if (active?.root === root) close(); };
    },
};
document.addEventListener('pointerdown', event => { if (active && !active.menu.contains(event.target)) close(); }, true);
document.addEventListener('keydown', event => {
    if (!active) return;
    if (event.key === 'Escape') { event.preventDefault(); close(); return; }
    const buttons = [...active.menu.querySelectorAll('button:not(:disabled)')];
    const index = buttons.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault(); buttons[(index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length]?.focus();
    }
});
document.addEventListener('myagent:plugin-page-visibility', event => { if (!event.detail?.visible) close(); });
document.addEventListener('myagent:plugin-page-dispose', close, { once: true });
