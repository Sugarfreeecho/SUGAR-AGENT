/** Stable seats for asynchronously rendered conversation activity triggers. */
var titlebarActivity = (function () {
    function mount(trigger) {
        var row = document.querySelector('.breadcrumb-title-row');
        if (!row || !trigger) return null;
        var host = row.querySelector('.breadcrumb-activities');
        if (!host) {
            host = document.createElement('div');
            host.className = 'breadcrumb-activities';
            row.insertBefore(host, row.querySelector('.breadcrumb-session-actions'));
        }
        if (trigger.id === 'subagent-catalog-trigger') {
            if (host.firstChild !== trigger) host.insertBefore(trigger, host.firstChild);
        } else if (trigger.parentNode !== host) host.appendChild(trigger);
        return host;
    }
    return { mount: mount };
})();
