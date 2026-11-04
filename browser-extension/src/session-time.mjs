export function activityTimestamp(session) {
  const raw = session.last_activity_at || session.updated_at || session.created_at || '';
  const timestamp = Date.parse(String(raw));
  return Number.isFinite(timestamp) ? timestamp : Number(raw) > 0 ? Number(raw) : 0;
}

export function relativeSessionTime(session, now = Date.now(), english = false) {
  const timestamp = activityTimestamp(session); if (!timestamp) return '';
  const elapsed = Math.max(0, now - timestamp), minute = 60000, day = 86400000;
  if (elapsed < minute) return english ? 'now' : '刚刚';
  const units = [[minute, 60 * minute, '分钟', 'm'], [60 * minute, day, '小时', 'h'], [day, 30 * day, '天', 'd'], [30 * day, 365 * day, '个月', 'mo'], [365 * day, Infinity, '年', 'y']];
  const [size, , zh, en] = units.find(([, end]) => elapsed < end);
  return Math.floor(elapsed / size) + (english ? en : zh);
}
