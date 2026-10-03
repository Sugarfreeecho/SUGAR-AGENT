"""Compare isolated UI work with saved source files, without changing application state.

Usage: python scripts/benchmark_frontend_performance.py --baseline-dir PATH
The baseline directory contains session-scroll-history.js and message-rendering.js.
"""
import argparse
import json
import os
import statistics
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STREAM = "frontend/src/app/modules/session-scroll-history.js"
RENDER = "frontend/src/app/modules/message-rendering.js"


def setup_stream(page, source, css, helpers):
    page.set_content(
        "<style>" + css + "</style><style>.fixture{width:800px}</style>"
        "<div id='subject' class='fixture process-aggregate'><div class='process-aggregate-body'>"
        "<div class='feed-item feed--llm'><div class='feed-row'><div class='feed-chunk is-streaming'>"
        "<div class='feed-chunk-scroller' id='sc'></div></div></div></div></div></div>"
    )
    page.add_script_tag(content=(
        "var LOG_TRUNCATE_HEAD_LINES=100,LOG_TRUNCATE_TAIL_LINES=100,"
        "LOG_TRUNCATE_HEAD_CHARS=12000,LOG_TRUNCATE_TAIL_CHARS=12000;"
        + helpers + source[source.index("function writeLlmStreamText("):
                           source.index("function appendLlmRevealedText(")]
    ))


def output(**result):
    print(json.dumps(result, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    args = parser.parse_args()
    rendering = (ROOT / RENDER).read_text(encoding="utf-8")
    helpers = rendering[rendering.index("function trimSurroundingBlankLines("):
                        rendering.index("function reactFeedPhase(")]
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
        )
        page = browser.new_page(viewport={"width": 1100, "height": 800})
        for version, directory in (("before", args.baseline_dir), ("after", ROOT)):
            source = (directory / (Path(STREAM).name if version == "before" else STREAM)).read_text(encoding="utf-8")
            for kind in ("multi", "single"):
                samples = []
                for _ in range(3):
                    setup_stream(page, source, css, helpers)
                    samples.append(page.evaluate("""kind => {
                      const sc=document.getElementById('sc');
                      const unit=kind==='single'?'x'.repeat(1000):'word 中文 abc '.repeat(8)+'\\n';
                      const text=unit.repeat(Math.ceil(300000/unit.length)).slice(0,300000),times=[];
                      for(let i=1000;i<=text.length;i+=1000){
                        const start=performance.now();writeLlmStreamText(sc,text.slice(0,i),'reasoning');
                        sc.getBoundingClientRect();times.push(performance.now()-start);
                      }
                      return {total:times.reduce((a,b)=>a+b,0),max:Math.max(...times)};
                    }""", kind))
                output(version=version, scenario=kind, updates=300, characters=300000,
                       median_total_ms=round(statistics.median(s["total"] for s in samples), 2),
                       max_update_ms=round(max(s["max"] for s in samples), 2))
            for size in (300000, 3000000):
                setup_stream(page, source, css, helpers)
                page.evaluate("""size => {
                  const sc=document.getElementById('sc'),unit='word 中文 abc '.repeat(8)+'\\n';
                  writeLlmStreamText(sc,unit.repeat(Math.ceil(size/unit.length)).slice(0,size),'reasoning');
                }""", size)
                page.wait_for_function("!document.getElementById('sc')._llmWindow.layoutJob", timeout=30000)
                result = page.evaluate("""() => {
                  window.measureSteps=[];
                  if(typeof createLlmStreamLayoutMeasurement==='function') {
                    const create=createLlmStreamLayoutMeasurement;
                    createLlmStreamLayoutMeasurement=(...args)=>{
                      const job=create(...args);if(!job)return job;
                      const advance=job.advance;
                      job.advance=(budget)=>{const t=performance.now();const result=advance(budget);
                        measureSteps.push(performance.now()-t);return result;};return job;
                    };
                  }
                  subject.style.width='600px';window.measureStart=performance.now();
                  refreshLlmStreamWindowGeometry(document.getElementById('sc'),true);
                  return {call_ms:performance.now()-measureStart};
                }""")
                page.wait_for_function("!document.getElementById('sc')._llmWindow.layoutJob", timeout=30000)
                result.update(page.evaluate("""() => ({
                  completion_ms:performance.now()-measureStart,
                  max_slice_ms:measureSteps.length?Math.max(...measureSteps):null
                })"""))
                output(version=version, scenario="remeasure", characters=size,
                       **{k: round(v, 2) if v is not None else None for k, v in result.items()})
            render_source = (directory / (Path(RENDER).name if version == "before" else RENDER)).read_text(encoding="utf-8")
            page.set_content(
                "<style>#chat-container{height:300px;overflow:auto}"
                ".process-aggregate-body{max-height:min(72vh,41.6rem);overflow:auto}</style>"
                "<div id='chat-container'>"
                + ("<div class='process-aggregate'><div class='process-aggregate-body'>"
                   + "<p>text for layout measurement</p>" * 20 + "</div></div>") * 200 + "</div>"
            )
            page.add_script_tag(content=render_source[
                render_source.index("function applyProcessBodyViewportClamp("):
                render_source.index("var processViewportClampScheduled")
            ])
            result = page.evaluate("""() => {
              const rows=document.querySelectorAll('.process-aggregate'),times=[];
              rows.forEach(row=>applyProcessBodyViewportClamp(row));
              for(let i=0;i<15;i++){const start=performance.now();
                rows.forEach(row=>applyProcessBodyViewportClamp(row));times.push(performance.now()-start);}
              times.sort((a,b)=>a-b);return {median_ms:times[7],max_ms:times[14]};
            }""")
            output(version=version, scenario="height_clamp", boxes=200,
                   **{k: round(v, 2) for k, v in result.items()})
        browser.close()


if __name__ == "__main__":
    main()
