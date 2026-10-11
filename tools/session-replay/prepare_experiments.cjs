/* Build-time only. Portable users need neither Git nor Node.js. */
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const {parseAst} = require(path.join(root, 'frontend/node_modules/rollup/dist/parseAst.js'));
const refs = {old: 'de2d6d6', current: 'cf8024b'};
const files = Object.fromEntries(Object.values(refs).map(ref=>[ref,cp.execFileSync('git', ['ls-tree', '-r', '--name-only', ref, 'frontend/src/app'], {cwd:root, encoding:'utf8'}).trim().split('\n').filter(p=>p.endsWith('.js'))]));
const cache = new Map();
function source(ref, file) {
    const key = ref + ':' + file;
    if (!cache.has(key)) cache.set(key, cp.execFileSync('git', ['show', key], {cwd:root, encoding:'utf8', maxBuffer:8e6}).replace(/\r\n/g,'\n'));
    return cache.get(key);
}
function declaration(ref, name) {
    for (const file of files[ref]) {
        const text = source(ref,file);
        if (!text.includes('function ' + name + '(')) continue;
        const node = parseAst(text).body.find(n=>n.type==='FunctionDeclaration' && n.id.name===name);
        if (node) return {text:text.slice(node.start,node.end),file};
    }
    throw new Error('Missing declaration: ' + ref + ' ' + name);
}
const definitions = [
    ['auto_follow','自动跟随最新文字','shared','source','两版共有路径。关闭流式生成时聊天区和执行框的自动跟随、终态贴底及长文本折叠位置补偿；仍逐步写入文字，保留初始历史定位和手动滚动。'],
    ['smooth_follow','平滑跟随动画','shared','source','两版共有路径。关闭弹簧缓动与持续跟随 RAF，只在内容更新请求时直接贴底。自动跟随关闭时，此项不生效；不改变逐字输出和行高动画。'],
    ['collapsed_layout','折叠执行框保留在布局','cf741f2','css','关闭后，折叠的执行过程正文恢复 display:none，避免其长文本继续参与布局。'],
    ['size_motion','高度与尺寸动画','cf741f2','css','关闭全局 interpolate-size 和面板 height / min-height / max-height / padding / width 过渡；保留透明度动画。'],
    ['overflow_switch','动画期间切换 overflow','cf741f2','module','关闭 transitionrun / transitionend 中对 overflow 的写入，测试滚动条切换和换行重算。'],
    ['process_reuse','执行过程分组复用','cf741f2','source','分组选择、创建、结束和连接时定位恢复 1004 实现；可能改变执行条目的分组位置。'],
    ['history_anchor','历史补页锚点补偿','cf741f2','uncovered','代码恢复 1004 单次高度补偿。当前工具直接载入历史，不触发补页，不能靠此重放验证这条路径。'],
    ['review_updates','改动审阅实时更新','a2889c2','conditional','执行记录的新增审阅元数据与 change-review 插件恢复 1004；只有工具改动审阅事件才涉及这条路径。'],
    ['plugin_style_wait','插件启动等待样式','a2889c2','module','关闭后仍加载插件 CSS，但模块初始化不再等待样式 load；适用于页面启动阶段。'],
    ['sidebar_rendering','侧栏分组与名称测量','cf741f2','source','侧栏分组选择与渲染恢复 1004，撤掉新增名称宽度测量；不回退整套侧栏 CSS。重放只显示一条会话。'],
    ['compression_reasoning','压缩思考流式展示','cf8024b','conditional','关闭压缩 reasoning 增量的新增渲染；保留压缩摘要正文与事件发送时间。只在含压缩的片段生效。'],
    ['media_cards','附件卡片与图片预览','cf741f2','conditional','附件渲染恢复 1004 缩略图，并撤掉新增图片预览点击监听。工具不执行图片上传批处理。']
].map(([id,label,commit,scope,description])=>({id,label,commit,scope,description,source:[],module:[],css:''}));
const byId = Object.fromEntries(definitions.map(d=>[d.id,d]));
function addGroup(id,label,description) {
    const feature={id,label,description,commit:'multiple',scope:'group',source:[],module:[],css:''};
    definitions.push(feature);byId[id]=feature;return feature;
}
addGroup('frontend_bundle','1007 整套前端资源','关闭后使用备份中完整的 1004 页面、脚本、样式和审阅插件；保留重放适配层及跟随控制选项。覆盖所有前端差异，用作旧版基线。').restore_assets={js:'20261004',css:'20261004',html:'20261004',plugin:'20261004'};
addGroup('js_bundle','1007 全部前端脚本','关闭后直接使用完整 1004 编译脚本，包含状态、Dock、路径选择器和所有模块；页面与样式仍按其他开关选择。用于脚本／样式交叉对照。').restore_assets={js:'20261004'};
addGroup('css_bundle','1007 整套样式','关闭后直接使用完整 1004 编译样式，并移除 1007 新增的折叠动效监听；不只是禁用尺寸过渡。页面结构与脚本仍按其他开关选择。').restore_assets={css:'20261004'};
function restoreModules(id,label,description,paths) {
    const group=addGroup(id,label,description);
    for(const file of paths) {
        const before=source(refs.current,file),after=source(refs.old,file);
        if(before===after)throw new Error('Unchanged group module: '+file);
        group.source.push({name:'完整模块 '+file,file,before,after,whole_module:true});
    }
    return group;
}
restoreModules('session_modules','会话加载、侧栏与刷新模块','关闭后整体回退会话管理、侧栏选择与渲染、偏好和新会话入口。包含指示点 RAF、行补丁、定时刷新及前端历史加载。重放仍直接播种历史，不运行原服务器分页。',[
    'frontend/src/app/modules/session-management.js','frontend/src/app/state/session-renderers.js',
    'frontend/src/app/state/session-selectors.js','frontend/src/app/modules/settings.js','frontend/src/app/modules/layout-panels.js']);
