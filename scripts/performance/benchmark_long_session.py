"""Read-only log analysis and isolated current-frontend history scaling benchmark.

Run with the repository Python runtime. No LLM requests or production API calls.
The browser routes every request to local fixture data or repository assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))


def summary(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    return {"n": len(values), "median": round(statistics.median(values), 3),
            "p95": round(values[min(len(values)-1, int(len(values)*.95))], 3),
            "max": round(values[-1], 3)}


def log_analysis(since):
    pattern = re.compile(r"^(\d{4}-\d\d-\d\d [\d:,]+) - agent_harness - INFO - (\w+_timing) session=(\S+) (.*)$")
    dedup, rows = set(), []
    for path in (ROOT / "logs").glob("*.log"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = pattern.match(line)
            if not match or match[1] < since or line in dedup:
                continue
            dedup.add(line)
            fields = dict(re.findall(r"([\w:]+)=([^\s,]+)", match[4]))
            nums = {k: int(v.removesuffix("ms")) for k, v in fields.items()
                    if re.fullmatch(r"\d+(ms)?", v)}
            first = re.search(r"(?<!\w)first_delta@(\d+)ms", match[4])
            if first:
                nums["first_delta_ms"] = int(first[1])
            rows.append({"at": match[1], "kind": match[2], "session": match[3],
                         "file": path.name, "fields": fields, "nums": nums})
    rows.sort(key=lambda x: x["at"])
    buckets, by_session, last = defaultdict(lambda: defaultdict(list)), defaultdict(list), {}
    counts = defaultdict(int)
    all_metrics = defaultdict(list)
    tools = defaultdict(list)
    tools_by_bucket = defaultdict(lambda: defaultdict(list))
    for row in rows:
        n, kind, sid = row["nums"], row["kind"], row["session"]
        counts[kind] += 1
        if kind == "pre_api_timing" and "estimated_tokens" in n:
            last[sid] = row
            by_session[sid].append(row)
        prior = last.get(sid)
        if prior:
            tokens = prior["nums"]["estimated_tokens"]
            bucket = "<20k" if tokens < 20000 else "20-80k" if tokens < 80000 else "80-160k" if tokens < 160000 else ">=160k"
            for key, val in n.items():
                if key in {"total", "token_estimate", "build_messages", "resolve_model_config",
                           "ui_emit", "append_model_history", "first_delta_ms",
                           "worker_done_to_consumed_ms", "bridge_emit_max_ms", "round_gap_ms", "invoke_ms"}:
                    buckets[bucket][kind + "." + key].append(val)
        if kind == "tool_execution_timing":
            tools[row["fields"].get("tool", "unknown")].append(n.get("invoke_ms", 0))
            if prior:
                tools_by_bucket[bucket][row["fields"].get("tool", "unknown")].append(n.get("invoke_ms",0))
        if kind in {"tool_result_post_timing", "llm_local_consumer_timing", "tool_to_next_llm_first_delta_timing"}:
            for key, val in n.items():
                if key != "react_iter":
                    all_metrics[kind + "." + key].append(val)
    same_session = []
    for sid, items in by_session.items():
        if len(items) < 10:
            continue
        low = [x for x in items if x["nums"]["estimated_tokens"] < 80000]
        high = [x for x in items if x["nums"]["estimated_tokens"] >= 160000]
        if len(low) >= 5 and len(high) >= 5:
            same_session.append({"session": sid, "low": {key: summary([x["nums"][key] for x in low if key in x["nums"]])
                                 for key in ("total", "token_estimate", "build_messages")},
                                 "high": {key: summary([x["nums"][key] for x in high if key in x["nums"]])
                                 for key in ("total", "token_estimate", "build_messages")}})
    examples = sorted((x for x in rows if x["kind"] == "pre_api_timing"),
                      key=lambda x: x["nums"].get("total", 0), reverse=True)[:5]
    return {"since": since, "unique_rows": len(rows), "counts": dict(counts),
            "input_token_buckets": {b: {k: summary(v) for k, v in ms.items()} for b, ms in buckets.items()},
            "all_metrics": {k: summary(v) for k, v in all_metrics.items()},
            "tool_invocation_ms": {k: summary(v) for k, v in tools.items()},
            "tool_invocation_ms_by_input_tokens": {b:{k:summary(v) for k,v in ts.items()} for b,ts in tools_by_bucket.items()},
            "same_session_comparisons": same_session, "slow_pre_api_examples": examples,
            "models": dict(Counter(x['fields'].get('model','unknown') for x in rows if x['kind']=='pre_api_timing')),
            "ordinary_latency_metrics": {k: summary([x for x in v if x < 120000]) for k,v in all_metrics.items()},
            "latency_samples_over_120_seconds": {k: sum(x>=120000 for x in v) for k,v in all_metrics.items() if any(x>=120000 for x in v)}}


def backend_benchmark():
    import psutil
    from agent_messages import UserMessage
    from agent_tokenizer import _clear_flatten_token_cache, count_message_tokens_incremental
    from runtime_v2.projector import RuntimeProjector
    from runtime_v2.event_schema import RuntimeEvent
    results = [{"kind":"host_before_backend","cpu_percent":psutil.cpu_percent(interval=.3),"memory_percent":psutil.virtual_memory().percent}]
    count_message_tokens_incremental([UserMessage("warm up")])
    for count in (20, 200, 1000, 5000):
        projector = RuntimeProjector()
        snapshot = projector.empty_snapshot()
        snapshot["messages"] = [{"seq": i, "role": "user", "payload": {"content": "history"}} for i in range(count)]
        snapshot["raw_model_messages"] = list(snapshot["messages"])
        snapshot["visible_messages"] = list(snapshot["messages"])
        snapshot["model_messages"] = list(snapshot["messages"])
        snapshot["executions"] = {str(i): {"execution_id": str(i), "content": "x"*1000} for i in range(count)}
        event = RuntimeEvent(seq=count+1, type="execution_recorded", session_id="fixture",
                             payload={"execution_id": "0", "content_delta": "新字", "kind": "reasoning"})
        times = []
        for _ in range(100):
            start = time.perf_counter()
            projector.project_incremental(snapshot, event)
            times.append((time.perf_counter()-start)*1000)
        results.append({"kind": "incremental_projection", "history_rows": count, "ms": summary(times)})
    for chars in (30000, 300000, 1000000):
        messages = [UserMessage(("历史内容 abc123\n"*100)[:1000]) for _ in range(chars//1000)]
        samples = defaultdict(list)
        for _ in range(5):
            _clear_flatten_token_cache()
            for label, sequence in (("cold", messages), ("warm", messages),
                                    ("append", messages+[UserMessage("新增内容"*100)])):
                start = time.perf_counter()
                count_message_tokens_incremental(sequence)
                samples[label].append((time.perf_counter()-start)*1000)
        results.append({"kind": "incremental_token_count", "history_chars": chars,
                        "ms": {k: summary(v) for k, v in samples.items()}})
    results.append({"kind":"host_after_backend","cpu_percent":psutil.cpu_percent(interval=.3),"memory_percent":psutil.virtual_memory().percent})
    return results


EXPOSE = r"""
window.__longBench = {
 setup: function(turns, mode) {
   var ctx = __archiveRuntime.setup(8000);
   replayingMessages = true;
   try {
     for(var t=0;t<turns;t++) {
       ctx.runId='history-'+t; ctx.processGroupId='history-group-'+t;
       renderEvent(ctx,{type:'user',content:'历史轮次 '+t},t*21,currentSessionId);
       for(var i=0;i<20;i++) renderExecutionRecord(ctx,{
         execution_id:'history-'+t+'-'+i, kind:'reasoning',status:'completed',
         content:'历史过程：检查代码，记录结果。 abc xyz\n'.repeat(30),
         run_id:ctx.runId,process_group_id:ctx.processGroupId,react_iter:i+1,last_runtime_seq:t*21+i+1
       },currentSessionId,{snapshot:true});
     }
   } finally {replayingMessages=false;}
   ctx.runId='live';ctx.processGroupId='live-group';
   renderEvent(ctx,{type:'user',content:'当前固定新增输出'},turns*21,currentSessionId);
   ctx.benchPrefix='当前输出：检查文件并记录代码结果。 abc xyz\n'.repeat(40);
   renderExecutionRecord(ctx,{execution_id:'live-row',kind:'reasoning',status:'generating',
     content:ctx.benchPrefix,run_id:'live',process_group_id:'live-group',react_iter:1,last_runtime_seq:1},currentSessionId,{snapshot:true});
   if(mode==='prune') {
     var users=Array.from(ctx.stream.querySelectorAll('.msg-wrap--user'));
     var boundary=users[Math.max(0,users.length-3)];
     Array.from(ctx.stream.children).forEach(function(n){
       if(n!==boundary && (n.compareDocumentPosition(boundary)&Node.DOCUMENT_POSITION_FOLLOWING)) n.remove();
     });
   }
   if(mode==='map') {
     var rowIndex=new Map(Array.from(ctx.stream.querySelectorAll('[data-execution-id]')).map(function(n){return [n.dataset.executionId,n];}));
     var query=ctx.stream.querySelectorAll.bind(ctx.stream);
     ctx.stream.querySelectorAll=function(sel){
       return sel==='[data-execution-id]' ? [rowIndex.get('live-row')] : query(sel);
     };
   }
   liveAutoFollow=true;streamChatNearBottom=true;streamProcNearBottom=true;
   __archiveRuntime.follow(ctx);
   return ctx;
 },
 render: function(ctx,text,seq){renderExecutionRecord(ctx,{execution_id:'live-row',kind:'reasoning',
   status:'generating',content:text,run_id:'live',process_group_id:'live-group',react_iter:1,last_runtime_seq:seq},currentSessionId,{smoothText:true});},
 burst: async function(ctx) {
   updateExecutionRecord(currentSessionId,{execution_id:'live-row',kind:'reasoning',status:'generating',
     content:ctx.benchPrefix,run_id:'live',process_group_id:'live-group',react_iter:1,last_runtime_seq:1});
   var text=ctx.benchPrefix,packets='';
   for(var i=0;i<150;i++) {
     var delta='检查结果 abc 中文 '.slice(0,8);text+=delta;
     packets+='data: '+JSON.stringify({type:'execution_update',session_id:currentSessionId,run_id:'live',
       runtime_seq:i+2,seq:i+2,update:{execution_id:'live-row',kind:'reasoning',status:'generating',
       text_delta:delta,process_group_id:'live-group',react_iter:1}})+'\n\n';
   }
   await consumeAgentSseResponseInner(new Response(new TextEncoder().encode(packets),
     {headers:{'Content-Type':'text/event-stream'}}),ctx,currentSessionId,0);
   return text;
 },
 finish: function(ctx,text){flushLlmDeltaText(ctx);return ctx.stream.querySelector('[data-execution-id="live-row"] .feed-chunk-scroller')._llmRawText===text;}
};
"""


def browser_benchmark(repeats, quick=False, burst=False, production_only=False):
    import psutil
    from playwright.sync_api import sync_playwright
    dist = ROOT / "app/templates/dist"
    html = (dist / "index.html").read_text(encoding="utf-8")
    script_url = re.search(r'src="(/assets/main-[^"]+\.js)"', html)[1]
    bootstrap = (ROOT / "scripts/performance/archived_stream_bootstrap.js").read_text(encoding="utf-8")
    # Append a JS string after the original injection; preserve literal escapes.
    bootstrap = bootstrap.replace("return Reflect.apply(nativeFunction, this, args);",
        "if (String(args[last]).includes('function newDomContext(')) args[last] += "
        + json.dumps(EXPOSE) + ";\n"
        + "if(new URLSearchParams(location.search).get('budget')==='on' && String(args[last]).includes('function newDomContext(')) {"
        + "var needle='for (const line of lines) {';if(args[last].split(needle).length!==2)throw new Error('SSE budget adaptation must match once');"
        + "args[last]=args[last].replace(needle,'let batchStarted=performance.now(); for (const line of lines) { if(performance.now()-batchStarted>=4) { await new Promise(resolve=>setTimeout(resolve,0)); batchStarted=performance.now(); }');}\n"
        + "return Reflect.apply(nativeFunction, this, args);")
    output = []
    host_before = {"cpu_percent":psutil.cpu_percent(interval=.3),"memory_percent":psutil.virtual_memory().percent}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        scenarios = [(1, "baseline", True), (10, "baseline", True), (50, "baseline", True),
                     (50, "prune", True), (50, "map", True), (50, "baseline", False)]
        if burst:
            scenarios = [(1,"baseline",True),(50,"baseline",True),(50,"map",True),(50,"prune",True),(50,"budget",True)]
        if production_only:
            scenarios = [(1,"baseline",True),(10,"baseline",True),(50,"baseline",True)]
        if quick:
            scenarios = scenarios[:1]
        for trial in range(repeats):
            for turns, mode, plugins in (scenarios if trial % 2 == 0 else reversed(scenarios)):
                context = browser.new_context(viewport={"width":1280,"height":800},device_scale_factor=1)
                context.add_init_script("window.__REPLAY_CONFIG__={version:'current',plugins:"+str(plugins).lower()+"};\n"+bootstrap)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                def route_request(route):
                    path = urlparse(route.request.url).path
                    if path == "/":
                        return route.fulfill(body=html, content_type="text/html")
                    if path == "/api/extensions":
                        data = {"ui_contributions": [{"plugin_id":"change-review","id":"chat","slot":"chat.extension",
                                "renderer":{"module":"/plugin-assets/change-review/web/change-review.js","style":"/plugin-assets/change-review/web/change-review.css"}}]} if plugins else {"ui_contributions": []}
                        return route.fulfill(json=data)
                    if path.startswith("/api/") or path.startswith("/sessions"):
                        return route.fulfill(json={"items":[],"events":[],"messages":[],"sessions":[],"profiles":[],"panels":[],"active":False,"ok":True})
                    dest = (ROOT / "plugins" / path.removeprefix("/plugin-assets/")) if path.startswith("/plugin-assets/") else dist / path.lstrip("/")
                    if dest.is_file() and dest.resolve().is_relative_to(ROOT.resolve()):
                        return route.fulfill(body=dest.read_bytes(),content_type=mimetypes.guess_type(str(dest))[0] or "application/octet-stream")
                    return route.fulfill(status=404,body="{}")
                page.route("**/*", route_request)
                page.goto("http://127.0.0.1:54879/"+ ("?plugins=off" if not plugins else "?budget=on" if mode=='budget' else ""))
                try:
                    page.wait_for_function("!!window.__longBench", timeout=15000)
                except Exception:
                    print(json.dumps({"initialization_errors":errors,"title":page.title()},ensure_ascii=False),flush=True)
                    raise
                page.evaluate("([turns,mode])=>{window.bctx=__longBench.setup(turns,mode)}", [turns,mode])
                page.wait_for_timeout(700)
                empty_cadence = page.evaluate("""async()=>{const gaps=[];let last=0;await new Promise(resolve=>{const until=performance.now()+500;function f(t){if(last)gaps.push(t-last);last=t;if(t<until)requestAnimationFrame(f);else resolve();}requestAnimationFrame(f);});gaps.sort((a,b)=>a-b);return {p95_ms:gaps[Math.floor(gaps.length*.95)],max_ms:Math.max(...gaps)};}""")
                host_cpu = psutil.cpu_percent(interval=.1)
                result = page.evaluate(r"""async burst => {
                  const gaps=[],renders=[],motion=[],chatMotion=[],longs=[];let last=0,active=true;
                  const port=bctx.currentProcessGroup.querySelector('.process-aggregate-body');
                  const chat=document.getElementById('chat-container');
                  const obs=new PerformanceObserver(list=>longs.push(...list.getEntries().map(e=>e.duration)));
                  obs.observe({type:'longtask',buffered:false});
                  function frame(t){if(last)gaps.push(t-last);last=t;motion.push(port.scrollTop);chatMotion.push(chat.scrollTop);if(active)requestAnimationFrame(frame);}
                  requestAnimationFrame(frame);
                  await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
                  let text=bctx.benchPrefix;const start=performance.now();
                  if(burst) {text=await __longBench.burst(bctx);}
                  else for(let i=0;i<150;i++) {
                    if(i===50 || i===100)await new Promise(r=>setTimeout(r,300));
                    text+='检查结果 abc 中文 '.slice(0,8);
                    const t=performance.now();__longBench.render(bctx,text,i+2);renders.push(performance.now()-t);
                    await new Promise(r=>setTimeout(r,30));
                  }
                  const processing_ms=performance.now()-start;
                  await new Promise(r=>setTimeout(r,400));
                  const verified=__longBench.finish(bctx,text);
                  active=false;obs.disconnect();
                  const pct=(a,p)=>{a=a.slice().sort((x,y)=>x-y);return a[Math.min(a.length-1,Math.floor(a.length*p))]||0;};
                  return {elapsed_ms:performance.now()-start,processing_ms,frames:gaps.length,raf_p95_ms:pct(gaps,.95),
                    raf_max_ms:Math.max(...gaps),raf_over_50:gaps.filter(x=>x>50).length,
                    render_median_ms:renders.length?pct(renders,.5):null,render_p95_ms:renders.length?pct(renders,.95):null,render_max_ms:renders.length?Math.max(...renders):null,
                    longtask_count:longs.length,longtask_total_ms:longs.reduce((a,b)=>a+b,0),
                    scroll_distance_px:Math.max(...motion)-Math.min(...motion),verified,
                    chat_scroll_distance_px:Math.max(...chatMotion)-Math.min(...chatMotion),
                    process_height:port.clientHeight,process_scroll_height:port.scrollHeight,
                    dom_nodes:bctx.stream.querySelectorAll('*').length,
                    execution_rows:Element.prototype.querySelectorAll.call(bctx.stream,'[data-execution-id]').length,
                    visibility:document.visibilityState,user_agent:navigator.userAgent};
                }""", burst)
                result.update(turns=turns,mode=mode,plugins=plugins,trial=trial,errors=errors,static_raf=empty_cadence,host_cpu_percent=host_cpu,burst=burst)
                output.append(result)
                print(json.dumps({"browser_progress":{k:result[k] for k in
                    ("turns","mode","trial","burst","processing_ms","raf_max_ms","verified")}},ensure_ascii=False),flush=True)
                context.close()
        browser.close()
    return {"dist_js":script_url,"dist_sha256":hashlib.sha256((dist/script_url.lstrip('/')).read_bytes()).hexdigest(),
            "headless":True,"rows_per_turn":20,"text_per_history_row_chars":len('历史过程：检查代码，记录结果。 abc xyz\n')*30,"new_chars":1200,"host_before":host_before,"samples":output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--since", default="2026-10-11")
    parser.add_argument("--repeats",type=int,default=3)
    parser.add_argument("--quick",action="store_true")
    parser.add_argument("--skip-browser",action="store_true")
    parser.add_argument("--browser-only",action="store_true")
    parser.add_argument("--burst",action="store_true",help="Feed 150 execution updates through the real SSE parser in one cached chunk")
    parser.add_argument("--production-only",action="store_true",help="Measure original rendering without diagnostic variants")
    args = parser.parse_args()
    result = {}
    if not args.browser_only:
        result["logs"] = log_analysis(args.since)
        print(json.dumps({"logs_complete":result["logs"]["unique_rows"]}),flush=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        result["backend"] = backend_benchmark()
    if not args.skip_browser:
        result["browser"] = browser_benchmark(args.repeats,args.quick,args.burst,args.production_only)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"saved":str(args.output),"log_rows":result.get("logs",{}).get("unique_rows")},ensure_ascii=False))


if __name__ == "__main__":
    main()
