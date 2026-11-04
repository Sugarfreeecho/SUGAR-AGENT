import React,{useContext,useLayoutEffect,useRef} from 'react';
import {createSmoothFollowController} from 'virtual:sugaragent-smooth-follow';

const controller=createSmoothFollowController();
const floor=(node:HTMLElement)=>Math.max(0,node.scrollHeight-node.clientHeight);
const gap=(node:HTMLElement)=>floor(node)-node.scrollTop;
type Member={pause:()=>void;resume:()=>void;atBottom:()=>boolean};
export function createFollowGroup(){
  const members=new Set<Member>();
  return {blocked:false,entering:true,members,
    pause(){this.blocked=true;this.entering=false;members.forEach(member=>member.pause());},
    resume(force=false){if(!force && [...members].some(member=>!member.atBottom()))return;this.blocked=false;this.entering=false;members.forEach(member=>member.resume());},
    reset(){this.blocked=false;this.entering=true;members.forEach(member=>member.pause());},
  };
}
type Group=ReturnType<typeof createFollowGroup>;
export const ScrollFollowContext=React.createContext<Group|null>(null);
type Options={active:boolean;visible?:boolean;boundary?:string;group?:Group|null;root?:boolean;snapOnBoundary?:boolean;onChange?:(following:boolean)=>void};

export function useSmoothFollow<T extends HTMLElement=HTMLDivElement>(options:Options){
  const ref=useRef<T|null>(null),following=useRef(true),detached=useRef(false);
  const latest=useRef(options);latest.current=options;
  const state=useRef<{node:HTMLElement|null;boundary?:string;visible:boolean;active:boolean;lastTop:number;settle:number;cleanup?:()=>void;anchor?:{top:number;height:number}}>({node:null,visible:false,active:false,lastTop:0,settle:0});
  const actions=useRef<any>(null);
  if(!actions.current){
    const notify=(value:boolean)=>{if(following.current!==value){following.current=value;latest.current.onChange?.(value);}};
    const cancel=()=>{if(state.current.settle)cancelAnimationFrame(state.current.settle);state.current.settle=0;controller.cancel(state.current.node);};
    const pause=()=>{detached.current=true;notify(false);cancel();};
    const request=()=>{
      const node=state.current.node,opt=latest.current;
      if(!node || !node.isConnected || opt.visible===false || !following.current || opt.group?.blocked)return;
      // Restoring history (including late images and execution snapshots) is
      // an instant placement. Fresh generation or reader input ends this mode.
      if(opt.group?.entering){cancel();node.scrollTop=node.scrollHeight;state.current.lastTop=node.scrollTop;return;}
      if(matchMedia('(prefers-reduced-motion: reduce)').matches){cancel();node.scrollTop=node.scrollHeight;return;}
      controller.request(node,{onUnpin:()=>{pause();latest.current.group?.pause();}});
      if(!opt.active && !state.current.settle){
        const settle=()=>{state.current.settle=0;if(!following.current || !node.isConnected)return;
          if(gap(node)<=.25 || !controller.isFollowing(node)){controller.cancel(node);return;}
          state.current.settle=requestAnimationFrame(settle);
        };state.current.settle=requestAnimationFrame(settle);
      }
    };
    const resume=()=>{detached.current=false;notify(true);controller.clearReaderDetached(state.current.node);request();};
    const onScroll=()=>{
      const node=state.current.node;if(!node)return;
      const top=node.scrollTop,previous=state.current.lastTop;state.current.lastTop=top;
      if(controller.isOwnedScroll(node))return;
      if(gap(node)<=2){
        if(detached.current || latest.current.group?.blocked){detached.current=false;latest.current.group?.resume();if(!latest.current.group?.blocked)resume();}
        return;
      }
      if(top<previous-2 || controller.isReaderDetached(node) || gap(node)>48 && !controller.isFollowing(node) && !latest.current.group?.entering){
        pause();latest.current.group?.pause();
      }
    };
    actions.current={request,pause,resume,onScroll,cancel,
      toBottom(){latest.current.group?.resume(true);resume();},
      reset(){latest.current.group?.reset();cancel();detached.current=false;following.current=true;state.current.visible=false;},
      preserveViewport(){const node=state.current.node;if(!node)return;pause();latest.current.group?.pause();state.current.anchor={top:node.scrollTop,height:node.scrollHeight};},
    };
  }
  useLayoutEffect(()=>{
    const s=state.current,node=ref.current,opt=latest.current,visible=opt.visible!==false;
    const changed=s.node!==node || s.boundary!==opt.boundary;
    if(changed || !visible || s.active!==opt.active){s.cleanup?.();s.cleanup=undefined;}
    if(changed || !visible)actions.current.cancel();
    if(changed){s.node=node;s.boundary=opt.boundary;s.visible=false;detached.current=false;following.current=true;}
    if(!node || !visible){s.visible=false;return;}
    if(!s.cleanup){
      const group=opt.group;
      const member:Member={pause:actions.current.pause,resume:actions.current.resume,atBottom:()=>!node.isConnected || node.clientHeight===0 || gap(node)<=2};
      if(group && (opt.active || opt.root))group.members.add(member);
      const resized=()=>actions.current.request();
      const observer=new ResizeObserver(resized);observer.observe(node);
      const motion=matchMedia('(prefers-reduced-motion: reduce)');motion.addEventListener('change',resized);
      const content=node.querySelector(':scope > .reading-content');if(content)observer.observe(content);
      const selected=()=>{const selection=document.getSelection();if(selection?.toString() && selection.anchorNode && node.contains(selection.anchorNode)){actions.current.pause();group?.pause();}};
      document.addEventListener('selectionchange',selected);
      s.cleanup=()=>{observer.disconnect();motion.removeEventListener('change',resized);document.removeEventListener('selectionchange',selected);group?.members.delete(member);};
    }
    const entering=!s.visible;s.visible=true;
    if(s.anchor){const anchor=s.anchor;delete s.anchor;controller.cancel(node);node.scrollTop=anchor.top+node.scrollHeight-anchor.height;}
    else if(entering && opt.snapOnBoundary && !opt.group?.blocked){controller.reset(node);controller.snapToBottom(node);}
    else if(s.active && !opt.active && following.current && !opt.group?.blocked){actions.current.cancel();controller.snapToBottom(node);}
    s.active=opt.active;s.lastTop=node.scrollTop;
    actions.current.request();
  });
  useLayoutEffect(()=>()=>{state.current.cleanup?.();actions.current.cancel();},[]);
  return {ref,following,...actions.current} as {ref:React.MutableRefObject<T|null>;following:React.MutableRefObject<boolean>;onScroll:()=>void;toBottom:()=>void;reset:()=>void;preserveViewport:()=>void};
}

export function useNestedSmoothFollow<T extends HTMLElement=HTMLDivElement>(active:boolean,visible:boolean){
  const group=useContext(ScrollFollowContext);
  return useSmoothFollow<T>({active,visible,group});
}
