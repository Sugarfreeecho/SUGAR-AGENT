/* Compile the actual archived application through the real bootstrap hook. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),cp=require('node:child_process');
const root=path.resolve(__dirname,'..');
const {parseAst}=require(path.resolve(root,'../../frontend/node_modules/rollup/dist/parseAst.js'));
const definition=JSON.parse(fs.readFileSync(path.join(root,'web/experiments-1007.json'),'utf8'));
const main=fs.readFileSync(path.join(root,'versions/20261007/site/assets/main-B_mPBPj8.js'),'utf8');
const ast=parseAst(main),variables=new Map();
for(const node of ast.body)if(node.type==='VariableDeclaration')for(const d of node.declarations)if(d.id.type==='Identifier')variables.set(d.id.name,d.init);
function value(node){
    if(node.type==='Identifier')return value(variables.get(node.name));
    if(node.type==='Literal')return node.regex?new RegExp(node.regex.pattern,node.regex.flags):node.value;
    if(node.type==='TemplateLiteral'&&!node.expressions.length)return node.quasis[0].value.cooked;
    if(node.type==='ArrayExpression')return node.elements.map(value);
    if(node.type==='BinaryExpression'&&node.operator==='+')return value(node.left)+value(node.right);
    if(node.type==='CallExpression'&&node.callee.type==='MemberExpression')return value(node.callee.object)[node.callee.property.name](...node.arguments.map(value));
    throw new Error('Unsupported source assembly expression '+node.type);
}
const invocation=ast.body.find(n=>n.type==='ExpressionStatement'&&n.expression.type==='CallExpression'&&n.expression.callee.type==='CallExpression'&&n.expression.callee.callee.name==='Function');
assert(invocation,'Application Function constructor missing');
const application=value(invocation.expression.callee.arguments[0]);
assert(application.includes('function newDomContext('));
const bootstrap=fs.readFileSync(path.join(root,'web/bootstrap.js'),'utf8');
const cases=[[],...definition.features.map(f=>[f.id]),definition.features.map(f=>f.id),definition.features.filter(f=>f.commit!=='shared').map(f=>f.id),
    ['session_modules','stream_pipeline','history_module','context_refresh','interaction_modules','media_module','review_updates','plugin_style_wait'],
    ['stream_pipeline','session_modules'],['history_module','context_refresh'],['js_bundle','auto_follow'],['css_bundle','overflow_switch']];
const python=path.resolve(root,'../../python/python.exe');
const configs=JSON.parse(cp.execFileSync(python,['-c',`import sys,json;sys.path.insert(0,${JSON.stringify(root)});from experiments import Experiments;from pathlib import Path;r=Path(${JSON.stringify(root)});v=json.loads((r/'versions/manifest.json').read_text(encoding='utf8'))['versions'];e=Experiments(r,{x['version']:x for x in v});c=json.loads(sys.argv[1]);print(json.dumps([e.config('20261007',tuple(s)) for s in c]))`,JSON.stringify(cases)],{encoding:'utf8',maxBuffer:64e6}));
function oldApplication(){
    const old=fs.readFileSync(path.join(root,'versions/20261004/site/assets/main-4D7D2on2.js'),'utf8');
    const oldAst=parseAst(old),oldVars=new Map();for(const n of oldAst.body)if(n.type==='VariableDeclaration')for(const d of n.declarations)if(d.id.type==='Identifier')oldVars.set(d.id.name,d.init);
    const saved=new Map(variables);variables.clear();for(const [k,v] of oldVars)variables.set(k,v);
    const call=oldAst.body.find(n=>n.type==='ExpressionStatement'&&n.expression.type==='CallExpression'&&n.expression.callee.type==='CallExpression'&&n.expression.callee.callee.name==='Function');
    const body=value(call.expression.callee.arguments[0]);variables.clear();for(const [k,v] of saved)variables.set(k,v);return body;
}
const archivedOld=oldApplication();
function compile(config,body=config.asset_versions.js==='20261004'?archivedOld:application){
    const {source_operations:operations,disabled}=config;
    const sandbox={URLSearchParams,location:{search:'?real=1'},localStorage:{getItem:()=> 'test'},__REPLAY_CONFIG__:{experiments:{fingerprint:'test',source_operations:operations,disabled}},addEventListener:()=>{}};
    sandbox.window=sandbox;vm.createContext(sandbox);vm.runInContext(bootstrap,sandbox);
    sandbox.body=body;
    vm.runInContext('Function(body)',sandbox);
    assert.equal(sandbox.__replayExperimentState.source_ready,true);
    assert.equal(sandbox.__replayExperimentState.source_operations.length,operations.length);
}
for(const config of configs)compile(config);
for(const feature of definition.features){
    let changed=main;
    for(const op of feature.module){assert.equal(changed.split(op.before).length,2);changed=changed.replace(op.before,op.after);}
    parseAst(changed);
}
const op=definition.features.find(f=>f.id==='process_reuse').source[0];
assert.throws(()=>compile(configs.find(c=>c.disabled.length===1&&c.disabled[0]==='process_reuse'),application.replace(op.before,'')),/开关适配失败/);
// Exercise the actual controller: off must avoid reads/writes and scheduling;
// immediate must reach the floor without queuing a continuous follow loop.
const appAst=parseAst(application);
function functionSource(name){const n=appAst.body.find(n=>n.type==='FunctionDeclaration'&&n.id.name===name);return application.slice(n.start,n.end);}
const settings=appAst.body.find(n=>n.type==='VariableDeclaration'&&n.declarations.some(d=>d.id.name==='SMOOTH_STREAM_CONFIG'));
const primitives=application.slice(settings.start,settings.end)+'\n'+['computeSmoothFollowSpringStep','smoothStreamClamp','setScrollTopImmediate'].map(functionSource).join('\n');
function controllerTest(disabled){
    let source=functionSource('createSmoothFollowController');
    for(const feature of definition.features.filter(f=>disabled.includes(f.id)))for(const op of feature.source)if(source.includes(op.before))source=source.replace(op.before,op.after);
    const scheduled=new Map(), listeners=new Map();let next=1,top=20,reads=0,writes=0;
    const sandbox={performance:{now:()=>20},isSmoothStreamActive:()=>true,isHistorySmoothScrollActive:()=>false,
        requestAnimationFrame:fn=>{const id=next++;scheduled.set(id,fn);return id;},cancelAnimationFrame:id=>scheduled.delete(id),setTimeout:()=>1,clearTimeout:()=>{},
        __replayFollowControl:{blocked_calls:0,immediate_writes:0}};sandbox.window=sandbox;
    const port={isConnected:true,style:{},addEventListener:(name,fn)=>listeners.set(name,fn),setAttribute:()=>{},removeAttribute:()=>{},
        get scrollTop(){reads++;return top;},set scrollTop(value){writes++;top=value;},get scrollHeight(){reads++;return 1000;},get clientHeight(){reads++;return 200;}};
    const controller=vm.runInNewContext(primitives+'\n'+source+'\ncreateSmoothFollowController()',sandbox);
    controller.request(port);
    if(disabled.includes('auto_follow')){
        assert.equal(controller.snapToBottom(port),false);assert.equal(top,20);assert.equal(reads,0);assert.equal(writes,0);assert.equal(scheduled.size,0);assert.equal(controller.isFollowing(port),false);
    }else if(disabled.includes('smooth_follow')){
        assert.equal(top,800);assert.equal(scheduled.size,0);assert.equal(controller.isFollowing(port),true);assert.equal(sandbox.__replayFollowControl.immediate_writes,1);
        listeners.get('wheel')({deltaY:-10});assert.equal(controller.isReaderDetached(port),true);
        top=300;controller.request(port);assert.equal(top,300);assert.equal(scheduled.size,0);
    }else{
        assert.equal(top,20);assert.equal(scheduled.size,1);const [id,frame]=scheduled.entries().next().value;scheduled.delete(id);frame(16.67);assert(top>20&&top<=23);assert.equal(scheduled.size,1);
    }
}
controllerTest([]);controllerTest(['auto_follow']);controllerTest(['smooth_follow']);controllerTest(['auto_follow','smooth_follow']);
console.log('Actual archived applications compile: each switch, group combinations, complete baseline, crossed assets, all off; mismatches rejected.');
console.log('Follow behavior verified: original spring, immediate without continuous RAF, off without layout reads/writes, reader detachment.');
