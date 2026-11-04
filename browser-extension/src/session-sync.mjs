export function mergeSessionMetadata(rows, message) {
  const id = message.session_id;
  if (!id || message.session?.id && message.session.id !== id) return rows;
  if (message.deleted) return rows.filter(row => row.id !== id);
  if (message.session?.is_subagent) return rows.filter(row => row.id !== id);
  const previous = rows.find(row => row.id === id);
  const next = {...previous,...message.session,id};
  return previous ? rows.map(row => row.id === id ? next : row) : [next,...rows];
}

export function latestPermission(snapshot, live) {
  if (!live) return snapshot;
  // Epoch seconds are emitted by the main application. Preserve a newer live
  // change when a slower snapshot or write receipt arrives afterwards.
  const liveTime = Number(live.updated_at), snapshotTime = Number(snapshot?.updated_at);
  if (Number.isFinite(snapshotTime) && Number.isFinite(liveTime) && liveTime < snapshotTime) return snapshot;
  return {...snapshot,...live,...(snapshot?.can_change !== undefined ? {can_change:snapshot.can_change} : {})};
}
