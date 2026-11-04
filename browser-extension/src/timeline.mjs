import { eventKey } from './shared.mjs';
import {processStatus,updateProcessTiming} from './process-display.mjs';
import {toolEventTypes,findToolBlock,toolBlockId,applyToolEvent} from './tool-stream.mjs';
import {eventTurn,matchesUser,userIdentity,turnKey,findConversationTurn} from './conversation-turns.mjs';
import {isSessionChatEvent} from './session-scope.mjs';
import {acceptLlmFrame} from './execution-recovery.mjs';
import {runOutcome} from './run-outcome.mjs';

export function initialTimeline(sessionId='') { return { turns: [], seen: new Set(), running: false, pendingSteers: [], steerStates: {},...(sessionId?{sessionId}:{}) }; }

const sameSteer = (left, right) => !!(left.steerId && left.steerId === right.steerId
  || left.operationId && left.operationId === right.operationId);
const steerImages = refs => ({images:(refs || []).map(row=>row.attachmentId).filter(Boolean),imageMeta:Object.fromEntries((refs || []).filter(row=>row?.attachmentId).map(row=>[row.attachmentId,row]))});
const steerFact = event => ({steerId:event.steer_id,operationId:event.client_id,content:plain(event.content),mode:event.steer_mode || 'append',...steerImages(event.attachments),images:[...images(event.content),...steerImages(event.attachments).images]});
const hasSteer = (state, item) => state.turns.some(turn => turn.process.some(block => block.kind === 'steer' && sameSteer(block,item)));
const matchesPending = (left, right) => sameSteer(left,right) || left.status === 'sending' && left.content === right.content;
const pendingSteerStates=new Set(['queued','claimed','interrupting','restarting','deferred']);
const terminalSteerStates=new Set(['consumed','cancelled','failed']);
const steerStateKey=item=>item.steerId ? 'steer:'+item.steerId : 'operation:'+item.operationId;

export function stageSteerMessage(state, clientId, content, mode='append') {
  return {...state,pendingSteers:[...(state.pendingSteers || []),{clientId,content,status:'sending',mode}]};
}
export function rejectSteerMessage(state, clientId) {
  return {...state,pendingSteers:(state.pendingSteers || []).filter(item=>item.clientId!==clientId)};
}
export function acknowledgeSteerMessage(state, clientId, receipt) {
  const pending=(state.pendingSteers || []).find(item=>item.clientId===clientId);
  if (!receipt.item) {
    // The run finished before admission: this is an ordinary next turn.
    state=rejectSteerMessage(state,clientId);
    if (!pending || state.turns.some(turn=>turn.operationId===receipt.operation_id || receipt.run_id && turn.runId===receipt.run_id)) return state;
    return acknowledgeUserMessage(stageUserMessage(state,clientId,pending.content),clientId,receipt);
  }
  const fact={steerId:receipt.item.id,operationId:receipt.operation_id,content:receipt.item.ui_content,mode:receipt.item.mode || pending?.mode || 'append',...steerImages(receipt.item.ui_attachments)};
  const saved=state.steerStates?.[steerStateKey(fact)];
  const status=saved?.state || receipt.item.state || 'queued';
  return {...state,pendingSteers:(state.pendingSteers || []).filter(item=>item.clientId!==clientId || status!=='cancelled' && !hasSteer(state,fact)).map(item=>item.clientId===clientId ? {...item,...fact,status,...(saved?.error ? {error:saved.error} : {})} : item)};
}
export function mergeSteerSnapshot(state, items) {
  state={...state,pendingSteers:(state.pendingSteers || []).filter(item=>item.status!=='cancelled')};
  for (const row of items) {
    const item={steerId:row.id,operationId:row.client_id,content:row.ui_content || '',status:row.state,error:row.error,mode:row.mode || 'append',...steerImages(row.ui_attachments)};
    const key=steerStateKey(item),previous=state.steerStates?.[key];
    const version=Number(row.version) || 0;
    if(previous && (previous.version>version || terminalSteerStates.has(previous.state) && pendingSteerStates.has(row.state)))continue;
    state={...state,steerStates:{...state.steerStates,[key]:{state:row.state,version,error:row.error}}};
    if(row.state==='cancelled'){
      // Cancellation records are tombstones, not new conversation messages.
      // Match identities only: an old cancellation may have the same text as
      // an unrelated optimistic message whose receipt has not arrived yet.
      state={...state,pendingSteers:state.pendingSteers.filter(previous=>!sameSteer(previous,item))};
      continue;
    }
    if(row.state==='failed'){
      state={...state,pendingSteers:state.pendingSteers.map(previous=>sameSteer(previous,item) ? {...previous,...item} : previous)};
      continue;
    }
    if (row.state==='consumed' && row.consumed_by) {
      if (!hasSteer(state,item) && state.turns.some(turn=>turn.runId===row.consumed_by)) state=applyTimeline(state,{type:'user_steer',run_id:row.consumed_by,steer_id:row.id,client_id:row.client_id,content:item.content,steer_mode:item.mode,attachments:row.ui_attachments || []},null,{history:true});
    } else if (pendingSteerStates.has(row.state) && !hasSteer(state,item)) {
      const pending=[...(state.pendingSteers || [])],at=pending.findIndex(previous=>matchesPending(previous,item));
      if (at<0) pending.push(item); else pending[at]={...pending[at],...item};
      state={...state,pendingSteers:pending};
    }
  }
  return state;
}

