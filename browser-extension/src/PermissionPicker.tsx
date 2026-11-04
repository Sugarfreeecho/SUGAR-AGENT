import React, { useState } from 'react';
import { Popover } from './Popover';
import { Icon } from './Icon';
import { Dialog } from './Dialog';

const modes = [
  { id: 'ask_for_approval', icon: 'permission-ask', label: '请求批准', description: '操作前由你确认' },
  { id: 'approve_for_me', icon: 'permission-auto', label: '替我审批', description: '由安全审查器评估操作' },
  { id: 'full_access', icon: 'permission-full', label: '完全访问', description: '普通操作不逐项询问，保留安全红线' },
];
export function PermissionPicker({ status, error, loading, saving, onOpen, onChange }: {
  status: any; error: string; loading: boolean; saving: boolean; onOpen: () => void; onChange: (mode: string, confirmed?: boolean) => Promise<boolean>;
}) {
  const [confirming, setConfirming] = useState(false), [failure, setFailure] = useState('');
  const mode = modes.find(item => item.id === status?.mode);
  return <><Popover label="权限选择" className={'permission-picker permission-' + (mode?.id || 'unknown')} disabled={saving} onOpen={onOpen} width={270}
    trigger={<><Icon name={mode?.icon || 'permission-ask'} size={15} strokeWidth={1.8} /><span>{mode?.label || '权限'}</span><Icon name="down" size={11} /></>}>
    {close => <><div className="popover-heading">权限 · 对所有会话生效</div>
      {error && <div className="menu-error" role="alert">{error}<button onClick={onOpen}>重试</button></div>}
      {loading && !status && <p className="menu-note">正在读取权限…</p>}
      {status?.security_enabled === false && <p className="menu-note">安全控制已在主程序关闭</p>}
      {modes.map(item => <button key={item.id} data-permission-mode={item.id} className={'menu-item permission-option' + (status?.mode === item.id ? ' selected' : '')}
        disabled={!status?.can_change || !status?.available_modes?.[item.id] || saving}
        aria-pressed={status?.mode === item.id} onClick={() => {
          if (item.id === status?.mode) { close(); return; }
          if (item.id === 'full_access') { close(); setFailure(''); setConfirming(true); }
          else void onChange(item.id).then(ok => { if (ok) close(); });
        }}><Icon name={item.icon} size={16} strokeWidth={1.8} /><span><strong>{item.label}</strong><small>{item.description}</small></span>{status?.mode === item.id && <Icon name="check" size={14} />}</button>)}
      {status && !status.can_change && <p className="menu-note">此连接只能查看权限，请在主程序修改。</p>}
    </>}
  </Popover>{confirming && <Dialog label="开启完全访问" onClose={() => { if (!saving) setConfirming(false); }}>
    <h2>开启完全访问</h2><p>普通文件、工作区内删除、Shell 和网络操作将不再逐项征求同意；高危系统命令仍需人工确认，安全红线保留。</p>
    <p>此设置对所有会话生效，重启后仍保留，直到手动切回“请求批准”。</p>
    {(failure || error) && <p className="dialog-error" role="alert">{error || failure}</p>}
    <div className="dialog-actions"><button disabled={saving} onClick={() => setConfirming(false)}>取消</button><button className="primary" disabled={saving} onClick={() => void onChange('full_access', true).then(ok => { if (ok) setConfirming(false); else setFailure('切换失败，请重试。'); })}>{saving ? '正在保存…' : '确认开启'}</button></div>
  </Dialog>}</>;
}
