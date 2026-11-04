import {processStatus,updateProcessTiming} from './process-display.mjs';

export const toolEventTypes=new Set(['tool_call_delta','tool_command_delta','tool_pending','tool_execution_state','tool_call','tool_snapshot']);
const terminal=new Set(['completed','failed','timed_out','interrupted','cancelled','denied','blocked','skipped','not_executed','unknown']);
const phaseOf=event=>event.react_iter ?? event.step ?? event.iteration;
const indexOf=event=>event.tool_call_index ?? event.index;
const callOf=event=>String(event.tool_call_id || event.id || '');
const scoped=(block,event)=> (phaseOf(event)==null || block.phase==null || block.phase===String(phaseOf(event)))
  && (event.stream_seq==null || block.streamSeq==null || String(block.streamSeq)===String(event.stream_seq));

export function findToolBlock(blocks,event) {
  const tools=blocks.filter(block=>block.kind==='tool');
  if(event.execution_id){const match=tools.find(block=>block.executionId===event.execution_id);if(match)return match;}
  const call=callOf(event);
  if(call){const match=tools.find(block=>block.toolCallId===call || block.id===call);if(match)return match;}
  const index=indexOf(event);
  if(index!=null){
    const match=tools.find(block=>scoped(block,event) && String(block.toolIndex)===String(index) && (!call || !block.toolCallId || block.toolCallId===call));
    if(match)return match;
  }
  if(call){
    const drafts=tools.filter(block=>!block.toolCallId && scoped(block,event) && !block.terminal && (index==null || block.toolIndex==null || String(block.toolIndex)===String(index)));
    if(drafts.length===1)return drafts[0];
  }
}