const timeHost=declaration(refs.current,'refreshUserMessageTimes');
byId.session_modules.source.push({name:'兼容 1004 消息时间刷新入口',file:timeHost.file,before:timeHost.text,after:timeHost.text+'\n'+declaration(refs.old,'ensureUserMessageTimeAutoRefresh').text});
addGroup('context_refresh','上下文卡片刷新','关闭后回退分段解析、卡片展示、标签设置和刷新请求；不再从标签刷新路径调度新增的两层 RAF 补取。保留上下文数值，不隐藏卡片。');
restoreModules('stream_pipeline','流式事件与执行渲染模块','关闭后整体回退消息／执行行、SSE 消费、事件分派、事件归约和会话状态对象。包含追问和压缩分支，保留原版平滑跟随算法。',[
    'frontend/src/app/modules/message-rendering.js','frontend/src/app/modules/sse-handling.js',
    'frontend/src/app/modules/event-dispatch.js','frontend/src/app/state/session-event-reducer.js','frontend/src/app/state/session-store.js']);
const historyGroup=restoreModules('history_module','历史与滚动状态模块','关闭后整体回退历史、上下文和滚动状态模块，移除新增补页观察器。为 1007 SSE 的读者事件保留空的兼容入口。当前重放不触发服务器补页。',['frontend/src/app/modules/session-scroll-history.js']);
historyGroup.source[0].after+='\nfunction enableHistoryAutoLoadForReader() { /* 1004 paging has no reader gate. */ }\n';
restoreModules('interaction_modules','审批、终端与交互模块','关闭后整体回退审批／终端卡片、技能选择、安全上下文、悬停提示及子代理 UI。只有相应事件／交互涉及这些路径；插件执行面板不在当前重放里运行。',[
    'frontend/src/app/modules/human-interactions.js','frontend/src/app/modules/skill-picker.js',
    'frontend/src/app/modules/permissions.js','frontend/src/app/modules/toc-todo.js',
    'frontend/src/app/modules/subagent-catalog-ui.js','frontend/src/app/modules/subagent-composer-ui.js']);
