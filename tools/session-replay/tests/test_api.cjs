// Exercise JSON and selected-file retries, including concurrent stale requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/api.js'),'utf8');

async function run() {
    let currentToken='first', refreshes=0, committed=0;
    const requests=[];
    const scope={window:{},Blob,fetch:async(path,options={})=>{
        requests.push({path,token:options.headers?.['X-Replay-Token'],body:options.body});
        if(path==='/api/replay/health') {
            refreshes++;
            await new Promise(resolve=>setTimeout(resolve,5));
            return {ok:true,json:async()=>({token:currentToken})};
        }
        if(path==='/foreign') return {ok:false,status:403,json:async()=>({code:'LOCAL_PAGE_REQUIRED',error:'wrong origin'})};
        if(path==='/bad-import') return {ok:false,status:400,json:async()=>({error:'bad session',candidates:['a','b']})};
        if(options.headers['X-Replay-Token']!==currentToken)
            return {ok:false,status:403,json:async()=>({code:'TOKEN_EXPIRED'})};
        committed++;
        return {ok:true,json:async()=>({ok:true})};
    }};
    vm.runInNewContext(source,scope);
    const api=scope.window.createReplayApi('first');
    currentToken='after-restart';
    const body=new Blob(['events.jsonl\n真实文本'],{type:'application/octet-stream'});
    await Promise.all([
        api('/api/replay/import',{method:'POST',body:{path:'D:\\会话.zip'}}),
        api('/api/replay/upload/file',{method:'POST',body})
    ]);
    assert.equal(refreshes,1);
    assert.equal(committed,2);
    assert.equal(api.token(),'after-restart');
    const imports=requests.filter(r=>r.path==='/api/replay/import');
    assert.equal(imports.length,2);
    assert.equal(imports[0].body,imports[1].body);
    assert.deepEqual(JSON.parse(imports[1].body),{path:'D:\\会话.zip'});
    const files=requests.filter(r=>r.path==='/api/replay/upload/file');
    assert.equal(files.length,2);
    assert.equal(files[0].body,body);
    assert.equal(files[1].body,body);
    await assert.rejects(api('/foreign',{method:'POST'}),/wrong origin/);
    assert.equal(refreshes,1);
    await assert.rejects(api('/bad-import',{method:'POST'}),error=>error.data.candidates.length===2);
    const beforeInit=scope.window.createReplayApi();
    await beforeInit('/api/replay/import',{method:'POST',body:{path:'before health loaded'}});
    assert.equal(beforeInit.token(),currentToken);
    assert.equal(committed,3);
    // A second restart during refresh must fail after one retry, not loop forever.
    const broken=scope.window.createReplayApi('old');
    scope.fetch=async(path)=>path==='/api/replay/health'
        ? {ok:true,json:async()=>({token:'also-old'})}
        : {ok:false,status:403,json:async()=>({code:'TOKEN_EXPIRED',error:'expired again'})};
    await assert.rejects(broken('/api/replay/import',{method:'POST',body:{path:'a'}}),/expired again/);
    console.log('Replay API restart/file/origin recovery checks passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
