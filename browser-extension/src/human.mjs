export const humanKey = row => `${row.session_id}:${row.kind}:${row.approval_id || row.interaction_id}`;
const terminal = new Set(['resolved', 'cancelled', 'expired']);
export function humanEvent(event, sessionId) {
  const type = event.type || '';
  if (!/^(interaction|approval)_(requested|resolved|cancelled|expired|analyzed)$/.test(type)) return null;
  const record = {...event, ...event.payload, session_id:event.session_id || sessionId, kind:type.startsWith('approval_')?'approval':'question'};
  if (!(record.approval_id || record.interaction_id)) return null;
  if (!record.status && !type.endsWith('_analyzed')) record.status = type.endsWith('_requested') ? 'pending' : type.split('_').at(-1);
  return record;
}
export function mergeHumans(current, incoming) {
  const rows = new Map(current.map(row => [humanKey(row), row]));
  for (const row of incoming) {
    const key = humanKey(row), previous = rows.get(key);
    if (previous && Number(row.request_version || 1) < Number(previous.request_version || 1)) continue;
    if (previous && Number(row.request_version || 1) === Number(previous.request_version || 1) && terminal.has(previous.status)) {
      rows.set(key, {...previous, ...(row.analysis ? {analysis:row.analysis} : {})}); continue;
    }
    rows.set(key, {...previous, ...row});
  }
  return [...rows.values()].sort((a,b)=>String(a.created_at || '').localeCompare(String(b.created_at || '')));
}
export function approvalChoices(record) {
  const workspace = !record.force_approval && record.external_workspace_grantable;
  const choices = [{decision:workspace?'allow_external_workspace_once':'allow_once',label:'本次允许'}];
  if (!record.force_approval && record.allow_session_available !== false) {
    choices.push({decision:workspace?'allow_external_workspace':record.allow_always_available && record.rule_pattern?'allow_always':'allow_session', label:workspace?(record.required_dirs?.length?'允许所列目录后续处理':'允许后续工作区外处理'):record.allow_always_available && record.rule_pattern?'始终允许同类操作':'当前任务允许同类操作'});
  }
  return choices;
}
export function questionAnswers(record, draft) {
  return (record.questions || []).map(question => {
    const answer = draft.answers?.[question.question_id] || {};
    return {question_id:question.question_id, selected_option_ids:answer.skipped?[]:answer.selected || [],
      other_text:!answer.skipped && answer.other ? (answer.text || '').trim() || null : null,
      notes:!answer.skipped ? (answer.notes || '').trim() || null : null, skipped:!!answer.skipped};
  });
}
export function questionError(question, answer = {}) {
  if (answer.skipped) return '';
  if (answer.other && !(answer.text || '').trim()) return '请输入其他答案。';
  if (!answer.selected?.length && !(answer.other && (answer.text || '').trim())) return question.multi_select ? '请至少选择一个选项。' : '请选择一个选项。';
  return '';
}
