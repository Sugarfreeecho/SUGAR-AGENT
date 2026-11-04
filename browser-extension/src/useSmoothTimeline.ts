import {useLayoutEffect,useReducer,useRef,useState} from 'react';
import {computeSmoothRevealCount,takeSmoothTextPrefix} from 'virtual:sugaragent-smooth-follow';
import {createTimelineReveal} from './reveal-timeline.mjs';

export function useSmoothTimeline(timeline:any,boundary:string,suspended=false){
  const controller=useRef<ReturnType<typeof createTimelineReveal>>();
  if(!controller.current)controller.current=createTimelineReveal({computeSmoothRevealCount,takeSmoothTextPrefix});
  const [,render]=useReducer(value=>value+1,0);
  const [instant,setInstant]=useState(()=>document.hidden || matchMedia('(prefers-reduced-motion: reduce)').matches);
  const clock=useRef({frame:0,last:0});
  const displayed=controller.current.sync(timeline,{boundary,instant:instant || suspended});
  useLayoutEffect(()=>{
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    const update=()=>setInstant(document.hidden || motion.matches);
    document.addEventListener('visibilitychange',update);motion.addEventListener('change',update);
    return ()=>{document.removeEventListener('visibilitychange',update);motion.removeEventListener('change',update);
      cancelAnimationFrame(clock.current.frame);controller.current?.clear();};
  },[]);
  useLayoutEffect(()=>{
    const state=clock.current;
    if(!controller.current!.pending){cancelAnimationFrame(state.frame);state.frame=0;state.last=0;return;}
    if(!state.frame)state.frame=requestAnimationFrame(now=>{
      state.frame=0;
      controller.current!.advance(state.last?now-state.last:16.67);state.last=now;render();
    });
  });
  return displayed;
}
