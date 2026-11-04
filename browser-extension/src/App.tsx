import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {flushSync} from 'react-dom';
import {CopyButton} from './CopyButton';
import {useSmoothTimeline} from './useSmoothTimeline';
import {settleTimelineReveal} from './reveal-timeline.mjs';
import {groupConversationTurns} from './turn-groups.mjs';
import {turnKey,eventTurn,humanTurnKey} from './conversation-turns.mjs';
import {createUserBackfill} from './user-backfill.mjs';
import {replaySessionBuffer} from './session-hydration.mjs';
import {SendMode,SteerMode} from './SendModePicker';
import {PendingQueue,PendingMessage,ComposerDraft} from './PendingQueue';
import {mergePendingMessages,steerDelivery,pendingRecovery,reconcilePendingTurns} from './pending-messages.mjs';
import { RichMarkdown as Markdown } from './Markdown';
import { AttachmentImage, MediaSession, MessageImage } from './media';
import { usePreferences } from './preferences';
import { applyTimeline, buildUserMessage, initialTimeline, timelineFromHistory, prependTimeline, mergeLiveTurns, stageUserMessage, acknowledgeUserMessage, rejectUserMessage, stageSteerMessage, acknowledgeSteerMessage, rejectSteerMessage, mergeSteerSnapshot } from './timeline.mjs';
import { eventKey, loopbackUrl } from './shared.mjs';
import { Icon, toolLabel } from './Icon';
import { AttachmentMenu, SkillChoice } from './AttachmentMenu';
import {skillDisplayMessage} from './skill-selection.mjs';
import { extension, rpc } from './api';
import { ModelPicker } from './ModelPicker';
import { WorkspacePicker } from './WorkspacePicker';
import { PermissionPicker } from './PermissionPicker';
import { ContextMeter } from './ContextMeter';
import { HumanCard } from './HumanInteractions';
import { humanEvent, humanKey, mergeHumans } from './human.mjs';
import { mergeSessionMetadata, latestPermission } from './session-sync.mjs';
import { Popover } from './Popover';
import { Feedback } from './Feedback';
import { SessionPicker } from './SessionPicker';
import { SessionActions, Session } from './SessionActions';
import { Dialog } from './Dialog';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolBlock } from './ToolBlock';
import {executionSnapshotEvent} from './execution-recovery.mjs';
import { ProcessElapsed } from './ProcessElapsed';
import {clipboardFiles,mergeUploads} from './clipboard.mjs';
import { readBrowserContext } from './browser-context';
import {createFollowGroup,ScrollFollowContext,useSmoothFollow} from './useSmoothFollow';
import {installSidepanelPresence} from './presence.mjs';
import {isCurrentConnection} from './connection.mjs';
import {isSessionChatEvent,isSubagentNotice} from './session-scope.mjs';
import {SubagentPicker,useSubagentCatalog} from './SubagentPicker';
import {RunNotice} from './RunNotice';
import {useRunRecovery} from './useRunRecovery';
import {noteFrame,markCommitted,streamTrace} from './stream-diagnostics.mjs';
import './ui.css';
import './selected.css';

type PageContext = { title: string; url: string; text: string; capturedAt: string; tabId?: number };
type Upload = { id: string; name: string; size: number };

const noHumans:any[]=[];
type ProcessView={expanded:boolean;showHeading:boolean;hasProcess:boolean;status:string;transient:string;count:number;toggle:()=>void};
const Turn=React.memo(function Turn({ turn:sourceTurn, sessionId, humans, onHumanUpdate, onHumanRefresh, revealEpoch, processView }: { turn: any; sessionId: string; revealEpoch:number; humans:any[];onHumanUpdate:(record:any)=>void;onHumanRefresh:()=>void;processView:ProcessView }) {
  const turn=useSmoothTimeline({turns:[sourceTurn]},sessionId+':'+revealEpoch).turns[0];
  const {expanded}=processView;
  const groups: { answer?: string; blocks?: any[]; steer?: any }[] = [];
  for (const block of turn.process) {
    if(block.kind==='error')continue;
    if (block.kind === 'steer') groups.push({steer:block});
    else if (block.kind === 'answer' || block.kind === 'text') groups.push({ answer: block.content });
    else {
      if (!groups.at(-1)?.blocks) groups.push({ blocks: [] });
      groups.at(-1)!.blocks!.push(block);
    }
  }
  return <MediaSession.Provider value={sessionId}><article className="turn" data-run-id={turn.runId}>
    {turn.user && <div className="user-message"><Markdown text={turn.user} /></div>}
    {turn.pending && <div className="user-delivery">{turn.status === 'sending' ? '正在发送…' : '等待执行'}</div>}
    {!!turn.images?.length && <div className="message-images">{turn.images.map((identity: string) => <MessageImage key={identity} identity={identity} meta={turn.imageMeta?.[identity]} />)}</div>}
    {processView.showHeading && processView.hasProcess && <div className="process"><button className="process-heading" aria-expanded={expanded} onClick={processView.toggle}>
      <span className={expanded ? 'chevron open' : 'chevron'}><Icon name="chevron" size={14} /></span><span className={processView.status === 'running' ? 'shimmer' : ''}>{processView.status === 'running' ? processView.transient || '正在处理' : processView.status === 'failed' ? '执行失败' : processView.status === 'interrupted' ? '已停止' : processView.status === 'unknown' ? '执行状态未确认' : '查看执行过程'}</span><span className="process-count">{processView.count} 次操作</span>
    </button></div>}
    {!processView.hasProcess && turn.transient && <div className="status-line shimmer">{turn.transient}</div>}
    {groups.map((group, index) => group.steer ? <React.Fragment key={group.steer.id}><div className="user-message steer-message" data-steer-id={group.steer.steerId}><Markdown text={group.steer.content} />{group.steer.images?.map((identity:string)=><MessageImage key={identity} identity={identity} meta={group.steer.imageMeta?.[identity]}/>)}</div><div className="user-delivery">{group.steer.mode==='interrupt'?'打断插话 · 已采纳':'插话 · 已采纳'}</div></React.Fragment> : group.answer !== undefined ? <div className="answer" key={'answer-' + index}><Markdown text={group.answer} /></div> : expanded && <div className="process process-segment" key={'process-' + index}><div className="process-contents">{group.blocks!.map((block: any) => block.kind === 'status' ? <div key={block.id} className="status-line">{block.content}</div>
      : block.kind === 'reason' ? <ThinkingBlock key={block.id} block={block} />
      : block.kind === 'tool' ? <ToolBlock key={block.id} block={block}/>
      : <details key={block.id} className={`process-block ${block.kind}`} open={block.kind === 'error'}><summary><span className="chevron entry-chevron"><Icon name="chevron" size={12} /></span><span className="process-title">{toolLabel(block.title)}</span><span className="entry-meta secondary"><span>{block.status}</span><ProcessElapsed block={block} /></span></summary>{block.format === 'json' ? <pre>{block.content}</pre> : <Markdown text={block.content} />}{block.images?.map((identity: string) => <AttachmentImage key={identity} identity={identity} />)}</details>)}</div></div>)}
    {turn.body && <div className="answer streaming"><Markdown text={turn.body} /></div>}
    {turn.finalImages?.map((identity: string) => <AttachmentImage key={identity} identity={identity} />)}
    {turn.final && <div className="answer"><Markdown text={turn.final} /><div className="answer-actions"><CopyButton text={turn.final}/></div></div>}
    {turn.process.filter((block:any)=>block.kind==='error').map((block:any)=><RunNotice key={block.id} block={block}/>)}
    {humans.map(record=><HumanCard key={humanKey(record)+':'+(record.request_version || 1)} record={record} onUpdate={onHumanUpdate} onRefresh={onHumanRefresh}/>)}
  </article></MediaSession.Provider>;
});

const TurnGroup=React.memo(function TurnGroup({group,sessionId,revealEpoch,humansByRun,onHumanUpdate,onHumanRefresh}:{group:any;sessionId:string;revealEpoch:number;humansByRun:Map<string,any[]>;onHumanUpdate:(record:any)=>void;onHumanRefresh:()=>void}){
  const latest=group.turns.at(-1),status=latest.status;
  const [expanded,setExpanded]=useState(status!=='succeeded');
  useEffect(()=>setExpanded(status!=='succeeded'),[status]);
  const toggle=useCallback(()=>setExpanded(value=>!value),[]);
  const hasProcess=group.turns.some((turn:any)=>turn.process.some((block:any)=>!['answer','text','steer','error'].includes(block.kind)));
  const count=group.turns.reduce((sum:number,turn:any)=>sum+turn.process.filter((block:any)=>block.kind==='tool').length,0);
  const views=useMemo(()=>{
    return group.turns.map((_turn:any,index:number)=>({expanded,showHeading:index===0,hasProcess,status,transient:latest.transient,count,toggle}));
  },[group.turns.length,expanded,hasProcess,count,status,latest.transient,toggle]);
  return <section className="turn-group" data-process-group={group.processGroupId || undefined}>{group.turns.map((turn:any,index:number)=><Turn key={turnKey(turn)} turn={turn} sessionId={sessionId} revealEpoch={revealEpoch} humans={humansByRun.get(turnKey(turn)) || noHumans} onHumanUpdate={onHumanUpdate} onHumanRefresh={onHumanRefresh} processView={views[index]}/>)}</section>;
});