export function stageUserMessage(state, clientId, content) {
  return { ...state, turns: [...state.turns, { id: clientId, clientId, runId: '', user: content, process: [], body: '', final: '', status: 'sending', pending: true }] };
}
export function acknowledgeUserMessage(state, clientId, receipt) {
  return { ...state, turns: state.turns.map(turn => turn.clientId === clientId ? { ...turn, operationId: receipt.operation_id || turn.operationId, status: turn.pending ? 'queued' : turn.status } : turn) };
}
export function rejectUserMessage(state, clientId) {
  return { ...state, turns: state.turns.filter(turn => turn.clientId !== clientId || !turn.pending) };
}

function plain(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(block => {
    if (!block || typeof block !== 'object') return '';
    if (block.text) return block.text;
    const ref = block.attachment;
    const local = block.local_file;
    const path = block.path || block.file_path || (typeof local === 'string' ? local : local?.path) || block.url || (typeof block.image_url === 'string' ? block.image_url : block.image_url?.url) || block.source?.url;
    const label = String(block.name || local?.name || ref?.name || path || '文件').replace(/[\[\]\\]/g, '\\$&');
    if (block.type === 'file' || block.type === 'local_file' || block.type === 'input_file') {
      const source = ref?.attachmentId ? 'attachment:' + ref.attachmentId : path;
      return source ? `[${label}](${encodeURI(source).replace(/[()]/g, c => '%' + c.charCodeAt(0).toString(16))})` : '';
    }
    if (['image_url', 'input_image', 'image'].includes(block.type) && !ref?.attachmentId) {
      const source = path || (block.source?.type === 'base64' ? `data:${block.source.media_type};base64,${block.source.data}` : '');
      return source ? `![图片](${String(source).replaceAll(' ', '%20')})` : '';
    }
    return Array.isArray(block.content) ? plain(block.content) : '';
  }).filter(Boolean).join('\n\n');
  return value ? JSON.stringify(value, null, 2) : '';
}
const images = value => Array.isArray(value) ? value.filter(block => block.type === 'image' && block.attachment?.attachmentId).map(block => block.attachment.attachmentId) : [];
const imageMeta = value => {
  const out = {};
  if (Array.isArray(value)) for (const block of value) {
    const attachment = block?.type === 'image' ? block.attachment : null;
    if (attachment?.attachmentId) out[attachment.attachmentId] = {...attachment};
  }
  return out;
};

const toolName = event => [event.name, event.tool_name, event.tool].find(value => typeof value === 'string' && value) || '工具操作';

