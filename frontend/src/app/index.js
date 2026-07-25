import { marked } from 'marked';
import i18nSource from './modules/i18n.js?raw';
import settingsSource from './modules/settings.js?raw';
import sharedStateAndDialogsSource from './modules/shared-state-and-dialogs.js?raw';
import agentTeamSource from './modules/agent-team.js?raw';
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
import sessionScrollHistorySource from './modules/session-scroll-history.js?raw';
import tocTodoSource from './modules/toc-todo.js?raw';
import messageRenderingSource from './modules/message-rendering.js?raw';
import subagentSource from './modules/subagent.js?raw';
import humanInteractionsSource from './modules/human-interactions.js?raw';
import eventDispatchSource from './modules/event-dispatch.js?raw';
import sessionManagementSource from './modules/session-management.js?raw';
import sseHandlingSource from './modules/sse-handling.js?raw';
import layoutPanelsSource from './modules/layout-panels.js?raw';

globalThis.marked = marked;

let mermaidImportPromise = null;
globalThis.loadMyAgentMermaid = function loadMyAgentMermaid() {
    if (globalThis.mermaid) return Promise.resolve(globalThis.mermaid);
    if (!mermaidImportPromise) {
        mermaidImportPromise = import('mermaid').then(function (module) {
            const api = module.default || module.mermaid || module;
            globalThis.mermaid = api;
            return api;
        });
    }
    return mermaidImportPromise;
};

const uiSources = [
    i18nSource,
    settingsSource,
    sharedStateAndDialogsSource,
    agentTeamSource,
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
    sessionScrollHistorySource,
    tocTodoSource,
    messageRenderingSource,
    subagentSource,
    humanInteractionsSource,
    eventDispatchSource,
    sessionManagementSource,
    sseHandlingSource,
    layoutPanelsSource,
];

Function('"use strict";\n' + uiSources.join('\n\n') + '\n//# sourceURL=myagent-ui.js')();

if (typeof initUiHoverTips === 'function') {
    initUiHoverTips(document);
}
