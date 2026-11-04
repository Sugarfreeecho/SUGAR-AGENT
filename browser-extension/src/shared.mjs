export function loopbackUrl(raw, protocols = ['http:']) {
  const url = new URL(raw);
  if (!protocols.includes(url.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
      || url.username || url.password) throw new Error('仅支持本机 SugarAgent 地址');
  return url;
}
export function ordinaryTab(tab) {
  const url = tab.url || tab.pendingUrl || '';
  return !tab.incognito && (url === 'about:blank' || /^https?:\/\//i.test(url));
}

// Durable identity and volatile stream identity are separate namespaces.
export function eventKey(event, sessionId) {
  if (event.ephemeral) return `${sessionId}:live:${event.event_bus_epoch}:${event.event_bus_seq}`;
  const durable=event.runtime_seq ?? event.event_index ?? event.message_id;
  if(durable!==undefined && durable!==null)return `${sessionId}:fact:${durable}:${event.type}:${event.tool_call_id || ''}`;
  if(event.source_seq!=null)return `${sessionId}:source:${event.run_id || event.turn_id || ''}:${event.stream_seq ?? ''}:${event.source_seq}:${event.type}:${event.tool_call_id || ''}`;
  return `${sessionId}:live:${event.event_bus_epoch}:${event.event_bus_seq}:${event.type}:${event.tool_call_id || ''}`;
}
