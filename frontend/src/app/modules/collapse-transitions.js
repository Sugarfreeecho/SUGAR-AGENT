const COLLAPSIBLE_PANELS = [
    '.session-section-body',
    '.session-group-body',
    '.skill-picker-group-items',
    '.dock-files-children',
    '.human-terminal-summary',
    '.human-terminal-detail',
    '.process-aggregate-body',
].join(',');

function isPanelCollapsed(panel) {
    const owner = panel.parentElement;
    return panel.classList.contains('is-collapsed') || !!(owner && owner.classList.contains('is-collapsed'));
}

document.addEventListener('transitionrun', function (event) {
    if (event.propertyName !== 'opacity') return;
    const panel = event.target;
    if (panel && panel.matches && panel.matches(COLLAPSIBLE_PANELS)) {
        panel.style.overflow = 'hidden';
    }
});

document.addEventListener('transitionend', function (event) {
    if (event.propertyName !== 'opacity') return;
    const panel = event.target;
    if (!panel || !panel.matches || !panel.matches(COLLAPSIBLE_PANELS)) return;

    if (panel.classList.contains('process-aggregate-body')) {
        panel.style.overflow = '';
        return;
    }

    panel.style.overflow = isPanelCollapsed(panel) ? '' : 'visible';
});