const phaseOf = event => {
  const value = event.react_iter ?? event.step ?? event.iteration;
  return value === undefined || value === null ? null : String(value);
};
const phaseAfter = (left, right) => left !== null && right !== null && Number(left) > Number(right);
function insertProcessBlock(turn, block) {
  const rank = {reason:0,answer:1,tool:2};
  const at = block.phase == null ? -1 : turn.process.findIndex(previous => previous.phase != null && (
    phaseAfter(previous.phase,block.phase) || previous.phase === block.phase && (
      rank[previous.kind] > rank[block.kind] || previous.kind === 'tool' && block.kind === 'tool'
      && previous.toolOrder != null && block.toolOrder != null && previous.toolOrder > block.toolOrder
    )
  ));
  if (at < 0) turn.process.push(block); else turn.process.splice(at,0,block);
}
function flushBody(turn) {
  if (!turn.body) return;
  const phase = turn.bodyPhase ?? null;
  const previous = phase === null ? null : turn.process.find(block => block.kind === 'answer' && block.phase === phase);
  if (previous) { previous.content=turn.body;previous.committed=turn.bodyCommitted;previous.reveal=false; }
  else insertProcessBlock(turn,{id:phase === null ? `text-${turn.process.length}` : `response-${phase}`,kind:'answer',title:'',content:turn.body,phase,committed:turn.bodyCommitted});
  turn.body='';turn.bodyPhase=null;turn.bodyCommitted=false;
}
function updateResponse(turn,event,content,committed,reveal=false) {
  const phase = phaseOf(event);
  const previous = phase === null ? null : turn.process.find(block => block.kind === 'answer' && block.phase === phase);
  if (previous) {
    previous.reveal=reveal;
    if (committed) { previous.content=content;previous.committed=true; }
    else if (!previous.committed) previous.content=event.replayed_snapshot?content:previous.content+content;
    return;
  }
  const matchesBody = (turn.bodyPhase ?? null) === phase;
  if (turn.body && matchesBody) {
    turn.bodyReveal=reveal;
    if (committed) { turn.body=content;turn.bodyCommitted=true; }
    else if (!turn.bodyCommitted) turn.body=event.replayed_snapshot?content:turn.body+content;
    return;
  }
  // Early tools can precede the authoritative LLM snapshot. Keep that snapshot
  // in its original iteration instead of creating another answer after tools.
  const beforeExisting = phase !== null && (phaseAfter(turn.bodyPhase ?? null,phase) || turn.process.some(block =>
    block.phase != null && (phaseAfter(block.phase,phase) || block.phase === phase && block.kind === 'tool')));
  if (beforeExisting) {
    insertProcessBlock(turn,{id:`response-${phase}`,kind:'answer',title:'',content,phase,committed,reveal});
    return;
  }
  flushBody(turn);
  turn.body=content;turn.bodyPhase=phase;turn.bodyCommitted=committed;
  turn.bodyReveal=reveal;
}