export function toolBlockId(event,count) {
  return event.execution_id ? 'execution-'+event.execution_id : callOf(event) || `tool-draft-${phaseOf(event) ?? 'legacy'}-${event.stream_seq ?? 'legacy'}-${indexOf(event) ?? count}`;
}
const owns=(object,key)=>Object.prototype.hasOwnProperty.call(object,key) && object[key]!==undefined && object[key]!==null;
function partialCommand(raw) {
  const match=/"(?:command|cmd)"\s*:\s*"((?:\\[\s\S]|[^"\\])*)(?:"|$)/.exec(raw || '');
  if(!match)return '';
  try{return JSON.parse('"'+match[1]+'"');}catch{return match[1].replace(/\\(["\\nrt])/g,(_,c)=>({n:'\n',r:'\r',t:'\t'}[c] || c));}
}
function commandFromArgs(args) {
  if(!args || typeof args!=='object')return '';
  const command=typeof args.command==='string' ? args.command : typeof args.cmd==='string' ? args.cmd : '';
  return command && Array.isArray(args.args) ? [command,...args.args].join(' ') : command;
}

export function applyToolEvent(block,event,renderText,timing={}) {
  const type=event.type,deltaType=type==='tool_call_delta' || type==='tool_command_delta';
  const version=Number(event.execution_runtime_seq || 0);
  if(version && block.executionVersion && version<=block.executionVersion)return;
  if(block.terminal && (deltaType || type==='tool_pending' || type==='tool_execution_state' && processStatus(event).active))return;
  const counter=type+':'+(event.stream_seq ?? block.streamSeq ?? 'legacy'),seq=Number(event.delta_seq || 0);
  if(deltaType && seq && seq<=Number(block.deltaSeqs?.[counter] || 0))return;
  if(deltaType)block.reveal=!!timing.reveal;
  else if(type==='tool_snapshot' || type==='tool_call' || event.args!==undefined || event.arguments!==undefined || event.tool_args!==undefined)block.reveal=false;
  if(version)block.executionVersion=version;
  if(event.execution_id)block.executionId=event.execution_id;
  if(callOf(event))block.toolCallId=callOf(event);
  if(indexOf(event)!=null)block.toolIndex=indexOf(event);
  if(event.stream_seq!=null)block.streamSeq=event.stream_seq;
  if(deltaType && seq)block.deltaSeqs={...block.deltaSeqs,[counter]:seq};
  if(type==='tool_snapshot')for(const kind of ['tool_call_delta','tool_command_delta']){
    const last=Number(event['last_'+kind+'_delta_seq'] || 0),key=kind+':'+(event.stream_seq ?? block.streamSeq ?? 'legacy');
    if(last)block.deltaSeqs={...block.deltaSeqs,[key]:Math.max(last,block.deltaSeqs?.[key] || 0)};
  }

  if(type==='tool_call_delta') {
    if(!block.argumentsCommitted){
      block.nameRaw=event.replayed_snapshot ? event.name_delta || '' : (block.nameRaw || '')+(event.name_delta || '');
      block.argsText=event.replayed_snapshot ? event.arguments_delta || '' : (block.argsText || '')+(event.arguments_delta || '');
      if(block.nameRaw)block.title=block.nameRaw;
      block.commandText=partialCommand(block.argsText);
    }
  } else {
    const name=[event.tool,event.tool_name,event.name].find(value=>typeof value==='string' && value);
    if(name){block.title=name;block.nameRaw=name;}
    const args=event.args ?? event.arguments ?? event.tool_args;
    if(args!==undefined && args!==null){block.args=args;block.argsText=renderText(args);block.argumentsCommitted=true;}
    else if(type==='tool_snapshot' && owns(event,'arguments_raw') && !block.argumentsCommitted)block.argsText=event.arguments_raw;
    block.commandText=commandFromArgs(block.args) || event.command_preview || block.commandText || partialCommand(block.argsText);
    if(type==='tool_command_delta')block.outputText=event.replayed_snapshot ? event.delta || event.command_delta || '' : (block.outputText || '')+(event.delta || event.command_delta || '');
    for(const [key,field] of [['output','outputText'],['stdout','stdoutText'],['stderr','stderrText']])if(owns(event,key))block[field]=renderText(event[key]);
    if(owns(event,'exit_code'))block.exitCode=event.exit_code;
    if(owns(event,'process_state'))block.processState=event.process_state;
    const result=event.raw_content ?? event.result ?? event.content;
    if(result!==undefined && result!==null){
      block.result=result;block.content=renderText(result);block.hasResult=true;
      block.format=result && typeof result==='object' && !Array.isArray(result) ? 'json' : 'markdown';
    }
  }
  let stateEvent=event;
  if(type==='tool_call_delta')stateEvent={status:'generating'};
  if(type==='tool_command_delta')stateEvent={status:'running'};
  const status=processStatus(stateEvent,block.statusCode);
  if(status.code==='running' && ['generating','pending','queued','waiting_approval'].includes(block.statusCode) && !event.started_at && !timing.history){
    block.startedAt=timing.now ?? Date.now();delete block.endedAt;delete block.durationMs;
  }
  block.statusCode=status.code;block.status=status.label;block.active=status.active;block.terminal=terminal.has(status.code);
  block.executed=!!(block.executed || event.executed || type==='tool_command_delta' || status.code==='running');
  updateProcessTiming(block,event,status.active,{...timing,history:timing.history || type==='tool_snapshot'});
}

export function toolSnapshotEvent(record) {
  return {...record,type:'tool_snapshot',execution_status:record.status,status:record.tool_status || record.status,
    last_tool_call_delta_seq:record.last_tool_call_delta_delta_seq ?? record.last_tool_call_delta_seq,
    last_tool_command_delta_seq:record.last_tool_command_delta_delta_seq ?? record.last_tool_command_delta_seq,
    started_at:record.executed ? record.execution_started_at : record.started_at,
    finished_at:record.finished_at || (!['generating','waiting_execution','pending','queued','running','waiting_approval','waiting_input'].includes(record.status) ? record.updated_at : undefined),
    execution_runtime_seq:record.last_runtime_seq,runtime_seq:record.last_runtime_seq,replayed_snapshot:true};
}
export function toolOutput(block) {
  if(block.outputText)return block.outputText;
  return [block.stdoutText,block.stderrText ? 'STDERR:\n'+block.stderrText : ''].filter(Boolean).join('\n');
}
export function outputCoveredByResult(block) {
  const normalize=value=>String(value || '').replace(/^[ \t]*(?:实时输出|STDOUT:|STDERR:)[ \t]*\r?$/gm,'').trim();
  const output=normalize(toolOutput(block));
  return !!output && normalize(block.content).includes(output);
}
