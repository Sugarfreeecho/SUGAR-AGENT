import React,{useCallback,useEffect,useRef,useState} from 'react';
import {extension} from './api';
import {Popover} from './Popover';
import {Icon} from './Icon';

export function useSubagentCatalog(sessionId:string,active:boolean,revision:number){
  const [snapshot,setSnapshot]=useState<any>(null),[error,setError]=useState('');
  const refreshRef=useRef<()=>Promise<void>>(async()=>{});
  useEffect(()=>{
    let disposed=false,inFlight=false,again=false;
    setSnapshot(null);setError('');
    async function read(){
      if(disposed || !active || !sessionId || document.hidden)return;
      if(inFlight){again=true;return;}
      inFlight=true;
      try{
        const result=await extension({type:'api',path:'/api/browser/v1/subagents',body:{session_id:sessionId}});
        if(result.session_id!==sessionId || !result.root?.id || !Array.isArray(result.entries))throw new Error('子 Agent 目录响应不完整，请重试。');
        if(!disposed){setSnapshot(result);setError('');}
      }catch(caught){if(!disposed)setError((caught as Error).message);}
      finally{inFlight=false;if(again && !disposed){again=false;void read();}}
    }
    refreshRef.current=read;void read();
    const timer=setInterval(()=>void read(),3000),visible=()=>void read();
    document.addEventListener('visibilitychange',visible);
    return()=>{disposed=true;clearInterval(timer);document.removeEventListener('visibilitychange',visible);};
  },[sessionId,active]);
  useEffect(()=>{const timer=setTimeout(()=>void refreshRef.current(),60);return()=>clearTimeout(timer);},[revision]);
  const refresh=useCallback(()=>refreshRef.current(),[]);
  return {data:snapshot?.session_id===sessionId?snapshot:null,error,refresh};
}

const statusLabel=(row:any)=>row.pending_human_count>0?'待处理':({running:'运行中',queued:'排队中',pending:'排队中',completed:'已完成',finished:'已完成',failed:'失败',interrupted:'已停止',cancelled:'已取消',orphaned:'已中断',unknown:'未运行'} as any)[row.status] || '未运行';
export function SubagentPicker({sessionId,catalog,busy,evidence,onSelect}:{sessionId:string;catalog:ReturnType<typeof useSubagentCatalog>;busy:boolean;evidence:boolean;onSelect:(id:string)=>Promise<void>}){
  const {data,error,refresh}=catalog;
  const [choosing,setChoosing]=useState(''),[actionError,setActionError]=useState('');
  useEffect(()=>setActionError(''),[sessionId]);
  if(!sessionId || !data?.parent && !data?.entries?.length && (!evidence || !!data))return null;
  const rows=data?.entries || [],running=rows.some((row:any)=>row.running),attention=rows.some((row:any)=>row.pending_human_count>0);
  async function choose(id:string,close=()=>{}){
    if(choosing)return;
    setChoosing(id);setActionError('');
    try{await onSelect(id);close();}catch(caught){setActionError((caught as Error).message);}finally{setChoosing('');}
  }
  return <>{data?.parent && <button type="button" className="subagent-back" title={'返回：'+data.parent.name} aria-label="返回父会话" disabled={busy || !!choosing} onClick={()=>void choose(data.parent.id)}><Icon name="chevron" size={14}/></button>}
    <Popover className="subagent-picker" label="子 Agent 会话" role="menu" placement="bottom" align="end" width={286} disabled={busy || !!choosing} onOpen={()=>void refresh()}
      trigger={<><span className={'subagent-dot'+(attention?' attention':running?' running':'')}/><span>子 Agent {rows.length}</span></>}>
      {close=><><div className="popover-heading">主／子会话</div>
        {data?.root && <button className="menu-item subagent-root" role="menuitem" disabled={busy || !!choosing} onClick={()=>void choose(data.root.id,close)}><Icon name="agents" size={14}/><span><small>主会话</small><strong>{data.root.name}</strong></span>{data.root.id===sessionId && <Icon name="check" size={12}/>}</button>}
        {!!rows.length && <div className="menu-divider"/>}<div className="menu-scroll subagent-options">{rows.map((row:any)=><button key={row.id} className={'menu-item subagent-row'+(row.id===sessionId?' selected':'')} role="menuitem" data-subagent-id={row.id} aria-current={row.id===sessionId?'page':undefined}
          title={row.selectable?row.name:'该任务没有独立会话，仅保留执行记录'} disabled={busy || !!choosing || !row.selectable} style={{paddingLeft:8+Math.min(4,Math.max(0,row.depth-1))*10}} onClick={()=>void choose(row.id,close)}>
          <span className={'subagent-dot'+(row.pending_human_count>0?' attention':row.running?' running':['failed','interrupted','orphaned'].includes(row.status)?' failed':'')}/><span className="subagent-name">{row.name}</span><small>{row.selectable?statusLabel(row):'仅记录'}</small>{row.id===sessionId && <Icon name="check" size={12}/>}</button>)}</div>
        {!rows.length && <p className="menu-note">{data?'暂无子 Agent 会话。':'正在读取子 Agent…'}</p>}
        {(actionError || error) && <div className="menu-error" role="alert">{actionError || error}<button onClick={()=>void refresh()}>重试</button></div>}
      </>}
    </Popover></>;
}