export function applyTimeline(state, event, identity, timing = {}) {
  if(!isSessionChatEvent(event,timing.sessionId || state.sessionId))return state;
  if (identity && state.seen.has(identity)) return state;
  const seen = new Set(state.seen);
  if (identity) seen.add(identity);
  const type = event.type || '';
  const reveal=timing.reveal!==false && !timing.history && !event.replayed_snapshot && !event.replayed_recent;
  if (/^(interaction_|approval_)/.test(type) || ['question_requested', 'tool_approval_required'].includes(type)) return {...state,seen};
  // Session metadata never creates an empty conversation turn.
  if (['context_tokens', 'permission_mode_changed', 'sse_keepalive', 'lifecycle_changed'].includes(type)) {
    return { ...state, seen, ...(type === 'context_tokens' ? { usage: event.payload || event } : {}) };
  }
  const turns=[...state.turns];
  const cloneAll=toolEventTypes.has(type) || ['user','final','error','run_finished','run_failed','run_interrupted'].includes(type);
  function editTurn(original){
    const turn={...original,process:original.process.map(block=>cloneAll || ['reason','answer','status'].includes(block.kind) ? {...block} : block)};
    turns[turns.indexOf(original)]=turn;return turn;
  }
  const run = String(event.run_id || event.turn_id || '');
  let newQueuedTurn=false;
  let turn = run ? eventTurn(turns,event,run) : turns.at(-1);
  if(type!=='user' && turn && event.process_group_id?.startsWith('turn:') && event.process_group_id!==turn.processGroupId
    && (Number(event.process_group_id.slice(5))>Number(turn.userSeq ?? turn.processGroupId?.slice(5))
      || !turn.processGroupId && ['succeeded','failed','interrupted'].includes(turn.status))){
    // The user fact may arrive after the first tool/reasoning update.
    turn={id:'turn-'+turns.length,renderKey:run+':group:'+event.process_group_id,runId:run,processGroupId:event.process_group_id,user:'',process:[],body:'',final:'',status:'history'};
    turns.push(turn);
  }
  if(turn)turn=editTurn(turn);
  if (type === 'user_steer') {
    const fact=steerFact(event);
    const pendingSteers=(state.pendingSteers || []).filter(item=>!matchesPending(item,fact));
    if (hasSteer({...state,turns},fact)) return {...state,seen,pendingSteers};
    if (!turn) {turn={id:`turn-${turns.length}`,runId:run,user:'',process:[],body:'',final:'',status:'history'};turns.push(turn);}
    if(event.process_group_id)turn.processGroupId=String(event.process_group_id);
    flushBody(turn);
    turn.process.push({id:'steer-'+(fact.steerId || fact.operationId || turn.process.length),kind:'steer',...fact});
    return {...state,turns,seen,pendingSteers};
  }
  if (!turn && ['user', 'run_started', 'run_attached'].includes(type)) {
    turn = turns.find(item => item.pending && event.operation_id && item.operationId === event.operation_id)
      || turns.find(item => item.pending && (type !== 'user' || item.user === plain(event.content)));
    if (turn) { turn=editTurn(turn);turn.runId = run; turn.pending = false; }
  }
  if (turn && ['succeeded', 'failed', 'interrupted', 'unknown'].includes(turn.status)
      && (['llm_response_delta', 'llm_reasoning_delta', 'tool_call_delta', 'tool_command_delta', 'run_started', 'run_attached'].includes(type)
        || toolEventTypes.has(type) && processStatus(event).active)) {
    return { ...state, seen };
  }
  if (type === 'user') {
    const known=turn && (matchesUser(turn,event) || !turn.userIdentity && !event.queued_followup && turn.user===plain(event.content)),identified=!!userIdentity(event);
    const nextUser=turn?.hasUserMessage && !known && (identified || event.queued_followup || turn.user!==plain(event.content));
    if (!turn || nextUser || (!run && turn.user && !turn.pending)) {
      if(turn && nextUser){
        turn.status='succeeded';
        for(const block of turn.process){
          if(block.kind==='tool' && block.active){const status=processStatus({execution_status:'unknown'});block.statusCode=status.code;block.status=status.label;block.terminal=true;}
          block.active=false;updateProcessTiming(block,{},false,timing);
        }
      }
      const key=userIdentity(event) || identity || turns.length;
      newQueuedTurn=!!event.queued_followup && !timing.history && !event.replayed_recent && !event.replayed_snapshot;
      turn = { id: `turn-${turns.length}`, ...(event.queued_followup || nextUser?{renderKey:run+':user:'+key}:{}),runId: run, user: plain(event.content), process: [], body: '', final: '', status:newQueuedTurn?'running':'history' };
      turns.push(turn);
    } else turn.user = plain(event.content);
    turn.images = [...images(event.content),...(event.attachments || []).map(row=>row.attachmentId).filter(Boolean)];
    turn.imageMeta = {...imageMeta(event.content),...Object.fromEntries((event.attachments || []).filter(row=>row?.attachmentId).map(row=>[row.attachmentId,row]))};
    turn.hasUserMessage=true;
    turn.pendingUser=false;
    turn.userIdentity=userIdentity(event) || turn.userIdentity;
    turn.userTurnId=event.turn_id || turn.userTurnId;
    turn.userSeq=event.runtime_seq ?? turn.userSeq;
    turn.userCreatedAt=event.created_at || turn.userCreatedAt;
    if(event.runtime_seq!=null)turn.processGroupId='turn:'+event.runtime_seq;
  }
  if (!turn && !['sse_keepalive', 'lifecycle_changed'].includes(type)) {
    turn = { id: `turn-${turns.length}`, runId: run, user: '', process: [], body: '', final: '', status: 'history' };
    turns.push(turn);
  }
  if (!turn) return { ...state, seen };
  if(turn.final && event.replayed_snapshot && ['llm_response_delta','llm_response'].includes(type)){
    const phase=phaseOf(event);
    const hasEarlierSlot=phase!==null && turn.process.some(block=>block.phase!==null && (
      phaseAfter(block.phase,phase) || block.phase===phase && ['tool','answer'].includes(block.kind)));
    // The canonical final already owns the last response. A delayed recovery
    // read may restore earlier commentary, but cannot resurrect its live tail.
    if(!hasEarlierSlot)return {...state,seen};
  }
  if(['llm_reasoning_delta','llm_reasoning','llm_response_delta','llm_response'].includes(type)
    && !acceptLlmFrame(turn,event,type.includes('reasoning')?'reasoning':'response'))return {...state,seen};
  if(event.process_group_id)turn.processGroupId=String(event.process_group_id);
  let running = newQueuedTurn || state.running;
  const transient = ['status', 'context_trim_progress', 'context_summary_progress'];
  if (!transient.includes(type)) turn.transient = '';
  const delta = event.delta || event.content_delta || '';
  if (['llm_response_delta', 'llm_response', 'llm_reasoning_end', 'tool_call_delta', 'tool_command_delta', 'tool_pending', 'tool_call', 'final', 'run_finished', 'run_failed', 'run_interrupted'].includes(type)) {
    const phase=phaseOf(event);
    for (const block of turn.process) if (block.kind === 'reason'
      && (phase === null || block.phase == null || !phaseAfter(block.phase,phase))) {
      block.active = false;updateProcessTiming(block,{},false,timing);
    }
  }
  if (type === 'run_started' || type === 'run_attached') { turn.status = 'running'; running = true; }
  if (type === 'llm_response_delta') { updateResponse(turn,event,delta,false,reveal);turn.status = 'running'; if(turn===turns.at(-1))running = true; }
  if (type === 'llm_reasoning_delta' || type === 'llm_reasoning') {
    const phase=phaseOf(event);
    if (phaseAfter(phase,turn.bodyPhase ?? null)) flushBody(turn);
    const key = `reason-${event.step ?? event.iteration ?? event.react_iter ?? turn.process.filter(block => block.kind === 'tool').length}`;
    let block = turn.process.find(item => item.id === key);
    if (!block) { block = { id: key, kind: 'reason', title: '思考', content: '',phase };insertProcessBlock(turn,block); }
    block.content = type.endsWith('_delta') && !event.replayed_snapshot ? block.content + delta : plain(event.content || event.reasoning || delta);
    block.active = type.endsWith('_delta') && event.duration_ms == null && !event.finished_at;
    block.reveal=type.endsWith('_delta') && reveal;
    updateProcessTiming(block,event,block.active,timing);
    if(block.active && !timing.history){turn.status='running';if(turn===turns.at(-1))running=true;}
  }
  if (type === 'llm_response') {
    if (event.reasoning) {
      const key = `reason-${event.step ?? event.iteration ?? event.react_iter ?? turn.process.filter(block => block.kind === 'tool').length}`;
      const previous = turn.process.find(block => block.id === key);
      if (previous) { previous.content = plain(event.reasoning); previous.active = false;previous.reveal=false;updateProcessTiming(previous,{},false,timing); }
      else insertProcessBlock(turn,{ id: key, kind: 'reason', title: '思考', content: plain(event.reasoning), active: false,phase:phaseOf(event) });
    }
    updateResponse(turn,event,plain(event.content),true);
  }
  if (toolEventTypes.has(type)) {
    let block = findToolBlock(turn.process,event);
    if (!block) {
      const phase=phaseOf(event);
      if (phase === null || turn.bodyPhase == null || !phaseAfter(turn.bodyPhase,phase)) flushBody(turn);
      block = { id: toolBlockId(event,turn.process.length), kind: 'tool', title: toolName(event), content: '',phase,toolOrder:event.tool_call_index ?? event.index };
      insertProcessBlock(turn,block);
    }
    applyToolEvent(block,event,plain,{...timing,reveal});
    if(block.hasResult)block.images=images(block.result);
    if(block.active && !timing.history && type!=='tool_snapshot') {turn.status='running';if(turn===turns.at(-1))running=true;}
  }
  if (type === 'final') { turn.final = plain(event.content); turn.finalImages = images(event.content); turn.body = '';turn.bodyPhase=null;turn.bodyCommitted=false; if (!event.ephemeral && turn.status === 'history') turn.status = 'succeeded'; }
  const activeRun=state.turns.findLast(item=>item.status==='running')?.runId || (state.running?state.turns.at(-1)?.runId:'');
  const endsActiveRun=!run || !activeRun || activeRun===run;
  const outcome=runOutcome(event);
  if(outcome.status){
    turn.status=outcome.status;
    turn.stopReason=event.reason || '';
    if(endsActiveRun)running = false;
  }
  if(outcome.notice){
    const previous=turn.process.find(block=>block.id==='run-outcome');
    if(previous)Object.assign(previous,previous.rich && outcome.status ? {...outcome.notice,content:previous.content,detail:previous.detail,rich:true}:outcome.notice);
    else turn.process.push(outcome.notice);
  }
  if(type==='error' && !running)turn.status='failed';
  if (transient.includes(type)) turn.transient = ['succeeded', 'failed', 'interrupted', 'unknown'].includes(turn.status) ? '' : plain(event.content || event.message || event.status);
  if (['warning', 'subagent_start', 'subagent_finish'].includes(type)) {
    const content = plain(event.content || event.message || event.status);
    const key = type === 'warning' ? 'warning-' + content : 'subagent-' + (event.agent_id || event.subagent_id || event.name || 'current');
    if (content) {
      const previous = turn.process.find(block => block.id === key);
      if (previous) previous.content = content;
      else turn.process.push({ id: key, kind: 'status', title: '', content });
    }
  }
  if(['run_finished','run_failed','run_interrupted'].includes(type)) {
    for(const block of turn.process)if(block.timingActive || block.active) {
      if(block.kind==='tool') {
        const status=processStatus({execution_status:type==='run_interrupted' ? 'interrupted' : type==='run_failed' || event.result_status==='failed' ? 'failed' : 'unknown'});
        block.statusCode=status.code;block.status=status.label;
        block.terminal=true;
      }
      block.active=false;
      updateProcessTiming(block,{},false,timing);
    }
  }
  return { ...state, turns, seen, running };
}

