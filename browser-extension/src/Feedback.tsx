import React from 'react';
import { Icon } from './Icon';
import { Popover } from './Popover';
export function Feedback({ error, modelError, loading, onDismiss, onReload }: {
  error: string; modelError: string; loading: boolean; onDismiss: () => void; onReload: () => void;
}) {
  if (!error && !modelError) return null;
  return <Popover className="feedback-control" triggerClassName="feedback-trigger" label="查看问题" role="alert" autoOpenKey={error || modelError} trigger={<Icon name="alert" size={16} />}>
    {close => <><div className="popover-heading">遇到问题</div><div className="feedback-message">{error || modelError}</div><div className="feedback-actions">{modelError && <button disabled={loading} onClick={onReload}>重试加载模型</button>}<button aria-label="关闭提示" onClick={() => { close(); onDismiss(); }}>关闭</button></div></>}
  </Popover>;
}
