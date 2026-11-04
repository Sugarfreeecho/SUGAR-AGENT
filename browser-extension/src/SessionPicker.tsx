import React, { useEffect, useState } from 'react';
import { Icon } from './Icon';
import { Popover } from './Popover';
import { SessionActions, Session, SessionActionsProps } from './SessionActions';
import { activityTimestamp, relativeSessionTime } from './session-time.mjs';

export function SessionPicker({ title, value, sessions, onOpen, onSelect, onManage, busy, onRename, onDelete, onUpdate }: {
  title: string; value: string; sessions: Session[]; onOpen: () => void; onSelect: (id: string) => Promise<void>; onManage: () => void;
} & Omit<SessionActionsProps, 'session'>) {
  const [search, setSearch] = useState('');
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const rows = sessions.filter(session => !session.archived && (session.name || '').toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned));
  return <Popover className="session-picker" triggerClassName="session-title" label="会话历史" placement="bottom" onOpen={() => { setSearch(''); onOpen(); }} trigger={<><span>{title}</span><Icon name="down" size={12} /></>}>
    {close => <><div className="popover-heading">会话</div><input className="menu-search" aria-label="搜索会话" placeholder="搜索会话" value={search} onChange={event => setSearch(event.target.value)} /><div className="session-options menu-scroll">{rows.map(session => {
      const timestamp = activityTimestamp(session);
      return <div key={session.id} data-session-id={session.id} className={'session-picker-row' + (session.id === value ? ' selected' : '')}><button className="history-open session-row-open" aria-pressed={session.id === value} onClick={() => { close(); void onSelect(session.id); }}><strong title={session.name}>{session.pinned ? '· ' : ''}{session.name || '未命名会话'}</strong>{session.id === value && <Icon name="check" size={12} />}{timestamp > 0 && <time dateTime={new Date(timestamp).toISOString()} title={new Date(timestamp).toLocaleString()}>{relativeSessionTime(session, now, document.documentElement.lang.startsWith('en'))}</time>}</button><SessionActions session={session} busy={busy} onRename={item => { close(); onRename(item); }} onDelete={item => { close(); onDelete(item); }} onUpdate={onUpdate} /></div>;
    })}{!rows.length && <p className="menu-note">没有匹配的会话。</p>}</div><div className="menu-divider" /><button className="menu-item" onClick={() => { close(); onManage(); }}><Icon name="history" size={15} />管理会话</button></>}
  </Popover>;
}
