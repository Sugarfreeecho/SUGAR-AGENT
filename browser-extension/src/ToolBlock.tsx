import React,{useLayoutEffect,useRef,useState} from 'react';
import {Icon,toolLabel} from './Icon';
import {ProcessElapsed} from './ProcessElapsed';
import {RichMarkdown} from './Markdown';
import {AttachmentImage} from './media';
import {toolOutput,outputCoveredByResult} from './tool-stream.mjs';
import {useNestedSmoothFollow} from './useSmoothFollow';

function inlineCommand(block:any) {
  const raw=String(block.commandText || '').trim();
  if(!raw)return '';
  const name=String(block.title || '');
  return name && raw.startsWith(name+'(') ? raw.slice(name.length) : raw;
}

export const ToolBlock=React.memo(function ToolBlock({block}:{block:any}) {
  const [open,setOpen]=useState(!!block.active);
  const scrolling=useNestedSmoothFollow(!!block.active,open),wasActive=useRef(!!block.active);
  useLayoutEffect(()=>{
    if(wasActive.current!==!!block.active){setOpen(!!block.active);wasActive.current=!!block.active;}
  },[block.active]);
  const output=toolOutput(block).replace(/^\s*实时输出\r?\n/,''),covered=outputCoveredByResult(block),command=inlineCommand(block);
  return <details className="process-block tool" data-tool-call-id={block.toolCallId} data-execution-id={block.executionId} open={open} onToggle={event=>setOpen(event.currentTarget.open)}>
    <summary><span className="chevron entry-chevron"><Icon name="chevron" size={12}/></span><span className="process-title">{toolLabel(block.title)}</span>{command && <span className="process-command" title={command}>{command}</span>}<span className="entry-meta secondary"><span className={block.active ? 'shimmer' : ''}>{block.status}</span><ProcessElapsed block={block}/></span></summary>
    <div ref={scrolling.ref} className="tool-scroll" onScroll={scrolling.onScroll} tabIndex={0}>
      {block.argsText ? <section className="tool-section tool-arguments"><strong>{block.argumentsCommitted ? '参数' : '参数草稿'}</strong><pre>{block.argsText}</pre></section> : block.statusCode==='generating' && <p className="secondary">正在生成参数…</p>}
      {output && (!block.hasResult || block.active && !covered) && <section className="tool-section tool-output"><strong>实时输出</strong><pre>{output}</pre></section>}
      {block.hasResult && <section className="tool-section tool-result"><strong>结果</strong>{block.active || block.format==='json' || block.title==='run_shell' ? <pre>{block.content}</pre> : <RichMarkdown text={block.content}/>}</section>}
      {output && block.hasResult && !block.active && !covered && <details className="tool-output-history"><summary>实时输出记录</summary><pre>{output}</pre></details>}
      {block.exitCode!==undefined && <p className="tool-exit-code">退出码：{block.exitCode}</p>}
      {block.images?.map((identity:string)=><AttachmentImage key={identity} identity={identity}/>)}
    </div>
  </details>;
});
