import { marked } from 'marked';
import { initPluginUiSlots } from './plugin-ui-slots.js';
import i18nSource from './modules/i18n.js?raw';
import settingsSource from './modules/settings.js?raw';
import inputActionsSource from './modules/input-actions.js?raw';
import sharedStateAndDialogsSource from './modules/shared-state-and-dialogs.js?raw';
import sessionStoreSource from './state/session-store.js?raw';
import sessionSelectorsSource from './state/session-selectors.js?raw';
import sessionActionsSource from './state/session-actions.js?raw';
import sessionRenderersSource from './state/session-renderers.js?raw';
import messageStoreSource from './state/message-store.js?raw';
import messageRenderersSource from './state/message-renderers.js?raw';
import subagentStoreSource from './state/subagent-store.js?raw';
import subagentContinueSource from './state/subagent-continue.js?raw';
import subagentEventStateSource from './state/subagent-event-state.js?raw';
import subagentRenderersSource from './state/subagent-renderers.js?raw';
import subagentCacheSource from './state/subagent-cache.js?raw';
import subagentLoaderSource from './state/subagent-loader.js?raw';
import subagentSyncSource from './state/subagent-sync.js?raw';
import subagentActionsSource from './state/subagent-actions.js?raw';
import subagentDockSource from './state/subagent-dock.js?raw';
import contextStoreSource from './state/context-store.js?raw';
import sessionEventReducerSource from './state/session-event-reducer.js?raw';
import modelProfilesSource from './modules/model-profiles.js?raw';
import skillPickerSource from './modules/skill-picker.js?raw';
import smoothStreamSource from './modules/smooth-stream.js?raw';
import sessionScrollHistorySource from './modules/session-scroll-history.js?raw';
import tocTodoSource from './modules/toc-todo.js?raw';
import workspaceMediaSource from './modules/workspace-media.js?raw';
import messageRenderingSource from './modules/message-rendering.js?raw';
import subagentSource from './modules/subagent.js?raw';
import humanInteractionsSource from './modules/human-interactions.js?raw';
import permissionsSource from './modules/permissions.js?raw';
import eventDispatchSource from './modules/event-dispatch.js?raw';
import sessionManagementSource from './modules/session-management.js?raw';
import sseHandlingSource from './modules/sse-handling.js?raw';
import layoutPanelsSource from './modules/layout-panels.js?raw';

globalThis.marked = marked;

const mermaidVendorUrl = '/assets/vendor/mermaid.min.js';
let mermaidImportPromise = null;
globalThis.loadMyAgentMermaid = function loadMyAgentMermaid() {
    if (globalThis.mermaid) return Promise.resolve(globalThis.mermaid);
    if (!mermaidImportPromise) {
        mermaidImportPromise = new Promise(function (resolve, reject) {
            const script = document.createElement('script');
            script.src = mermaidVendorUrl;
            script.async = true;
            script.dataset.myagentMermaidVendor = 'true';
            script.onload = function () {
                if (!globalThis.mermaid) {
                    script.remove();
                    reject(new Error('Mermaid vendor loaded without exposing its API'));
                    return;
                }
                resolve(globalThis.mermaid);
            };
            script.onerror = function () {
                script.remove();
                reject(new Error('Failed to load Mermaid vendor asset'));
            };
            document.head.appendChild(script);
        }).catch(function (error) {
            mermaidImportPromise = null;
            throw error;
        });
    }
    return mermaidImportPromise;
};

let html2canvasImportPromise = null;
globalThis.loadMyAgentHtml2Canvas = function loadMyAgentHtml2Canvas() {
    if (!html2canvasImportPromise) {
        html2canvasImportPromise = import('html2canvas').then(function (module) {
            return module.default || module;
        });
    }
    return html2canvasImportPromise;
};

const uiSources = [
    i18nSource,
    settingsSource,
    inputActionsSource,
    sharedStateAndDialogsSource,
    sessionStoreSource,
    sessionSelectorsSource,
    sessionActionsSource,
    sessionRenderersSource,
    messageStoreSource,
    messageRenderersSource,
    subagentStoreSource,
    subagentContinueSource,
    subagentEventStateSource,
    subagentRenderersSource,
    subagentCacheSource,
    subagentLoaderSource,
    subagentSyncSource,
    subagentActionsSource,
    subagentDockSource,
    contextStoreSource,
    sessionEventReducerSource,
    modelProfilesSource,
    skillPickerSource,
    smoothStreamSource,
    sessionScrollHistorySource,
    tocTodoSource,
    workspaceMediaSource,
    messageRenderingSource,
    subagentSource,
    humanInteractionsSource,
    permissionsSource,
    eventDispatchSource,
    sessionManagementSource,
    sseHandlingSource,
    layoutPanelsSource,
];

Function('"use strict";\n' + uiSources.join('\n\n') + '\n//# sourceURL=myagent-ui.js')();

void initPluginUiSlots();

if (typeof initUiHoverTips === 'function') {
    initUiHoverTips(document);
}
