import React,{useEffect,useRef,useState} from 'react';
import {Icon} from './Icon';

export function CopyButton({text}:{text:string}){
  const [status,setStatus]=useState<'idle'|'copying'|'success'|'error'>('idle');
  const epoch=useRef(0),timer=useRef<ReturnType<typeof setTimeout>>();
  useEffect(()=>{
    ++epoch.current;setStatus('idle');
    return ()=>{++epoch.current;clearTimeout(timer.current);};
  },[text]);
  async function copy(){
    const current=++epoch.current;
    clearTimeout(timer.current);setStatus('copying');
    let next:'success'|'error';
    try{await navigator.clipboard.writeText(text);next='success';}
    catch{next='error';}
    if(current!==epoch.current)return;
    setStatus(next);
    timer.current=setTimeout(()=>{if(current===epoch.current)setStatus('idle');},next==='success'?2000:4000);
  }
  const label=status==='success'?'已复制':status==='error'?'复制失败，请重试':status==='copying'?'正在复制…':'复制';
  return <button className={'copy-button '+status} title={label} aria-label={label} disabled={status==='copying'} onClick={()=>void copy()}>
    <Icon name={status==='success'?'check':status==='error'?'alert':'copy'} size={14}/><span aria-live="polite">{label}</span>
  </button>;
}
