import React from 'react';
import { Icon } from './Icon';
import { Popover } from './Popover';

export type Session = { id: string; name?: string; updated_at?: string; last_activity_at?: string; created_at?: string; pinned?: boolean; archived?: boolean };
export type SessionActionsProps = {
  session: Session; busy: boolean; onRename: (session: Session) => void; onDelete: (session: Session) => void;
  onUpdate: (session: Session, method: string, extra?: object) => Promise<boolean>;
};
export function SessionActions({ session, busy, onRename, onDelete, onUpdate }: SessionActionsProps) {
  return <Popover className="history-menu" label="会话操作" placement="bottom" align="end" role="menu" width={180} trigger={<Icon name="more" size={16} />}>
    {close => <><button className="menu-item" role="menuitem" disabled={busy} onClick={() => { close(); onRename(session); }}>改名</button><button className="menu-item" role="menuitem" disabled={busy} onClick={() => { close(); void onUpdate(session, 'session.update', { pinned: !session.pinned }); }}>{session.pinned ? '取消置顶' : '置顶'}</button><button className="menu-item" role="menuitem" disabled={busy} onClick={() => { close(); void onUpdate(session, 'session.archive', { archived: !session.archived }); }}>{session.archived ? '取消归档' : '归档'}</button><div className="menu-divider" /><button className="menu-item danger" role="menuitem" disabled={busy} onClick={() => { close(); onDelete(session); }}>删除</button></>}
  </Popover>;
}