restoreModules('media_module','媒体展示完整模块','关闭后整体回退 workspace-media 模块的附件展示与预览行为。路径选择器的编译代码可用“全部前端脚本”回退；不执行图片上传。',['frontend/src/app/modules/workspace-media.js']);
for(const name of ['scrollContentAreaIfFollow','followStreamProcessScroll','finishStreamScrollIfFollow','scrollProcessBodyToBottom','scrollChatToBottomIfFollow','repinStreamScrollAfterComposerResize','compensateWindowedLlmCollapse','refreshLiveAutoFollowPins']) {
    const current=declaration(refs.current,name);
    const signature=current.text.slice(0,current.text.indexOf('{'));
    const reset=name==='refreshLiveAutoFollowPins'?'liveAutoFollow=false; streamChatNearBottom=false; streamProcNearBottom=false; ':'';
    byId.auto_follow.source.push({name,file:current.file,before:current.text,after:signature+'{ '+reset+'window.__replayFollowControl.blocked_calls++; }'});
}
const smooth=source(refs.current,'frontend/src/app/modules/smooth-stream.js');
for(const [name,before,after] of [
    ['controller request guard','function request(port, options) {\n        if (!port) return;','function request(port, options) {\n        window.__replayFollowControl.blocked_calls++; return;'],
    ['controller final snap guard','function snapToBottom(port) {\n        if (!port) return false;','function snapToBottom(port) {\n        window.__replayFollowControl.blocked_calls++; return false;']
]) {
    if(smooth.split(before).length!==2)throw new Error('Missing follow entry: '+name);
    byId.auto_follow.source.push({name,file:'frontend/src/app/modules/smooth-stream.js',before,after});
}
const scheduleFollow="port.setAttribute('data-smooth-follow-owned', '1');\n        schedule();\n    }";
if(smooth.split(scheduleFollow).length!==2)throw new Error('Missing follow scheduling entry');
byId.smooth_follow.source.push({name:'request immediate follow without spring RAF',file:'frontend/src/app/modules/smooth-stream.js',before:scheduleFollow,after:`port.setAttribute('data-smooth-follow-owned', '1');
        var floor = Math.max(0, Number(port.scrollHeight) - Number(port.clientHeight));
        state.animatedTop = floor;
        state.followVelocityPxPerSec = 0;
        state.lastStepPx = 0;
        state.lastWrittenTop = floor;
        state.ownedUntil = performance.now() + 100;
        activePorts.delete(port);
        setScrollTopImmediate(port, floor);
        window.__replayFollowControl.immediate_writes++;
    }`});
