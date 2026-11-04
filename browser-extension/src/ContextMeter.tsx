import React from 'react';
import { Popover } from './Popover';

export function ContextMeter({ usage, loading, error, onOpen }: { usage: any; loading: boolean; error: string; onOpen: () => void }) {
  const used = Number(usage?.estimated), limit = Number(usage?.threshold);
  const known = usage?.estimated != null && Number.isFinite(used) && used >= 0 && limit > 0;
  const percent = known ? Math.round(used / limit * 100) : null;
  const breakdown = usage?.breakdown;
  const lanes = breakdown ? [
    ['系统提示', breakdown.system_tokens ?? breakdown.system_prompt ?? breakdown.system],
    ['工具', breakdown.tools_tokens ?? breakdown.tools],
    ['对话', breakdown.message_tokens ?? breakdown.messages ?? breakdown.conversation],
  ] as const : [];
  return <Popover label="上下文使用占比" className="context-meter" onOpen={onOpen} width={245} align="end"
    trigger={<><svg width="14" height="14" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" opacity=".2" strokeWidth="2" /><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray={`${known ? Math.min(100, percent!) * .44 : 0} 44`} transform="rotate(-90 10 10)" /></svg><span>{percent === null ? '—' : percent + '%'}</span></>}>
    {() => <><div className="popover-heading">上下文使用量</div><div className="context-total">{known ? `${used.toLocaleString()} / ${limit.toLocaleString()} tokens · ${percent}%` : '暂无用量数据'}</div>
      {known && <progress max={limit} value={used} />}
      {usage?.pending_recalculation || usage?.stale ? <p className="menu-note">等待重新估算</p> : null}
      {lanes.length > 0 && <dl className="context-breakdown">{lanes.filter(([, value]) => typeof value === 'number').map(([name, value]) => <React.Fragment key={name}><dt>{name}</dt><dd>~{Number(value).toLocaleString()}</dd></React.Fragment>)}</dl>}
      {loading && <p className="menu-note">正在更新…</p>}{error && <p className="menu-error" role="alert">{error}</p>}
      <p className="menu-note">与主程序采用相同的 token 统计口径。</p><button className="menu-item" disabled={loading} onClick={onOpen}>刷新用量</button>
    </>}
  </Popover>;
}