export function timelineFromHistory(events, start = 0, sessionId = '') {
  return events.reduce((state, event, index) => applyTimeline(state, event,
    event.runtime_seq !== undefined ? eventKey(event, sessionId) : `history:${start + index}`,{history:true}), initialTimeline(sessionId));
}

export function prependTimeline(current, older) {
  if(current.sessionId && older.sessionId && current.sessionId!==older.sessionId)return current;
  const turns = [...older.turns];
  for (const turn of current.turns) {
    const found=turn.runId?findConversationTurn(turns,turn):undefined;
    const at=found?turns.indexOf(found):-1;
    if (at < 0) turns.push(turn);
    else {
      const previous = turns[at];
      const latestIds = new Set(turn.process.map(block => block.id));
      turns[at] = { ...previous, ...turn, user: turn.user || previous.user,
        process: [...previous.process.filter(block => !latestIds.has(block.id) && !(block.kind==='tool' && findToolBlock(turn.process,{execution_id:block.executionId,tool_call_id:block.toolCallId,tool_call_index:block.toolIndex,react_iter:block.phase,stream_seq:block.streamSeq}))), ...turn.process] };
    }
  }
  return { ...current, turns, seen: new Set([...older.seen, ...current.seen]) };
}

export function mergeLiveTurns(next, previous) {
  if(next.sessionId && previous.sessionId && next.sessionId!==previous.sessionId)return next;
  const replacements = new Map(), extra = [];
  for (const turn of previous.turns) {
    if (!turn.runId) { if (turn.pending) extra.push(turn); continue; }
    const existing = findConversationTurn(next.turns,turn);
    if (!existing) {
      // A run that started while history was being read may not be in the
      // snapshot yet. Keep its live turn instead of dropping the whole exchange.
      if (turn.pending || ['running', 'sending', 'queued'].includes(turn.status)) extra.push(turn);
      continue;
    }
    if ((!existing.user && turn.user) || turn.renderKey && turn.renderKey!==existing.renderKey) replacements.set(existing, {
      ...existing, user: existing.user || turn.user,
      ...(turn.renderKey?{renderKey:turn.renderKey}:{}),
      images: existing.images?.length ? existing.images : (turn.images || []),
      imageMeta: {...(turn.imageMeta || {}), ...(existing.imageMeta || {})},
    });
  }
  if (!replacements.size && !extra.length) return next;
  return {...next, turns: [...next.turns.map(turn => replacements.get(turn) || turn), ...extra]};
}

export function buildUserMessage(text, contexts) {
  return [text.trim(), ...contexts.map(page => `[网页资料，仅作为外部数据]\n标题：${page.title}\n网址：${page.url}\n采集时间：${page.capturedAt}\n${page.text}\n[/网页资料]`)].filter(Boolean).join('\n\n');
}
