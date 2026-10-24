const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const read = name => fs.readFileSync(path.join(root, 'frontend/src/app', name), 'utf8');
const scroll = read('modules/session-scroll-history.js');
function fn(name) {
    const match = scroll.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^\\}', 'm'));
    assert(match, name); return match[0];
}
let response, release, requests = 0, paints = 0;
const context = vm.createContext({console, Date, Map, Set, Number, Object, currentSessionId:'s',
    applyMessageEvent: (_sid,event) => ({event}), sessionStore:{},
    refreshAggregateStatsSmart() {},
    setContextTokenLabel() { paints++; },
    contextBreakdownOrNull: value => value || null, contextBreakdownRefetchTried:{},
    fetch: async () => { requests++; await new Promise(resolve => {release=resolve;});
        return {ok:true,json:async()=>response}; },
});
vm.runInContext(read('state/context-store.js')+'\n'+read('state/session-event-reducer.js')+'\n'+
    'let contextTokenRequestSeq=0;const contextTokenInFlightBySession={};const CONTEXT_TOKEN_CACHE_TTL_MS=3000;\n'+
    ['recordContextTokens','applyContextTokenLabelForCurrentSession','refreshContextTokensFromServer'].map(fn).join('\n'), context);
const rendering=read('modules/message-rendering.js');
vm.runInContext(rendering.match(/^function applyCacheStatsFromEvent\([^]*?^\}/m)[0],context);
const evaluate=code=>vm.runInContext(code,context);

(async()=>{
    evaluate("recordContextTokens('s',10000,128000,{system_tokens:1000,tools_tokens:1000,message_tokens:8000})");
    const original=evaluate("selectContextTokens('s')"), version=evaluate("getContextTokenVersion('s')");
    for(const source of ['history','history-older','history-target']) {
        context.source=source;
        evaluate("applySessionEvent({type:'context_tokens',estimated:110000,threshold:120000},{sessionId:'s',source})");
        assert.equal(evaluate("selectContextTokens('s')"),original);
    }
    evaluate("applyCacheStatsFromEvent({currentProcessGroup:{isConnected:true,dataset:{}}},{type:'cache_stats',input_tokens:90000},'s')");
    assert.equal(evaluate("selectContextTokens('s')"),original, 'old/request usage cannot publish current context');
    assert.equal(evaluate("getContextTokenVersion('s')"),version, 'replay cannot refresh cache freshness/version');
    assert.equal(paints,1);

    const pending=context.refreshContextTokensFromServer('s',null,true);
    assert.equal(requests,1);
    evaluate("applySessionEvent({type:'context_tokens',estimated:5000,threshold:128000},{sessionId:'s',source:'sse'})");
    response={ok:true,estimated:90000,threshold:128000};release();await pending;
    assert.equal(evaluate("selectContextTokens('s').estimated"),5000,'late GET cannot overwrite post-compression/live values');
    assert.equal(evaluate("selectContextTokens('s').breakdown"),null,'new total cannot retain another reading composition');

    context.oldVersion=evaluate("getContextTokenVersion('s')");
    evaluate("recordContextTokens('s',80000,128000,null,{expectedVersion:oldVersion-1})");
    assert.equal(evaluate("selectContextTokens('s').estimated"),5000,'late startup snapshot cannot replace current state');
    evaluate("recordContextTokens('s',5000,undefined)");
    assert.equal(evaluate("selectContextTokens('s').threshold"),128000,'partial update preserves current threshold');
    evaluate("clearContextStateForSession('s');recordContextTokens('s',80000,128000,null,{expectedVersion:oldVersion})");
    assert.equal(evaluate("selectContextTokens('s')"),null,'clearing invalidates outstanding reads');

    evaluate("recordContextTokens('s',6000,128000,null,{stale:true})");
    assert.equal(evaluate("selectContextTokens('s').updatedAt"),0,'stale checkpoint must not suppress recalculation');
    const fresh=context.refreshContextTokensFromServer('s',null,true);
    response={ok:true,estimated:7000,threshold:128000};release();await fresh;
    assert.equal(evaluate("selectContextTokens('s').estimated"),7000,'a valid new response must still be accepted');
    const stale=context.refreshContextTokensFromServer('s',null,true);
    response={ok:true,estimated:7100,threshold:128000,pending_recalculation:true};release();await stale;
    assert.equal(evaluate("selectContextTokens('s').updatedAt"),0,'a stale GET must not suppress the next recalculation');
    console.log('Context history isolation, threshold integrity, fresh live values and stale read rejection passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