byId.auto_follow.css=':root .chat-container,:root .process-aggregate-body{overflow-anchor:none!important;scroll-behavior:auto!important}';
function restore(id,names) {
    for (const name of names) {
        const old=declaration(refs.old,name), current=declaration(refs.current,name);
        if(old.text===current.text)throw new Error('No change: '+name);
        byId[id].source.push({name,file:current.file,before:current.text,after:old.text});
    }
}
restore('process_reuse',['selectExecutionProcessGroup','ensureProcessGroup','sealProcessGroup']);
restore('review_updates',['renderExecutionRecord','renderExecutionEvent']);
restore('history_anchor',['maybeAutoLoadOlderHistory','loadOlderHistoryChunk']);
restore('sidebar_rendering',['selectNormalSessionTimeGroups','selectSessionSections','renderSessionListFromStore']);
restore('media_cards',['durableAttachmentImageHost','renderDurableAttachmentImages']);
restore('context_refresh',['contextBreakdownOrNull','renderContextBreakdownCard','setContextTokenLabel','refreshContextTokensFromServer']);
for (const name of ['appendCompressionReasoningDelta','finishCompressionReasoning']) {
    const current=declaration(refs.current,name);
    byId.compression_reasoning.source.push({name,file:current.file,before:current.text,after:'function '+name+'() { /* Diagnostic: 1007 reasoning display disabled. */ }'});
}
const sse=source(refs.current,'frontend/src/app/modules/sse-handling.js');
const start=sse.indexOf("runCtx.processGroupId = savedRecovery");
const end=sse.indexOf('runCtx.currentProcessGroup = existingProcessGroup;',start);
if(start<0||end<0)throw new Error('Missing scoped group lookup');
byId.process_reuse.source.push({name:'attachSessionEventStream group lookup',file:'frontend/src/app/modules/sse-handling.js',before:sse.slice(start,end),after:"var existingProcessGroup = runCtx.stream.querySelector('.process-aggregate:last-of-type');\n        if (existingProcessGroup) {\n            "});
const media=source(refs.current,'frontend/src/app/modules/workspace-media.js');
const preview=parseAst(media).body.filter(n=>n.type==='IfStatement'&&media.slice(n.start,n.end).includes('__durableAttachmentPreviewBound'));
if(preview.length!==1)throw new Error('Missing media preview binding');
byId.media_cards.source.push({name:'preview click binding',file:'frontend/src/app/modules/workspace-media.js',before:media.slice(preview[0].start,preview[0].end),after:''});
byId.collapsed_layout.css=':root:root .process-aggregate.is-collapsed > .process-aggregate-body{display:none!important}';
byId.size_motion.css=`
:root:root{interpolate-size:numeric-only!important}
:root .session-section-body,:root .session-group-body,:root .skill-picker-group-items,:root .dock-files-children,:root .human-terminal-summary,:root .human-terminal-detail,:root .process-aggregate > .process-aggregate-body{transition:opacity var(--ui-collapse-duration) ease,border-color var(--ui-collapse-duration) ease,visibility 0s linear!important}
:root .session-section.is-collapsed > .session-section-body,:root .session-group.is-collapsed > .session-group-body,:root .skill-picker-group.is-collapsed > .skill-picker-group-items,:root .dock-files-children.is-collapsed,:root .human-interaction-card.is-collapsed > .human-terminal-detail,:root .human-interaction-card.is-expanded > .human-terminal-summary,:root .process-aggregate.is-collapsed > .process-aggregate-body{transition-delay:0s,0s,var(--ui-collapse-duration)!important}
:root .feed-chunk{transition:box-shadow .2s ease!important}
:root .feed-chunk-scroller{transition:opacity var(--ui-collapse-duration) ease!important}
:root .dock-rightbar,:root .dock-rightbar.is-collapsed{transition:none!important}`;
byId.sidebar_rendering.css=':root .session-list-head{display:none!important}';
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'versions/manifest.json'),'utf8'));
const version=manifest.versions.find(v=>v.version==='20261007');
const main=fs.readFileSync(path.join(__dirname,'versions',version.version,'site',version.js),'utf8');
const ast=parseAst(main);
const listeners=ast.body.filter(n=>n.type==='ExpressionStatement'&&n.expression.type==='CallExpression'&&['transitionrun','transitionend'].includes(n.expression.arguments[0]?.value)&&main.slice(n.start,n.end).includes('propertyName!=="opacity"'));
if(listeners.length!==2)throw new Error('Missing overflow listeners');
for(const node of listeners)byId.overflow_switch.module.push({name:'opacity '+node.expression.arguments[0].value,before:main.slice(node.start,node.end),after:''});
byId.css_bundle.module=byId.overflow_switch.module.map(op=>({...op}));
const wait=ast.body.find(n=>n.type==='FunctionDeclaration'&&main.slice(n.start,n.end).includes('.dataset[')&&main.slice(n.start,n.end).includes('document.head.appendChild')&&main.slice(n.start,n.end).includes('.styleUrl'));
if(!wait)throw new Error('Missing plugin style wait');
const ret=wait.body.body.find(n=>n.type==='ReturnStatement');
const call=ret.argument.expressions?.at(-1);
if(call?.type!=='CallExpression'||call.arguments[0].type!=='Identifier')throw new Error('Unexpected style wait expression');
const before=main.slice(wait.start,wait.end), callText=main.slice(call.start,call.end);
byId.plugin_style_wait.module.push({name:'plugin stylesheet await',before,after:before.replace(callText,'Promise.resolve(!!'+call.arguments[0].name+')')});
// Verify every source patch against the exact raw strings in the supplied asset.
const strings=[];
function walk(node){if(!node||typeof node!=='object')return;if(node.type==='Literal'&&typeof node.value==='string')strings.push(node.value);if(node.type==='TemplateLiteral'&&!node.expressions.length)strings.push(node.quasis[0].value.cooked);for(const value of Object.values(node)){if(Array.isArray(value))value.forEach(walk);else if(value&&typeof value==='object')walk(value);}}
walk(ast);
const assembled=strings.filter(s=>s.includes('function ')&&s.includes('\n')).join('\n').replace(/\r\n/g,'\n');
function replaceExactly(text,op){const parts=text.split(op.before);if(parts.length!==2)throw new Error('Expected exactly one '+op.name+', found '+(parts.length-1));return parts.join(op.after);}
// Check each independent group against the real compiled archive. Resolution
// of overlapping whole-module and function patches is tested by the engine.
for(const d of definitions){let variant=assembled,module=main;for(const op of d.source)variant=replaceExactly(variant,op);for(const op of d.module)module=replaceExactly(module,op);parseAst(module);}
// Source modules share scope at runtime. Parse the patched declarations, not
// import/index literals or dependency code that happen to contain functions.
for(const d of definitions)for(const op of d.source)if(op.after.trim()&&!['controller request guard','controller final snap guard','request immediate follow without spring RAF'].includes(op.name))parseAst(op.after.startsWith('var existingProcessGroup')?'function check(){'+op.after+'}}':op.after);
const output={schema:2,version:'20261007',base_revision:refs.current,restore_revision:refs.old,base_js_sha256:version.js_sha256,base_css_sha256:version.css_sha256,features:definitions,uncovered:['原后端执行日志、投影、检查点、缓存和数据发送链路：重放工具不运行原服务器，不能设置有效对照开关。','原 Electron 宿主和插件执行面板：便携重放在浏览器运行，不加载这些宿主服务。','图片上传及服务器历史分页：重放不执行上传，直接加载历史。相关模块回退只覆盖当前实际执行的前端路径。']};
const destination=path.join(__dirname,'web/experiments-1007.json');
fs.writeFileSync(destination,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify({file:destination,features:definitions.length,sha256:crypto.createHash('sha256').update(fs.readFileSync(destination)).digest('hex')}));
