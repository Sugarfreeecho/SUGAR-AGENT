// The websocket envelope is the subscribed transport, not necessarily the
// owner of the forwarded child frame inside it. Check ownership first.
export function isSessionChatEvent(event,sessionId=''){
  if(!event || event._subagent_forward)return false;
  const owner=event.session_id || event.sessionId;
  if(sessionId && owner && owner!==sessionId)return false;
  if(event.agent_id && (sessionId ? event.agent_id!==sessionId : event.ephemeral || event.type==='execution_update'))return false;
  return !['subagent_start','subagent_finish','subagent_state','subagent_status'].includes(event.type);
}
export const isSubagentNotice=event=>!!(event && (event._subagent_forward || event.agent_id || String(event.type || '').startsWith('subagent_'))
  && /^(subagent_|run_|interaction_|approval_|question_requested|tool_approval_required)/.test(event.type || ''));
