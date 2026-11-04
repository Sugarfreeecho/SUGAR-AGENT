import React, {useEffect,useState} from 'react';
import {elapsedMilliseconds,formatElapsed} from './process-display.mjs';

export function ProcessElapsed({block,placeholder='—'}:{block:any;placeholder?:string}) {
  const [now,setNow]=useState(Date.now);
  useEffect(()=>{
    if(!block.timingActive)return;
    setNow(Date.now());
    const timer=setInterval(()=>setNow(Date.now()),200);
    return()=>clearInterval(timer);
  },[block.timingActive,block.startedAt]);
  const elapsed=elapsedMilliseconds(block,now);
  const text=elapsed===null ? placeholder : formatElapsed(elapsed);
  return text ? <span className="process-elapsed" data-timing-active={block.timingActive || undefined} title={elapsed===null ? undefined : '用时'}>{text}</span> : null;
}
