import { marked } from 'marked';
import { initPluginUiSlots } from './plugin-ui-slots.js';
import i18nSource from './modules/i18n.js?raw';
import settingsSource from './modules/settings.js?raw';
import inputActionsSource from './modules/input-actions.js?raw';
import sharedStateAndDialogsSource from './modules/shared-state-and-dialogs.js?raw';
import uiPerformanceSource from './modules/ui-performance.js?raw';
import uiSlotRegistrySource from './modules/ui-slot-registry.js?raw';
import sessionStoreSource from './state/session-store.js?raw';
import sessionSelectorsSource from './state/session-selectors.js?raw';
import sessionActionsSource from './state/session-actions.js?raw';
import sessionRenderersSource from './state/session-renderers.js?raw';
import messageStoreSource from './state/message-store.js?raw';
import messageRenderersSource from './state/message-renderers.js?raw';
import contextStoreSource from './state/context-store.js?raw';
import subagentCatalogStoreSource from './state/subagent-catalog-store.js?raw';
import subagentAddressingSource from './state/subagent-addressing.js?raw';
import subagentFramesSource from './modules/subagent-frames.js?raw';
import subagentCatalogUiSource from './modules/subagent-catalog-ui.js?raw';
import subagentUiDecisionsSource from './state/subagent-ui-decisions.js?raw';
import subagentComposerUiSource from './modules/subagent-composer-ui.js?raw';
import sessionEventReducerSource from './state/session-event-reducer.js?raw';
import modelProfilesSource from './modules/model-profiles.js?raw';
import skillPickerSource from './modules/skill-picker.js?raw';
import smoothStreamSource from './modules/smooth-stream.js?raw';
import sessionScrollHistorySource from './modules/session-scroll-history.js?raw';
import tocTodoSource from './modules/toc-todo.js?raw';
import workspaceMediaSource from './modules/workspace-media.js?raw';
import messageRenderingSource from './modules/message-rendering.js?raw';
import humanInteractionsSource from './modules/human-interactions.js?raw';
import permissionsSource from './modules/permissions.js?raw';
import eventDispatchSource from './modules/event-dispatch.js?raw';
import sessionManagementSource from './modules/session-management.js?raw';
import sseHandlingSource from './modules/sse-handling.js?raw';
import layoutPanelsSource from './modules/layout-panels.js?raw';
import dockTypesSource from './modules/dock/engine/types.js?raw';
import dockTreeSource from './modules/dock/engine/tree.js?raw';
import dockConstraintsSource from './modules/dock/engine/constraints.js?raw';
import dockGeometrySource from './modules/dock/engine/geometry.js?raw';
import dockOperationsSource from './modules/dock/engine/operations.js?raw';
import dockPlannerSource from './modules/dock/engine/planner.js?raw';
import dockSequenceSource from './modules/dock/engine/sequence.js?raw';
import dockControllerSource from './modules/dock/engine/controller.js?raw';
import dockIconsSource from './modules/dock/renderer/icons.js?raw';
import dockGestureSource from './modules/dock/renderer/gesture.js?raw';
import dockMeasureSource from './modules/dock/renderer/measure.js?raw';
import dockSurfaceSource from './modules/dock/renderer/dock-surface.js?raw';
import dockFloatLayerSource from './modules/dock/renderer/float-layer.js?raw';
import dockSurfaceStoreSource from './modules/dock/embedder/surface-store.js?raw';
import dockTabRegistrySource from './modules/dock/embedder/tab-registry.js?raw';
import dockRightColumnSource from './modules/dock/embedder/right-column.js?raw';

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

// 闭包内的接线代码：必须与模块同一作用域（Function() 体内的 var 是局部绑定，
// 模块外部看不到），否则 bindStore / subscribe / 探针都会静默失效。
const uiWiring = `
// 子代理目录对象层 ↔ 表现层接线
if (typeof subagentCatalogUi !== 'undefined' && subagentCatalogUi) {
    subagentCatalogUi.bindStore();
}
if (typeof subagentAddressing !== 'undefined' && subagentAddressing) {
    subagentAddressing.subscribe(function () {
        if (typeof subagentComposerUi !== 'undefined' && subagentComposerUi) {
            subagentComposerUi.syncComposer();
        }
    });
}
// 编辑器接管座位：登记进 slot 注册表（chain 选举）
if (typeof subagentComposerUi !== 'undefined' && subagentComposerUi) {
    subagentComposerUi.registerComposerSeat();
}
// 子代理 UI 运行时探针：供自动化冒烟/排障读取寻址与目录状态（只读）。
globalThis.__myagentSubagentProbe = {
    addressing: function () {
        return (typeof subagentAddressing !== 'undefined' && subagentAddressing)
            ? subagentAddressing.snapshot()
            : null;
    },
    catalog: function (parentId) {
        if (typeof subagentCatalogStore === 'undefined' || !subagentCatalogStore) return null;
        var catalog = subagentCatalogStore.getCatalog(parentId);
        return catalog ? {
            state: catalog.state,
            entries: (catalog.entries || []).map(function (entry) {
                return {
                    childId: entry.childId, label: entry.label, activity: entry.activity,
                    mode: entry.mode, diagnostic: !!entry.diagnostic,
                };
            }),
        } : null;
    },
    ui: function () {
        return (typeof subagentCatalogUi !== 'undefined' && subagentCatalogUi)
            ? { menuOpen: subagentCatalogUi.isMenuOpen() }
            : null;
    },
};
`;

const uiSources = [
    i18nSource,
    settingsSource,
    inputActionsSource,
    sharedStateAndDialogsSource,
    uiPerformanceSource,
    uiSlotRegistrySource,
    sessionStoreSource,
    sessionSelectorsSource,
    sessionActionsSource,
    sessionRenderersSource,
    messageStoreSource,
    messageRenderersSource,
    contextStoreSource,
    subagentCatalogStoreSource,
    subagentAddressingSource,
    subagentFramesSource,
    subagentCatalogUiSource,
    subagentUiDecisionsSource,
    subagentComposerUiSource,
    sessionEventReducerSource,
    modelProfilesSource,
    skillPickerSource,
    smoothStreamSource,
    sessionScrollHistorySource,
    tocTodoSource,
    workspaceMediaSource,
    messageRenderingSource,
    humanInteractionsSource,
    permissionsSource,
    eventDispatchSource,
    sessionManagementSource,
    sseHandlingSource,
    layoutPanelsSource,
    dockTypesSource,
    dockTreeSource,
    dockConstraintsSource,
    dockGeometrySource,
    dockOperationsSource,
    dockPlannerSource,
    dockSequenceSource,
    dockControllerSource,
    dockIconsSource,
    dockGestureSource,
    dockMeasureSource,
    dockSurfaceSource,
    dockFloatLayerSource,
    dockSurfaceStoreSource,
    dockTabRegistrySource,
    dockRightColumnSource,
];

Function('"use strict";\n' + uiSources.join('\n\n') + '\n\n' + uiWiring + '\n//# sourceURL=myagent-ui.js')();

void initPluginUiSlots();

if (typeof initUiHoverTips === 'function') {
    initUiHoverTips(document);
}
