import React, { useState } from 'react';
import { Popover } from './Popover';
import { Icon } from './Icon';
export const folderName = (path: string) => path.replace(/[\\/]+$/, '').split(/[\\/]/).at(-1) || path;
export function WorkspacePicker({ value, workspaces, disabled, loading, error, onOpen, onSelect, onBrowse, onValidate }: {
  value: string; workspaces: { path: string; name: string }[]; disabled: boolean; loading: boolean; error: string;
  onOpen: () => void; onSelect: (path: string) => Promise<boolean>; onBrowse: () => Promise<void>; onValidate: (path: string) => Promise<boolean>;
}) {
  const [search, setSearch] = useState(''), [manual, setManual] = useState(false), [path, setPath] = useState('');
  const visible = workspaces.filter(item => `${item.name} ${item.path}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <Popover className="workspace-picker" label="选择工作区" disabled={disabled} onOpen={() => { setSearch(''); setManual(false); onOpen(); }} trigger={<><Icon name="folder" size={15} /><span title={value}>{value ? folderName(value) : '选择工作区'}</span><Icon name="down" size={12} /></>}>
    {close => <><div className="popover-heading">工作区</div>{error && <p className="menu-error" role="alert">{error}</p>}{manual ? <form className="workspace-form" onSubmit={event => { event.preventDefault(); void onValidate(path.trim()).then(ok => { if (ok) close(); }); }}><label>目录路径<input autoFocus aria-label="工作区路径" value={path} onChange={event => setPath(event.target.value)} required placeholder="输入已存在的绝对目录" /></label><div className="workspace-form-actions"><button type="button" disabled={loading} onClick={() => setManual(false)}>返回</button><button className="primary" disabled={loading || !path.trim()}>{loading ? '正在验证…' : '使用此目录'}</button></div></form> : <><input className="menu-search" aria-label="搜索工作区" value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索工作区" />
      <div className="workspace-options">{visible.map(item => <button key={item.path} data-workspace={item.path} className={item.path === value ? 'selected' : ''} disabled={loading} onClick={() => { close(); void onSelect(item.path); }}><Icon name="folder" size={15} /><span><strong title={item.name}>{item.name}</strong><small title={item.path}>{item.path}</small></span>{item.path === value && <Icon name="check" size={13} />}</button>)}</div>
      {search && !visible.length && <p className="menu-note">没有匹配的工作区。</p>}
      {!loading && !workspaces.length && <p className="menu-note">暂无最近工作区。</p>}
      <div className="menu-divider" /><button className="menu-item" disabled={loading} onClick={() => { close(); void onBrowse(); }}><Icon name="folder" size={15} />选择其他文件夹…</button><button className="menu-item" disabled={loading} onClick={() => { setManual(true); setPath(value); }}>输入目录路径…</button></>}
    </>}
  </Popover>;
}