export function Sidebar() {
  const { preferences, update: updatePreferences } = usePreferences();
  const [connection, setConnection] = useState<any>({ status: 'connecting', baseUrl: 'http://127.0.0.1:8192' });
  const [view, updateView] = useState<'chat' | 'history' | 'settings'>(location.hash === '#settings' ? 'settings' : 'chat');
  const viewRef=useRef(view);viewRef.current=view;
  function setView(next:'chat'|'history'|'settings'){
    if(next!==viewRef.current)setTimeline((previous:any)=>settleTimelineReveal(previous));
    viewRef.current=next;updateView(next);
  }
  const [sessions, setSessions] = useState<Session[]>([]), [sessionId, setSessionId] = useState('');
  const [activeSession,setActiveSession]=useState<any>(null),[subagentRevision,setSubagentRevision]=useState(0),[childEvidence,setChildEvidence]=useState<Record<string,boolean>>({});
  const sessionRef = useRef('');
  const connectionFact=useRef<any>(null);
  const [timeline, setTimeline] = useState<any>(initialTimeline());
  const previousTurnGroups=useRef<any[]>([]);
  const turnGroups=useMemo(()=>{const groups=groupConversationTurns(timeline.turns,previousTurnGroups.current);previousTurnGroups.current=groups;return groups;},[timeline.turns]);
  const [revealEpoch,setRevealEpoch]=useState(0);
  const [draft, setDraft] = useState(''), [contexts, setContexts] = useState<PageContext[]>([]), [uploads, setUploads] = useState<Upload[]>([]);
  const [pendingMessages,setPendingMessages]=useState<PendingMessage[]>([]),[pendingModes,setPendingModes]=useState<Record<string,SteerMode>>({});
  const pendingRevision=useRef(0);
  const pendingFacts=useRef<any[]>([]);
  const recentPending=useRef(''),keyboardSubmission=useRef<{sessionId:string;epoch:number;immediate:boolean}|null>(null),pendingAction=useRef(false);
  useEffect(()=>{void chrome.storage.local.get('sugar.pendingModes').then(saved=>setPendingModes(saved['sugar.pendingModes'] || {}));},[]);
  function choosePendingMode(id:string,mode:SteerMode){setPendingModes(previous=>{const next={...previous,[id]:mode};void chrome.storage.local.set({'sugar.pendingModes':next});return next;});}
  const uploading = useRef(false), sending = useRef(false), pendingUploads = useRef(new Map<string,Upload[]>());
  const [skills,setSkills]=useState<SkillChoice[]>([]),[selectedSkills,setSelectedSkills]=useState<string[]>([]);
  const composerRef=useRef<any>(null);composerRef.current={text:draft,contexts,uploads,selectedSkills};
  const [skillsLoading,setSkillsLoading]=useState(false),[skillsError,setSkillsError]=useState('');
  const skillsRequest=useRef(0),skillDrafts=useRef(new Map<string,string[]>());
  function chooseSkills(names:string[]){skillDrafts.current.set(sessionRef.current,names);setSelectedSkills(names);}
  async function loadSkills(){
    const request=++skillsRequest.current;setSkillsLoading(true);setSkillsError('');
    try{const result=await extension({type:'api',path:'/api/browser/v1/skills'});if(request===skillsRequest.current)setSkills(result.skills || []);}
    catch(caught){if(request===skillsRequest.current){const message=(caught as Error).message;setSkillsError(/404|not found|尚未加载/i.test(message) ? '后端尚未加载 Skill 列表，请重启后端后重试。' : 'Skill 列表加载失败：'+message);}}
    finally{if(request===skillsRequest.current)setSkillsLoading(false);}
  }
  const [humans, setHumans] = useState<any[]>([]), [humanError, setHumanError] = useState(''), [models, setModels] = useState<any[]>([]), [modelId, setModelId] = useState('');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [loading, setLoading] = useState(false);
  const [repairing,setRepairing]=useState(false);
  const [diagnosticCopy,setDiagnosticCopy]=useState('复制同步诊断');
  useEffect(()=>markCommitted(),[timeline]);
  async function copyStreamDiagnostics(){
    try{
      const id=sessionRef.current,background=await extension({type:'stream-diagnostics',sessionId:id});
      await navigator.clipboard.writeText(JSON.stringify({version:chrome.runtime.getManifest().version,session_id:id,collected_at:new Date().toISOString(),sidebar:streamTrace(id),background},null,2));
      setDiagnosticCopy('已复制同步诊断');
    }catch(caught){setError('复制同步诊断失败：'+(caught as Error).message);}
  }
  const streamWatch=useRunRecovery(timeline,connection.status==='connected' && view==='chat' && !loading,setTimeline,setError,async id=>{
    if(id===sessionRef.current && !hydrating.current && viewRef.current==='chat')await selectSession(id,true,true);
  });
  const [modelsError, setModelsError] = useState(''), [modelsLoading, setModelsLoading] = useState(false), [modelSaving, setModelSaving] = useState(false), [creating, setCreating] = useState(false);
  const selectionEpoch = useRef(0), pendingSession = useRef(''), createPending = useRef<Promise<string> | null>(null), modelRef = useRef('');
  const [effort, setEffort] = useState(''), [workDir, setWorkDir] = useState('');
  const effortRef = useRef(''), workDirRef = useRef('');
  const [workspaces, setWorkspaces] = useState<{path: string; name: string}[]>([]), [workspaceLoading, setWorkspaceLoading] = useState(false), [workspaceError, setWorkspaceError] = useState('');
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [permissions, setPermissions] = useState<any>(null), [usage, setUsage] = useState<any>(null);
  const [stateLoading, setStateLoading] = useState(false), [stateError, setStateError] = useState(''), [usageError, setUsageError] = useState(''), [permissionSaving, setPermissionSaving] = useState(false), [stopping, setStopping] = useState(false);
  const stateEpoch = useRef(0), usageRevision = useRef(0), permissionRevision = useRef(0), permissionLive = useRef<any>(null);
  const sessionsRequest = useRef(0), metadataRevision = useRef(0);
  const [baseUrl, setBaseUrl] = useState('http://127.0.0.1:8192'), [pairCode, setPairCode] = useState('');
  const [search, setSearch] = useState(''), [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<Session | null>(null), [newName, setNewName] = useState(''), [deleting, setDeleting] = useState<Session | null>(null);
  const [sessionActionBusy, setSessionActionBusy] = useState(false), [dialogError, setDialogError] = useState('');
  const [tabPicker, setTabPicker] = useState<any[] | null>(null), [older, setOlder] = useState<number | null>(null), [unread, setUnread] = useState(false);
  const followGroup=useMemo(createFollowGroup,[]);
  const scrolling=useSmoothFollow({active:timeline.running,visible:connection.status==='connected' && view==='chat' && !loading,boundary:sessionId,group:followGroup,root:true,snapOnBoundary:true,onChange:value=>setUnread(!value && timeline.running)});
  const {ref:viewport,following:follow}=scrolling;
  const hydrating = useRef(false), buffer = useRef<any[]>([]), history = useRef<any[]>([]), loadedConnection = useRef(false), files = useRef<HTMLInputElement>(null);
  const current = sessions.find(session => session.id === sessionId) || (activeSession?.id===sessionId?activeSession:null);
  const subagentCatalog=useSubagentCatalog(sessionId,connection.status==='connected' && view==='chat',subagentRevision);
  const canWrite=current?.is_subagent?subagentCatalog.data?.parent_available===true:subagentCatalog.data?.parent_available!==false;
  const canWriteRef=useRef(canWrite);canWriteRef.current=canWrite;

  // A user event can be missed while the host connection or the history
  // snapshot is being replaced; retry that run's real message from history so
  // a live turn never renders as "generation without the question".
  const userBackfill=useRef<any>(null);
  if(!userBackfill.current)userBackfill.current=createUserBackfill({
    read:(id:string)=>rpc('session.history',{session_id:id,turns:4}),
    isCurrent:(id:string,epoch:number)=>sessionRef.current===id && selectionEpoch.current===epoch && !hydrating.current,
    apply:(fact:any,id:string,epoch:number)=>setTimeline((previous:any)=>{
      if(sessionRef.current!==id || selectionEpoch.current!==epoch)return previous;
      const turn=eventTurn(previous.turns,fact,String(fact.run_id || fact.turn_id || ''));
      if(!turn || turn.hasUserMessage || !turn.pendingUser && (turn.user || turn.images?.length))return previous;
      return applyTimeline(previous,fact,eventKey(fact,id) || 'backfill:'+id+':'+turn.runId,{history:true});
    }),
  });
  useEffect(() => {
    userBackfill.current.sync({sessionId,epoch:selectionEpoch.current,turns:timeline.turns,enabled:!loading && !hydrating.current && connection.status==='connected' && view==='chat'});
  }, [timeline, sessionId, loading,connection.status,view]);
  useEffect(()=>()=>userBackfill.current.dispose(),[]);

  const humanEpoch = useRef(0);
  const refreshHumans=useCallback(async (id = sessionRef.current) => {
    if (!id) { setHumans([]); setHumanError(''); return; }
    const epoch = ++humanEpoch.current;
    try {
      const result = await extension({type:'api',path:'/api/browser/v1/human/list',body:{session_id:id,include_descendants:false}});
      if (sessionRef.current === id && humanEpoch.current === epoch) {setHumans(previous=>mergeHumans(previous,(result.records || []).filter((record:any)=>record.session_id===id)));setHumanError('');}
    } catch (caught) { if (sessionRef.current === id && humanEpoch.current === epoch) setHumanError((caught as Error).message); }
  },[]);
  const updateHuman=useCallback((record:any)=>{setHumans(previous=>mergeHumans(previous,[record]));},[]);
  const humanOwners=useRef(new Map<string,string>());
  const humanTurnLayout=timeline.turns.map((turn:any)=>[turnKey(turn),turn.processGroupId,turn.userCreatedAt].join(':')).join('|');
  const humansByRun=useMemo(()=>{
    const groups=new Map<string,any[]>();
    for(const record of humans)if(record.session_id===sessionId && record.run_id){
      const saved=humanOwners.current.get(humanKey(record));
      const anchored=record.process_group_id && timeline.turns.some((turn:any)=>turn.runId===record.run_id && turn.processGroupId===record.process_group_id);
      const timed=Number.isFinite(Date.parse(record.created_at)) && timeline.turns.filter((turn:any)=>turn.runId===record.run_id).every((turn:any)=>Number.isFinite(Date.parse(turn.userCreatedAt)));
      const key=!anchored && !timed && saved && timeline.turns.some((turn:any)=>turnKey(turn)===saved)?saved:humanTurnKey(record,timeline.turns);
      if(!key)continue;
      humanOwners.current.set(humanKey(record),key);
      if(!groups.has(key))groups.set(key,[]);
      groups.get(key)!.push(record);
    }
    return groups;
  },[humans,sessionId,humanTurnLayout]);
  async function refreshSessions() {
    const epoch = ++sessionsRequest.current, revision = metadataRevision.current;
    const result = await rpc('session.list', { include_archived: true });
    if (sessionsRequest.current === epoch && metadataRevision.current === revision) setSessions(result.sessions || []);
    return result.sessions as Session[] || [];
  }
  async function selectSession(id: string, preserveComposer = false, streamRepair = false) {
    if (!id || typeof id !== 'string') throw new Error('会话标识无效，未打开会话');
    const epoch = ++selectionEpoch.current;
    humanOwners.current.clear();
    userBackfill.current.cancel();
    const previousId = sessionRef.current;
    const previousComposer=composerRef.current;
    let installed=false;
    if(!streamRepair){++pendingRevision.current;setPendingMessages([]);pendingFacts.current=[];recentPending.current='';keyboardSubmission.current=null;}
    pendingSession.current = id;setRepairing(streamRepair);setLoading(true);if(!streamRepair)setError('');
    ++stateEpoch.current; setStateLoading(false); if(!streamRepair){setUsage(null);setUsageError('');}
    if(!streamRepair){scrolling.reset();setUnread(false);}hydrating.current = true; buffer.current = [];
    try {
      if(previousId)await Promise.all([
        chrome.storage.local.set({['sugar.draft.'+previousId]:previousComposer.text}),
        chrome.storage.session.set({['sugar.composer.'+previousId]:{contexts:previousComposer.contexts,uploads:previousComposer.uploads,selectedSkills:previousComposer.selectedSkills}}),
      ]);
      if(selectionEpoch.current!==epoch)return;
      await extension({ type: 'subscribe', sessionId: id });
      const [result, info, local, temporary] = await Promise.all([
        rpc('session.history', { session_id: id, turns: streamRepair?Math.max(15,timeline.turns.filter((turn:any)=>turn.hasUserMessage).length):15 }), rpc('session.get', { session_id: id, include_runtime: true }),
        chrome.storage.local.get('sugar.draft.' + id), chrome.storage.session.get(['sugar.composer.' + id, 'sugar.pendingContext']),
      ]);
      if (selectionEpoch.current !== epoch) return;
      if (info.session?.id !== id) throw new Error('后端返回了不同的会话，未切换');
      streamWatch.snapshot(id,{...result,events:[...(result.events || []),...buffer.current]});
      noteFrame('history_installed',id,{type:'history',runtime_seq:result.last_runtime_seq},{reason:streamRepair?'automatic_repair':'selection',event_count:result.events?.length || 0});
      const saved = temporary['sugar.composer.' + id] || {};
      history.current = result.events || [];
      let next: any = timelineFromHistory(history.current, result.range_start || 0, id); next.running = !!info.session.stream_active;
      if(next.running && next.turns.at(-1)?.status==='history' && !next.turns.at(-1)?.final)next.turns.at(-1).status='running';
      const snapshotBuffer=buffer.current;
      for (const event of snapshotBuffer) next = applyTimeline(next, event, eventKey(event, id));
      buffer.current = [];
      next=settleTimelineReveal(next);
      sessionRef.current = id;installed=true; setSessionId(id);setActiveSession(info.session); if(!streamRepair)setView('chat');
      ++humanEpoch.current; setHumanError(''); setHumans(mergeHumans([], [...history.current, ...snapshotBuffer].filter(event=>isSessionChatEvent(event,id)).map(event=>humanEvent(event,id)).filter(Boolean)));
      if (!preserveComposer) {
        setDraft(local['sugar.draft.' + id] || '');
        setContexts([...(saved.contexts || []), ...(temporary['sugar.pendingContext'] ? [temporary['sugar.pendingContext']] : [])]);
        setUploads(saved.uploads || []);
        const selected=skillDrafts.current.get(id) ?? (Array.isArray(saved.selectedSkills) ? saved.selectedSkills.filter((name:any)=>typeof name==='string') : []);
        skillDrafts.current.set(id,selected);setSelectedSkills(selected);
      }
      setTimeline((previous: any) => preserveComposer ? mergeLiveTurns(next, previous) : next);
      setRevealEpoch(value=>value+1);
      modelRef.current = info.session.model_profile_id || ''; setModelId(modelRef.current);
      effortRef.current = info.session.reasoning_effort || ''; setEffort(effortRef.current);
      workDirRef.current = info.session.work_dir || ''; setWorkDir(workDirRef.current);
      setUsage(next.usage || null); setUsageError(''); void loadSessionState(id);
      setOlder(result.has_older ? result.range_start : null); void refreshHumans(id);
      await chrome.storage.local.set({ 'sugar.lastSession': id });
      await chrome.storage.session.remove('sugar.pendingContext');
    } catch (caught) {
      if (selectionEpoch.current === epoch) {
        setError((caught as Error).message);
        if (!installed && previousId && previousId !== id){
          // Drop B's events before switching the buffering owner back to A.
          buffer.current=[];pendingSession.current=previousId;
          await extension({ type: 'subscribe', sessionId: previousId }).catch(() => {});
        }
      }
    } finally {
      if (selectionEpoch.current === epoch) {
        // Events that arrived while the snapshot was being installed must not
        // disappear; apply them before accepting direct updates.
        const leftover = buffer.current; buffer.current = [];
        const owner=pendingSession.current;
        if (leftover.length) {
          setTimeline((previous:any)=>selectionEpoch.current===epoch?replaySessionBuffer(previous,leftover,owner,sessionRef.current):previous);
          if(owner===sessionRef.current){const cards=leftover.filter(event=>isSessionChatEvent(event,owner)).map(event=>humanEvent(event,owner)).filter(Boolean);if(cards.length)setHumans(previous=>selectionEpoch.current===epoch?mergeHumans(previous,cards):previous);}
        }
        pendingSession.current = ''; hydrating.current = false; setLoading(false);setRepairing(false);
        const pending=pendingUploads.current.get(sessionRef.current);
        if(pending?.length){setUploads(previous=>mergeUploads(previous,pending));pendingUploads.current.delete(sessionRef.current);}
      }
    }
  }
  async function navigateSubagent(id:string){
    await selectSession(id);
    if(sessionRef.current!==id)throw new Error('会话未能打开，请重试。');
  }
  function newSession(preserveComposer = false): Promise<string> {
    if (createPending.current) return createPending.current;
    const epoch = selectionEpoch.current;
    const stagedEffort = effortRef.current, stagedWorkspace = workDirRef.current;
    setCreating(true);
    const pending = (async () => {
      const result = await rpc('session.create', { name: '新会话', model_profile_id: modelRef.current, ...(stagedWorkspace ? { work_dir: stagedWorkspace } : {}) });
      if (!result.session_id || typeof result.session_id !== 'string') throw new Error('新建会话未成功，未切换会话');
      await refreshSessions();
      if (selectionEpoch.current !== epoch) throw new Error('创建期间已切换会话，未跳转到新会话');
      await selectSession(result.session_id, preserveComposer);
      if (sessionRef.current !== result.session_id) throw new Error('新会话未能打开，请从会话列表重试');
      if (stagedEffort) {
        await rpc('session.update', { session_id: result.session_id, reasoning_effort: stagedEffort });
        const info = await rpc('session.get', { session_id: result.session_id, include_runtime: true });
        if (info.session?.reasoning_effort !== stagedEffort) throw new Error('后端未保存思考强度，请重试');
        if (sessionRef.current === result.session_id) { effortRef.current = stagedEffort; setEffort(stagedEffort); }
      }
      return result.session_id as string;
    })();
    createPending.current = pending;
    void pending.finally(() => { if (createPending.current === pending) createPending.current = null; setCreating(false); }).catch(() => {});
    return pending;
  }
  async function loadModels() {
    setModelsLoading(true); setModelsError('');
    try { const result = await extension({ type: 'api', path: '/api/browser/v1/models' }); setModels(result.profiles || []); }
    catch (caught) { setModelsError('模型列表加载失败：' + (caught as Error).message); }
    finally { setModelsLoading(false); }
  }
  async function chooseModel(value: string) {
    if (loading || creating || modelSaving) return;
    const id = sessionRef.current;
    // An unsent conversation has no server identity yet. Model choice is local
    // until the user sends a message or explicitly creates a conversation.
    if (!id) { modelRef.current = value; setModelId(value); return; }
    const epoch = selectionEpoch.current;
    setModelSaving(true); setError('');
    try {
      await rpc('session.update', { session_id: id, model_profile_id: value });
      const result = await rpc('session.get', { session_id: id, include_runtime: true });
      if (result.session?.model_profile_id !== value) throw new Error('后端未保存模型选择，请重试');
      if (sessionRef.current === id && selectionEpoch.current === epoch) { modelRef.current = value; setModelId(value); setUsage(null); void loadSessionState(id); }
    } catch (caught) { if (sessionRef.current === id && selectionEpoch.current === epoch) setError((caught as Error).message); }
    finally { setModelSaving(false); }
  }
  async function chooseEffort(value: string) {
    if (loading || creating || modelSaving) return;
    const id = sessionRef.current;
    if (!id) { effortRef.current = value; setEffort(value); return; }
    const epoch = selectionEpoch.current; setModelSaving(true); setError('');
    try {
      await rpc('session.update', { session_id: id, reasoning_effort: value });
      const result = await rpc('session.get', { session_id: id, include_runtime: true });
      if ((result.session?.reasoning_effort || '') !== value) throw new Error('后端未保存思考强度，请重试');
      if (sessionRef.current === id && selectionEpoch.current === epoch) { effortRef.current = value; setEffort(value); }
    } catch (caught) { if (sessionRef.current === id && selectionEpoch.current === epoch) setError((caught as Error).message); }
    finally { setModelSaving(false); }
  }
  async function loadWorkspaces() {
    if (workspaceLoading) return;
    setWorkspaceLoading(true); setWorkspaceError('');
    try { const result = await extension({ type: 'api', path: '/api/browser/v1/workspaces' }); setWorkspaces(result.workspaces || []); }
    catch (caught) { setWorkspaceError((caught as Error).message); }
    finally { setWorkspaceLoading(false); }
  }
  async function chooseWorkspace(path: string, inline = false) {
    if (loading || creating || modelSaving || timeline.running) return false;
    setWorkspaceSaving(true); setWorkspaceError(''); setError('');
    const id = sessionRef.current, epoch = selectionEpoch.current;
    try {
      const validated = await extension({ type: 'api', path: '/api/browser/v1/workspaces/validate', body: { path } });
      if (id) {
        await rpc('session.update', { session_id: id, work_dir: validated.path });
        const result = await rpc('session.get', { session_id: id, include_runtime: true });
        if (result.session?.work_dir !== validated.path) throw new Error('后端未保存工作区，请重试');
      }
      if (sessionRef.current === id && selectionEpoch.current === epoch) { workDirRef.current = validated.path; setWorkDir(validated.path); }
      return true;
    } catch (caught) { setWorkspaceError((caught as Error).message); if (!inline) setError((caught as Error).message); return false; }
    finally { setWorkspaceSaving(false); }
  }
  async function browseWorkspace() {
    const target = sessionRef.current, epoch = selectionEpoch.current;
    setWorkspaceSaving(true); setWorkspaceError('');
    try {
      const result = await extension({ type: 'api', path: '/api/browser/v1/workspaces/pick', body: { initial: workDirRef.current, session_id: target } });
      if (!result.cancelled && result.path) {
        if (sessionRef.current !== target || selectionEpoch.current !== epoch) throw new Error('选择目录期间会话已切换，请重新选择目录');
        await chooseWorkspace(result.path);
      }
    } catch (caught) { setError((caught as Error).message); }
    finally { setWorkspaceSaving(false); }
  }
  async function loadSessionState(id = sessionRef.current) {
    const epoch = ++stateEpoch.current, revision = usageRevision.current, permissionAtStart = permissionRevision.current;
    setStateLoading(true); setStateError('');
    try {
      const result = await extension({ type: 'api', path: '/api/browser/v1/session-state', body: { session_id: id } });
      if (stateEpoch.current !== epoch || sessionRef.current !== id) return;
      setPermissions(permissionAtStart === permissionRevision.current ? result.permissions : latestPermission(result.permissions, permissionLive.current));
      if (usageRevision.current === revision) { setUsage(result.context_tokens); setUsageError(result.context_error || ''); }
    } catch (caught) { if (stateEpoch.current === epoch && sessionRef.current === id) { setStateError((caught as Error).message); setUsageError((caught as Error).message); } }
    finally { if (stateEpoch.current === epoch) setStateLoading(false); }
  }
  async function choosePermission(mode: string, confirmed = false) {
    if (permissionSaving) return false;
    const revision = permissionRevision.current;
    setPermissionSaving(true); setStateError('');
    try {
      const result = await extension({type:'api', path:'/api/browser/v1/permissions', body:{session_id:sessionRef.current, mode, confirmed_full_access:confirmed}});
      if (result.permissions?.mode !== mode) throw new Error('后端未保存权限模式，请重试');
      const selected = revision === permissionRevision.current ? result.permissions : latestPermission(result.permissions, permissionLive.current);
      ++stateEpoch.current; ++permissionRevision.current; setStateLoading(false);
      permissionLive.current = selected; setPermissions(selected); return true;
    } catch (caught) { setStateError((caught as Error).message); return false; }
    finally { setPermissionSaving(false); }
  }
  async function stop() {
    if (stopping || !sessionRef.current) return;
    setStopping(true); setError('');
    try { await rpc('session.interrupt', {session_id:sessionRef.current}); }
    catch (caught) { setError((caught as Error).message); }
    finally { setStopping(false); }
  }
  async function loadConnected() {
    void loadModels();
    void loadWorkspaces();
    const epoch = selectionEpoch.current;
    try {
      const [rows, local] = await Promise.all([refreshSessions(), chrome.storage.local.get('sugar.lastSession')]);
      if (selectionEpoch.current !== epoch) return;
      const last = sessionRef.current || local['sugar.lastSession'];
      const fallback=rows.find(row=>!row.archived)?.id;
      const id = last || fallback;
      if (id){await selectSession(id,id===sessionRef.current);if(sessionRef.current!==id && !sessionRef.current && fallback && fallback!==id)await selectSession(fallback);}
      else void loadSessionState('');
    } catch (caught) { setError((caught as Error).message); }
  }
  useEffect(() => {
    const firstChunks=new Set<string>();
    const handle = (message: any) => {
      if (message.type === 'connection') {
        if(!isCurrentConnection(connectionFact.current,message))return;
        connectionFact.current=message;
        setConnection((previous: any) => ({ ...previous, ...message }));
        if(message.baseUrl)setBaseUrl(message.baseUrl);
        if (message.status === 'connected' && !loadedConnection.current) { loadedConnection.current = true; void loadConnected(); }
        if (message.status !== 'connected') loadedConnection.current = false;
      } else if (message.type === 'session.metadata' && (message.session_id === sessionRef.current || message.session_id === pendingSession.current)) {
        ++metadataRevision.current;
        setSessions(previous => mergeSessionMetadata(previous,message));
        if(message.session_id===sessionRef.current && message.session)setActiveSession((previous:any)=>previous?.id===message.session_id?{...previous,...message.session}:previous);
        if (message.deleted && message.session_id === sessionRef.current) {
          skillDrafts.current.delete(message.session_id);setSelectedSkills([]);
          ++selectionEpoch.current; sessionRef.current='';pendingSession.current='';hydrating.current=false;buffer.current=[];
          setSessionId('');setTimeline(initialTimeline());setHumans([]);setLoading(false);setUsage(null);
          void extension({type:'subscribe',sessionId:''}).catch(()=>{});void loadSessionState('');
        }
      } else if (message.type === 'session.executions' && (message.session_id === sessionRef.current || message.session_id === pendingSession.current)) {
        for(const row of message.records || [])noteFrame('execution_snapshot',message.session_id,row);
        const events=(message.records || []).filter((row:any)=>isSessionChatEvent(row,message.session_id)).map(executionSnapshotEvent).filter(Boolean);
        streamWatch.restored(message.session_id,events);
        if(hydrating.current && message.session_id===pendingSession.current)buffer.current.push(...events);
        else if(!hydrating.current)setTimeline((previous:any)=>events.reduce((state:any,event:any)=>applyTimeline(state,event,'execution:'+message.session_id+':'+event.execution_id+':'+event.execution_runtime_seq),previous));
      } else if (message.type === 'session.event' && (message.session_id === sessionRef.current || message.session_id === pendingSession.current)) {
        noteFrame('sidebar_received',message.session_id,message.event);
        if(isSubagentNotice(message.event)){
          setChildEvidence(previous=>previous[message.session_id]?previous:{...previous,[message.session_id]:true});
          setSubagentRevision(value=>value+1);
        }
        if(!isSessionChatEvent(message.event,message.session_id)){noteFrame('scope_filtered',message.session_id,message.event,{reason:'session_ownership'});return;}
        streamWatch.event(message.session_id,message.event);
        if(!hydrating.current && !message.event.replayed_snapshot && !message.event.replayed_recent && ['run_started','user','llm_reasoning_delta','llm_response_delta','tool_call_delta','tool_command_delta'].includes(message.event.type))followGroup.entering=false;
        if (hydrating.current && message.session_id === pendingSession.current){buffer.current.push(message.event);noteFrame('buffered',message.session_id,message.event);}
        else if (!hydrating.current){
          const event=message.event,key=[message.session_id,event.run_id,event.stream_seq ?? event.react_iter ?? '',event.type].join(':');
          const first=['llm_reasoning_delta','llm_response_delta'].includes(event.type) && (event.delta || event.content_delta) && !event.replayed_snapshot && !event.replayed_recent && !firstChunks.has(key);
          const apply=()=>setTimeline((previous:any)=>{
            const key=eventKey(event,message.session_id),next=applyTimeline(previous,event,key,{reveal:viewRef.current==='chat'});
            const before=eventTurn(previous.turns,event,String(event.run_id || '')),after=eventTurn(next.turns,event,String(event.run_id || ''));
            noteFrame('reduced',message.session_id,event,{outcome:previous.seen.has(key)?'duplicate':next.turns===previous.turns?'ignored':'applied',status_before:before?.status,status_after:after?.status,running_before:previous.running,running_after:next.running});
            return next;
          });
          if(first){
            firstChunks.add(key);if(firstChunks.size>256)firstChunks.delete(firstChunks.values().next().value!);
            flushSync(apply);
          }else apply();
        }
        if (message.session_id === sessionRef.current && message.event.type === 'context_tokens') { ++usageRevision.current; setUsage(message.event.payload || message.event); setUsageError(''); }
        if (message.event.type === 'permission_mode_changed') {
          ++permissionRevision.current; permissionLive.current = latestPermission(permissionLive.current,message.event);
          setPermissions((previous: any) => latestPermission(previous,permissionLive.current));
        }
        const human=humanEvent(message.event,message.session_id);
        if(human && !hydrating.current) updateHuman(human);
        if(human || ['tool_approval_required','question_requested'].includes(message.event.type)) void refreshHumans(message.session_id);
        if (['run_finished', 'run_failed', 'run_interrupted'].includes(message.event.type)) { void refreshSessions().catch(() => {}); void loadSessionState(message.session_id); void refreshHumans(message.session_id); }
      } else if (message.type === 'session.error') setError(message.message);
      else if (message.type === 'context') { setContexts(previous => [...previous, message.value]); void chrome.storage.session.remove('sugar.pendingContext'); }
    };
    let active=true,port:chrome.runtime.Port | null=null,releasePresence=()=>{},timer:ReturnType<typeof setTimeout>;
    function attach(){
      if(!active)return;
      try{
        const next=chrome.runtime.connect({name:'sugaragent-sidepanel'});port=next;
        next.onMessage.addListener(message=>{if(active && port===next)handle(message);});
        const release=installSidepanelPresence(next);releasePresence=release;
        next.onDisconnect.addListener(()=>{
          release();if(!active || port!==next)return;
          loadedConnection.current=false;
          setConnection((previous:any)=>({...previous,status:'disconnected',error:'正在恢复扩展后台连接，配对已保留'}));
          timer=setTimeout(attach,500);
        });
        void extension({type:'state'}).then(state=>{if(active && port===next)handle({type:'connection',...state});}).catch(caught=>{if(active && port===next)setError(caught.message);});
      }catch{timer=setTimeout(attach,1000);}
    }
    attach();return()=>{active=false;clearTimeout(timer);releasePresence();port?.disconnect();};
  }, []);
  useEffect(() => {
    if (!sessionId || loading) return;
    const timer = setTimeout(() => { void chrome.storage.local.set({ ['sugar.draft.' + sessionId]: draft }); }, 300);
    return () => clearTimeout(timer);
  }, [draft, sessionId, loading]);
  useEffect(() => {
    if (sessionId && !loading) void chrome.storage.session.set({ ['sugar.composer.' + sessionId]: { contexts, uploads, selectedSkills } });
  }, [contexts, uploads, selectedSkills, sessionId, loading]);
  useEffect(()=>{if(pendingMessages.length || pendingFacts.current.length)setTimeline((previous:any)=>reconcilePendingTurns(previous,[...pendingMessages,...pendingFacts.current]));},[pendingMessages,timeline.turns]);
  const hasPendingSteers=!!pendingMessages.length || !!timeline.pendingSteers?.some((item:any)=>['sending','queued','claimed','interrupting','restarting','deferred'].includes(item.status));
  useEffect(()=>{
    if(!sessionId || loading || connection.status!=='connected' || view!=='chat')return;
    let cancelled=false,timer:ReturnType<typeof setTimeout>;
    const epoch=selectionEpoch.current;
    async function sync(){
      try{
        const revision=pendingRevision.current;
        const result=await extension({type:'api',path:'/api/browser/v1/steers',body:{session_id:sessionId}});
        const recoveries:PendingMessage[]=[];for(const row of await pendingRecovery(sessionId)){try{const op=await rpc('operation.get',{id:row.operationId});if(['queued','cancelled'].includes(op.status))recoveries.push(row);else await pendingRecovery(sessionId,row,true);}catch{recoveries.push(row);}}
        if(!cancelled && sessionRef.current===sessionId && selectionEpoch.current===epoch){
          pendingFacts.current=result.started_pending || [];
          setTimeline((previous:any)=>reconcilePendingTurns(mergeSteerSnapshot(previous,result.items || []),pendingFacts.current));
          if(revision===pendingRevision.current)setPendingMessages(previous=>mergePendingMessages([...previous.filter(row=>!row.recovery),...recoveries],result.pending || []));
        }
      }catch(caught){if(!cancelled)setError('插话状态同步失败：'+(caught as Error).message);}
      if(!cancelled && (timeline.running || hasPendingSteers))timer=setTimeout(sync,1500);
    }
    void sync();return()=>{cancelled=true;clearTimeout(timer);};
  },[sessionId,loading,connection.status,view,timeline.running,hasPendingSteers]);

  async function send(override?:ComposerDraft,forcedMode?:SendMode,key?:string,editOperationId?:string) {
    const snapshot=override || {text:draft,contexts:[...contexts],uploads:[...uploads],selectedSkills:[...selectedSkills]};
    if (!canWriteRef.current || (!snapshot.text.trim() && !snapshot.contexts.length && !snapshot.uploads.length && !snapshot.selectedSkills.length) || sending.current || busy || stopping || uploading.current || loading || creating || modelSaving || workspaceSaving) return false;
    sending.current=true;setBusy(true);setError('');
    const mode=forcedMode || (timeline.running?'pending':'queue');
    const asPending=mode==='pending',asSteer=mode==='append' || mode==='interrupt';
    const text=snapshot.text,pages=[...snapshot.contexts],attachments=[...snapshot.uploads],selected=[...snapshot.selectedSkills];
    const uiMessage=text || (selected.length?'使用所选 Skill':'附加资料');
    const clientId=key || 'send-'+crypto.randomUUID();
    const automatic=snapshot.automatic ?? (preferences.autoPageContext!==false && !connection.paused);
    const pageContext=snapshot.browser_context!==undefined?Promise.resolve(snapshot.browser_context):automatic?chrome.windows.getCurrent().then(window=>readBrowserContext({windowId:window.id})).catch(()=>({page:null,status:'unavailable'})):Promise.resolve(null);
    let id=sessionRef.current;
    if(asPending)++pendingRevision.current;
    if(asPending && !editOperationId){setPendingMessages(previous=>[...previous.filter(row=>row.clientId!==clientId),{clientId,content:skillDisplayMessage(uiMessage,selected),status:'sending',draft:snapshot}]);}
    else if(!asPending)setTimeline((previous:any)=>asSteer?stageSteerMessage(previous,clientId,skillDisplayMessage(uiMessage,selected),mode):stageUserMessage(previous,clientId,skillDisplayMessage(uiMessage,selected)));
    scrolling.toBottom();
    try{
      id ||= await newSession(true);
      const receipt=await extension({type:'api',path:'/api/browser/v1/messages',body:{session_id:id,message:buildUserMessage(text || (selected.length?'请按所选 Skill 开始处理。':'请处理附加的资料。'),pages),ui_message:uiMessage,...(selected.length?{selected_skills:selected}:{}),mode,automatic,browser_context:await pageContext,idempotency_key:clientId,...(editOperationId?{edit_operation_id:editOperationId}:{}),...(asPending?{composer:{text,contexts:pages}}:{}),...(attachments.length?{attachments:attachments.map(item=>({id:item.id}))}:{})}});
      if(receipt.accepted===false || receipt.error)throw new Error(receipt.error?.message || '消息未被接收，请重试。');
      if(sessionRef.current===id){
        if(asPending){++pendingRevision.current;setPendingMessages(previous=>previous.map(row=>row.clientId===clientId || row.operationId===editOperationId?{...row,content:skillDisplayMessage(uiMessage,selected),draft:snapshot,...receipt.pending_item,operationId:receipt.operation_id,runId:receipt.run_id,status:'queued'}:row));}
        else setTimeline((previous:any)=>(asSteer?acknowledgeSteerMessage:acknowledgeUserMessage)(previous,clientId,receipt));
      }
      if(!override){
        skillDrafts.current.set(id,[]);
        if(sessionRef.current===id){setDraft('');setContexts([]);setUploads([]);setSelectedSkills([]);}
        const composerKey='sugar.composer.'+id,saved=(await chrome.storage.session.get(composerKey).catch(()=>({} as Record<string,any>)))[composerKey] || {};
        await chrome.storage.session.set({[composerKey]:{...saved,selectedSkills:[]}}).catch(()=>{});
        await chrome.storage.local.remove('sugar.draft.'+id);
      }
      return asPending?{clientId,content:skillDisplayMessage(uiMessage,selected),draft:snapshot,...receipt.pending_item,operationId:receipt.operation_id,runId:receipt.run_id,status:'queued'} as PendingMessage:true;
    }catch(caught){
      if(asPending){++pendingRevision.current;setPendingMessages(previous=>previous.filter(row=>row.clientId!==clientId));}
      else setTimeline((previous:any)=>(asSteer?rejectSteerMessage:rejectUserMessage)(previous,clientId));
      if(!override && sessionRef.current===id){setDraft(text);setContexts(pages);setUploads(attachments);chooseSkills(selected);}
      setError((caught as Error).message);if(override)throw caught;return false;
    }finally{sending.current=false;setBusy(false);}
  }
  async function withdrawPending(item:PendingMessage,preserveRecovery=false){
    const target=sessionRef.current,epoch=selectionEpoch.current;
    ++pendingRevision.current;
    await extension({type:'api',path:'/api/browser/v1/pending/cancel',body:{session_id:target,operation_id:item.operationId}});
    if(sessionRef.current!==target || selectionEpoch.current!==epoch)throw new Error('会话已切换，待发操作已结束');
    ++pendingRevision.current;setPendingMessages(previous=>previous.filter(row=>row.operationId!==item.operationId));
    if(!preserveRecovery)await pendingRecovery(target,item,true);
  }
  async function editPending(item:PendingMessage,snapshot:ComposerDraft,key:string){
    const target=sessionRef.current;
    if(item.recovery)await withdrawPending(item,true);
    if(!await send(snapshot,'pending',key,item.recovery?undefined:item.operationId))throw new Error('当前暂不能提交，编辑内容已保留');
    await pendingRecovery(target,item,true);
  }
  async function dispatchPending(item:PendingMessage,mode:SteerMode=pendingModes[item.operationId!] || 'append'){
    if(pendingAction.current)return;
    pendingAction.current=true;
    const target=sessionRef.current;
    mode=item.recoveryMode || mode;
    const recovery={...item,recovery:true,recoveryMode:mode,status:'recovery'};
    try{
      await pendingRecovery(target,recovery);
      await withdrawPending(item,true);
      if(!await send(item.draft,mode,'pending-steer-'+item.operationId))throw new Error('当前暂不能插话');
      await pendingRecovery(target,item,true);
    }catch(caught){
      try{const state=await rpc('operation.get',{id:item.operationId});if(!['queued','cancelled'].includes(state.status)){await pendingRecovery(target,item,true);throw caught;}}
      catch(error){if(error===caught)throw caught;}
      if(sessionRef.current===target){++pendingRevision.current;setPendingMessages(previous=>[...previous.filter(row=>row.operationId!==item.operationId),recovery]);}
      throw caught;
    }finally{pendingAction.current=false;}
  }
  async function submitComposer(){
    // Match the main UI: input -> Pending; empty input -> the most recently
    // queued item (or first waiting item). A rapid second Enter is remembered
    // until admission finishes, instead of sending the text twice.
    if(keyboardSubmission.current){keyboardSubmission.current.immediate=true;return;}
    if(pendingAction.current)return;
    const hasDraft=draft.trim() || contexts.length || uploads.length || selectedSkills.length;
    if(!hasDraft){
      const waiting=pendingMessages.filter(item=>item.operationId && !item.recovery && (!item.runId || !timeline.turns.some((turn:any)=>turn.runId===item.runId)));
      const item=waiting.find(item=>item.operationId===recentPending.current) || waiting[0];
      if(item)try{await dispatchPending(item);}catch(caught){setError((caught as Error).message);}
      return;
    }
    const ticket={sessionId:sessionRef.current,epoch:selectionEpoch.current,immediate:false};keyboardSubmission.current=ticket;
    try{
      const accepted=await send();
      if(accepted && typeof accepted==='object'){
        recentPending.current=accepted.operationId!;
        if(ticket.immediate && ticket.sessionId===sessionRef.current && ticket.epoch===selectionEpoch.current)await dispatchPending(accepted);
      }
    }catch(caught){setError((caught as Error).message);}
    finally{if(keyboardSubmission.current===ticket)keyboardSubmission.current=null;}
  }
  async function attachPage(tabId?: number, selectionOnly = false) {
    try { const value = await extension({ type: 'capture', tabId, selectionOnly }); setContexts(previous => [...previous, value]); setTabPicker(null); }
    catch (caught) { setError((caught as Error).message); }
  }
  function pasteIntoComposer(event:React.ClipboardEvent<HTMLTextAreaElement>) {
    const incoming=clipboardFiles(event.clipboardData);
    if(!incoming.length)return;
    event.preventDefault();
    const text=event.clipboardData.getData('text/plain');
    if(text){
      const input=event.currentTarget,start=input.selectionStart,end=input.selectionEnd;
      setDraft(input.value.slice(0,start)+text+input.value.slice(end));
      requestAnimationFrame(()=>{if(input.isConnected)input.setSelectionRange(start+text.length,start+text.length);});
    }
    void uploadFiles(incoming);
  }
  async function uploadFiles(list: FileList | File[] | null) {
    if (!list?.length)return;
    if(uploading.current || busy){setError('正在处理附件或发送消息，请稍候再粘贴。');return;}
    if(loading || creating || modelSaving || workspaceSaving){setError('正在切换或保存会话，请完成后再附加文件。');return;}
    if(list.length>32){setError('一次最多附加 32 个文件。');return;}
    uploading.current=true;setBusy(true);setError('');
    try {
      const id = sessionRef.current || await newSession(true);
      const settings = (await chrome.storage.local.get('sugar.connection'))['sugar.connection'];
      const url = loopbackUrl(settings.baseUrl); url.pathname = '/api/browser/v1/uploads'; url.searchParams.set('session_id', id);
      const body = new FormData(); for (const file of Array.from(list)) body.append('files', file);
      const response = await fetch(url.href, { method: 'POST', headers: { Authorization: 'Bearer ' + settings.token }, body });
      const result = await response.json(); if (!response.ok) throw new Error(result.detail || result.error || '上传失败');
      if(!Array.isArray(result.files) || result.files.some((item:any)=>!item?.id || !item.name))throw new Error('上传未返回有效附件，请重试。');
      pendingUploads.current.set(id,mergeUploads(pendingUploads.current.get(id) || [],result.files));
      const key='sugar.composer.'+id,saved=(await chrome.storage.session.get(key))[key] || {};
      await chrome.storage.session.set({[key]:{...saved,uploads:mergeUploads(saved.uploads || [],result.files)}});
      if(sessionRef.current===id && !hydrating.current){
        const pending=pendingUploads.current.get(id) || [];
        setUploads(previous=>mergeUploads(previous,pending));pendingUploads.current.delete(id);
      }
    } catch (caught) { setError((caught as Error).message); } finally { uploading.current=false;setBusy(false); if (files.current) files.current.value = ''; }
  }
  async function updateSession(session: Session, method: string, extra: object = {}) {
    if (sessionActionBusy) return false;
    setSessionActionBusy(true); setDialogError('');
    try { await rpc(method, { session_id: session.id, ...extra }); await refreshSessions(); if (method === 'session.delete' && sessionRef.current === session.id) { skillDrafts.current.delete(session.id); setSelectedSkills([]); sessionRef.current = ''; setSessionId(''); setTimeline(initialTimeline()); ++stateEpoch.current; setStateLoading(false); setUsage(null); setUsageError(''); setPermissions((previous: any) => previous ? {...previous, can_change:false} : null); ++humanEpoch.current; setHumans([]); setHumanError(''); } return true; }
    catch (caught) { if (editing || deleting) setDialogError((caught as Error).message); else setError((caught as Error).message); return false; }
    finally { setSessionActionBusy(false); }
  }
  async function loadOlder() {
    if (older === null || !sessionId) return;
    try {
      const id=sessionId,epoch=selectionEpoch.current;
      const result = await rpc('session.history', { session_id: id, turns: 15, before_index: older });
      if(sessionRef.current!==id || selectionEpoch.current!==epoch)return;
      scrolling.preserveViewport();
      setTimeline((previous: any) => prependTimeline(previous, timelineFromHistory(result.events, result.range_start, sessionId))); setOlder(result.has_older ? result.range_start : null);
    } catch (caught) { setError((caught as Error).message); }
  }
  const connected = connection.status === 'connected';
  const needsPairing=connection.status==='unpaired' || connection.status==='auth-required';
  const noticeError=error || modelsError || (needsPairing || view==='settings' ? connection.error : '');
  const unavailable = !connected || loading || creating || modelSaving || workspaceSaving;
  const hasInput=!!(draft.trim() || contexts.length || uploads.length || selectedSkills.length);
  const stopAction=timeline.running && (!hasInput || !canWrite);
  const sendLabel=stopAction ? '停止任务' : timeline.running ? '加入待发队列' : '发送';
  const recent = sessions.filter(session => !session.archived && session.id !== sessionId).slice(0, 2);
  const dismissError = () => { setError(''); setModelsError(''); };
  const beginRename = (session: Session) => { setDialogError(''); setEditing(session); setNewName(session.name || ''); };
  const beginDelete = (session: Session) => { setDialogError(''); setDeleting(session); };
  return <main className="app" data-design="selected-m"><header className="topbar"><img className="topbar-brand" src={chrome.runtime.getURL('icon.png')} alt="SugarAgent" /><SessionPicker title={current?.name || '新会话'} value={sessionId} sessions={sessions} onOpen={() => void refreshSessions().catch(caught => setError(caught.message))} onSelect={selectSession} onManage={() => setView('history')} busy={sessionActionBusy} onRename={beginRename} onDelete={beginDelete} onUpdate={updateSession} />{view==='chat' && <SubagentPicker sessionId={sessionId} catalog={subagentCatalog} busy={loading || busy || creating} evidence={!!childEvidence[sessionId] || !!current?.is_subagent} onSelect={navigateSubagent}/>}<nav><button title="新会话" onClick={() => void newSession().catch(caught => setError(caught.message))} disabled={!connected || unavailable || busy}><Icon name="edit" size={17} /></button>
    <Popover className="header-more" label="更多操作" placement="bottom" align="end" trigger={<Icon name="more" size={17} />}>{close => <><div className="popover-heading">设置</div><div className="quick-setting"><span>主题</span><div className="theme-options">{(['light', 'dark', 'purple'] as const).map((theme, index) => <button key={theme} aria-pressed={preferences.theme === theme} onClick={() => updatePreferences({ theme })}>{['浅色', '深色', '紫色'][index]}</button>)}</div></div><div className="quick-setting"><span>本机服务</span><span className="server-address" title={baseUrl}>{baseUrl}</span></div><div className="menu-divider" /><button className="menu-item" disabled={!connected} onClick={() => { close(); void extension({ type: 'pause', paused: !connection.paused }).catch(caught => setError(caught.message)); }}><Icon name="stop" size={15} />{connection.paused ? '恢复控制' : '暂停控制'}</button><button className="menu-item" onClick={() => { close(); setView('history'); void refreshSessions().catch(caught => setError(caught.message)); }}><Icon name="history" size={15} />会话历史</button><button className="menu-item" onClick={() => { close(); setView('settings'); }}><Icon name="settings" size={15} />设置</button><button className="menu-item" onClick={() => { close(); void chrome.tabs.create({ url: baseUrl }); }}><Icon name="external" size={15} />打开主程序</button></>}</Popover></nav></header>
    {noticeError && (!connected || view !== 'chat') && <div className="error-banner" role="alert"><span>{noticeError}</span>{modelsError && <button disabled={modelsLoading} onClick={() => void loadModels()}>重试加载模型</button>}<button onClick={dismissError} aria-label="关闭提示">×</button></div>}
    {!connected && !needsPairing && view!=='settings' && <div className="connection-recovery" role="status"><span>{connection.error || '正在连接本机服务，配对信息会自动恢复'}</span><button onClick={()=>void extension({type:'reconnect'}).catch(caught=>setError(caught.message))}>重试连接</button><button title="连接设置" onClick={()=>setView('settings')}><Icon name="settings" size={14}/></button></div>}
    {(needsPairing || view === 'settings') ? <section className="settings view"><div className="view-heading"><h1>{connected ? '设置' : '连接 SugarAgent'}</h1>{!needsPairing && <button onClick={() => setView('chat')}>返回</button>}</div><p className="secondary">连接本机 Agent，在这里继续会话，并使用已登录的网页完成任务。</p><div className="connection-guide"><span className="guide-index">01</span><div><strong>先在主程序完成准备</strong><p>按步骤加载扩展、生成配对码。</p><button onClick={() => void chrome.tabs.create({ url: baseUrl + '/plugins/browser-use' })}>打开连接向导 <Icon name="external" size={13} /></button></div></div><div className="guide-form-label"><span className="guide-index">02</span><strong>填入地址，完成配对</strong></div>
      <form onSubmit={event => { event.preventDefault(); setBusy(true); void extension({ type: 'pair', baseUrl, code: pairCode }).then(() => { setPairCode(''); setView('chat'); }).catch(caught => setError(caught.message)).finally(() => setBusy(false)); }}><label>服务地址<input value={baseUrl} onChange={event => setBaseUrl(event.target.value)} placeholder="http://127.0.0.1:8192" /></label><label>一次性配对码<input value={pairCode} onChange={event => setPairCode(event.target.value)} autoComplete="off" placeholder="在主程序的浏览器连接设置中生成" /></label><button className="primary" disabled={busy || !pairCode.trim()}>配对并连接</button></form>
      <button onClick={() => void chrome.tabs.create({ url: baseUrl + '/settings?section=plugin%3Abrowser-use%3Abrowser' })}>打开主程序设置 ↗</button><div className="setting-row"><label>语言<select data-pref-language value={preferences.language} onChange={event => updatePreferences({ language: event.target.value as 'auto' | 'zh-CN' | 'en' })}><option value="auto">跟随浏览器</option><option value="zh-CN">中文</option><option value="en">English</option></select></label><label>主题<select data-pref-theme value={preferences.theme} onChange={event => updatePreferences({ theme: event.target.value as 'system' | 'light' | 'purple' | 'dark' })}><option value="system">跟随系统</option><option value="light">浅色</option><option value="purple">紫色</option><option value="dark">深色</option></select></label></div><div className="setting-row"><label className="auto-page-label"><span>自动关联当前网页</span><input type="checkbox" data-pref-auto-page checked={preferences.autoPageContext !== false} onChange={event => updatePreferences({autoPageContext:event.target.checked})} /></label></div><div className="setting-row"><span>浏览器控制</span><button disabled={!connected} onClick={() => void extension({ type: 'pause', paused: !connection.paused }).catch(caught => setError(caught.message))}>{connection.paused ? '恢复控制' : '暂停控制'}</button></div><div className="setting-row"><span>连接状态</span><span className="secondary">{connection.status}</span></div><button onClick={() => void extension({ type: 'reconnect' })}>重新连接</button><button onClick={() => void extension({ type: 'disconnect' })}>清除本机配对</button>
      <div className="setting-row"><span>当前版本</span><span className="secondary" data-extension-version>v{chrome.runtime.getManifest().version}</span></div>
      <div className="setting-row"><span>会话同步</span><button onClick={()=>void copyStreamDiagnostics()}>{diagnosticCopy}</button></div>
    </section> : view === 'history' ? <section className="history view"><div className="view-heading"><h1>会话</h1><button onClick={() => setView('chat')}>返回</button></div><input className="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索会话标题" /><label className="checkbox"><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} />显示已归档</label>
      {sessions.filter(session => (showArchived || !session.archived) && (session.name || '').toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned)).map(session => <div key={session.id} className={'history-item' + (session.id === sessionId ? ' selected' : '')}><button className="history-open" onClick={() => void selectSession(session.id)}><strong>{session.pinned ? '· ' : ''}{session.name || '未命名会话'}</strong><small>{session.archived ? '已归档 · ' : ''}{session.updated_at ? new Date(session.updated_at).toLocaleString() : ''}</small></button><SessionActions session={session} busy={sessionActionBusy} onRename={beginRename} onDelete={beginDelete} onUpdate={updateSession} /></div>)}
    </section> : <><div className="reading" ref={viewport} onScroll={scrolling.onScroll} tabIndex={0} aria-label="会话内容"><ScrollFollowContext.Provider value={followGroup}><div className="reading-content">
      {older !== null && <button className="older" onClick={() => void loadOlder()}>加载更早的对话</button>}{loading && !repairing && !timeline.turns.some((turn: any) => turn.pending) ? <p className="secondary">正在读取会话…</p> : !timeline.turns.length ? <div className="welcome"><img className="welcome-brand" src={chrome.runtime.getURL('icon.png')} alt="SugarAgent" /><div className="recent-sessions"><div className="recent-caption">继续最近的会话</div>{recent.map(session => <button key={session.id} onClick={() => void selectSession(session.id)}><Icon name="history" size={14} /><span>{session.name || '未命名会话'}</span><Icon name="chevron" size={12} /></button>)}{!recent.length && <p className="secondary">输入消息，开始新会话。</p>}</div></div> : turnGroups.map((group:any)=><TurnGroup key={sessionId+':'+group.id} group={group} sessionId={sessionId} revealEpoch={revealEpoch} humansByRun={humansByRun} onHumanUpdate={updateHuman} onHumanRefresh={refreshHumans}/>)}{(timeline.pendingSteers || []).map((item:any)=><MediaSession.Provider value={sessionId} key={item.clientId || item.steerId}><article className="turn pending-steer"><div className="user-message"><Markdown text={item.content}/></div>{!!item.images?.length && <div className="message-images">{item.images.map((identity:string)=><MessageImage key={identity} identity={identity} meta={item.imageMeta?.[identity]}/>)}</div>}<div className="user-delivery" role="status">{steerDelivery(item,timeline.running)}</div></article></MediaSession.Provider>)}{humans.filter(record=>record.session_id===sessionId && (record.status==='pending' || record._sidebarHandled || !record.run_id) && !(record.run_id && timeline.turns.some((turn:any)=>turn.runId===record.run_id))).map(record=><HumanCard key={humanKey(record)+':'+(record.request_version || 1)} record={record} onUpdate={updateHuman} onRefresh={()=>void refreshHumans()} />)}{humanError && <div className="human-load-error" role="alert">{humanError}<button onClick={()=>void refreshHumans()}>重新加载交互卡片</button></div>}</div></ScrollFollowContext.Provider></div>
      {unread && !follow.current && <button className="jump-bottom" onClick={() => { scrolling.toBottom();setUnread(false); }}>↓ 新内容</button>}
      <div className="composer-seat">{(timeline.running || connection.paused) && <div className="task-status"><span className={timeline.running ? 'shimmer' : ''}>{connection.paused ? '浏览器控制已暂停' : humans.some(record=>record.status==='pending') ? '等待你处理交互卡片' : 'Agent 正在执行'}</span><button onClick={() => void extension({ type: 'pause', paused: !connection.paused }).catch(caught => setError(caught.message))}>{connection.paused ? '恢复控制' : '暂停控制'}</button>{timeline.running && hasInput && <button className="task-stop" title="停止任务" disabled={stopping} onClick={()=>void stop()}>停止任务</button>}</div>}
      <PendingQueue items={pendingMessages.filter(item=>!item.runId || !timeline.turns.some((turn:any)=>turn.runId===item.runId))} modes={pendingModes} disabled={busy || unavailable || stopping || !canWrite} onMode={choosePendingMode} onCancel={withdrawPending} onEdit={editPending} onSend={dispatchPending}/>
      {(contexts.length > 0 || uploads.length > 0 || selectedSkills.length > 0) && <div className="context-chips">{selectedSkills.map(name=><div className="file-chip skill-chip" key={name}><Icon name="skill" size={13}/><span>{name}</span><button aria-label="移除 Skill" title={name} onClick={()=>chooseSkills(selectedSkills.filter(selected=>selected!==name))}>×</button></div>)}{contexts.map((page, index) => <details className="context-chip" key={index}><summary><span>↗ {page.title || page.url}</span><button aria-label="移除网页" onClick={event => { event.preventDefault(); setContexts(previous => previous.filter((_, at) => at !== index)); }}>×</button></summary><small>{page.url}</small><pre>{page.text}</pre></details>)}{uploads.map(item => <div className="file-chip" key={item.id}><span>▤ {item.name}</span><button onClick={() => setUploads(previous => previous.filter(file => file.id !== item.id))} aria-label="移除文件">×</button></div>)}</div>}
      <div className="composer-stack"><div className="composer-quick-actions"><WorkspacePicker value={workDir} workspaces={workspaces} disabled={unavailable || timeline.running || !canWrite} loading={workspaceLoading || workspaceSaving} error={workspaceError} onOpen={() => void loadWorkspaces()} onSelect={chooseWorkspace} onValidate={path => chooseWorkspace(path, true)} onBrowse={browseWorkspace} /><button title="附加文件" disabled={busy || unavailable || !canWrite} onClick={() => files.current?.click()}><Icon name="attach" size={15} /><span>文件</span></button><ContextMeter usage={usage} loading={stateLoading} error={usageError} onOpen={() => void loadSessionState()} /></div>
      {!canWrite && <p className="subagent-readonly" role="status">父会话不可用，当前子会话仅可查看。</p>}<div className="composer"><textarea aria-label="消息" disabled={!canWrite} readOnly={busy && sending.current} onPaste={pasteIntoComposer} placeholder={timeline.running ? 'Enter 加入 Pending，再按 Enter 插话…' : '给 SugarAgent 发消息…'} value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if(event.key==='Enter' && event.ctrlKey && !event.shiftKey && !event.metaKey && !event.altKey && !event.nativeEvent.isComposing){event.preventDefault();const input=event.currentTarget,start=input.selectionStart,end=input.selectionEnd;setDraft(input.value.slice(0,start)+'\n'+input.value.slice(end));requestAnimationFrame(()=>input.setSelectionRange(start+1,start+1));return;} if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey && !event.nativeEvent.isComposing) { event.preventDefault(); if(!event.repeat)void submitComposer(); } }} /><div className="composer-toolbar"><div className="composer-left"><AttachmentMenu disabled={busy || unavailable || !canWrite} skills={skills} selectedSkills={selectedSkills} skillsLoading={skillsLoading} skillsError={skillsError} onSkillsOpen={()=>void loadSkills()} onSkillsChange={chooseSkills} onPage={() => void attachPage()} onFile={() => files.current?.click()} onTabs={() => void extension({ type: 'tabs' }).then(setTabPicker).catch(caught => setError(caught.message))} /><PermissionPicker status={permissions} error={stateError} loading={stateLoading} saving={permissionSaving || loading || creating} onOpen={() => void loadSessionState()} onChange={choosePermission} /><Feedback error={error} modelError={modelsError} loading={modelsLoading} onDismiss={dismissError} onReload={() => void loadModels()} /></div><div className="send-tools"><ModelPicker models={models} value={modelId} effort={effort} disabled={unavailable || !canWrite} loading={modelsLoading} error={modelsError} onModel={chooseModel} onEffort={chooseEffort} onReload={() => void loadModels()} /><button className={'send-button' + (stopAction ? ' is-stop' : '')} title={sendLabel} aria-label={sendLabel} disabled={stopping || busy || unavailable || (!timeline.running && !hasInput) || (!canWrite && !stopAction)} onClick={() => void (stopAction ? stop() : submitComposer())}>{stopping || busy ? '…' : <Icon name={stopAction ? 'stop' : 'arrow'} size={stopAction ? 13 : 17} />}</button></div></div></div></div><input ref={files} type="file" multiple hidden onChange={event => void uploadFiles(event.target.files)} /></div>
    </>}
    {(editing || deleting || tabPicker) && <Dialog label={editing ? '修改会话名' : deleting ? '删除会话' : '选择网页'} onClose={() => { if (!sessionActionBusy) { setEditing(null); setDeleting(null); setTabPicker(null); setDialogError(''); } }}>
      {dialogError && <p className="dialog-error" role="alert">{dialogError}</p>}
      {editing ? <form onSubmit={event => { event.preventDefault(); void updateSession(editing, 'session.update', { name: newName.trim() }).then(ok => { if (ok) setEditing(null); }); }}><h2>修改会话名</h2><input aria-label="会话名称" autoFocus value={newName} onChange={event => setNewName(event.target.value)} /><div className="dialog-actions"><button disabled={sessionActionBusy} type="button" onClick={() => setEditing(null)}>取消</button><button disabled={sessionActionBusy || !newName.trim()} className="primary">保存</button></div></form>
      : deleting ? <><h2>删除会话</h2><p>确认删除“{deleting.name || '未命名会话'}”？</p><div className="dialog-actions"><button disabled={sessionActionBusy} onClick={() => setDeleting(null)}>取消</button><button disabled={sessionActionBusy} className="danger" onClick={() => void updateSession(deleting, 'session.delete').then(ok => { if (ok) setDeleting(null); })}>删除</button></div></>
      : <><div className="view-heading"><h2>附加标签页</h2><button onClick={() => setTabPicker(null)}>关闭</button></div><div className="tab-list">{tabPicker?.map(tab => <button key={tab.id} onClick={() => void attachPage(tab.id)}><strong>{tab.title || tab.url}</strong><small>{tab.url}</small></button>)}</div></>}
    </Dialog>}
  </main>;
}
