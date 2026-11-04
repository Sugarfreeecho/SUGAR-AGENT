import React,{useState} from 'react';
import {Icon} from './Icon';
import {Dialog} from './Dialog';
import {SendModePicker,SteerMode} from './SendModePicker';
export type ComposerDraft={text:string;contexts:any[];uploads:{id:string;name:string;size:number}[];selectedSkills:string[];automatic?:boolean;browser_context?:any};
export type PendingMessage={clientId?:string;operationId?:string;runId?:string;content:string;status:string;draft:ComposerDraft;recovery?:boolean;recoveryMode?:SteerMode;images?:string[]};
export function PendingQueue({items,modes,disabled,onMode,onCancel,onEdit,onSend}:{items:PendingMessage[];modes:Record<string,SteerMode>;disabled:boolean;onMode:(id:string,mode:SteerMode)=>void;onCancel:(item:PendingMessage)=>Promise<void>;onEdit:(item:PendingMessage,draft:ComposerDraft,key:string)=>Promise<void>;onSend:(item:PendingMessage)=>Promise<void>}){
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[editing,setEditing]=useState<{item:PendingMessage;text:string;key:string}|null>(null);
  async function act(item:PendingMessage,action:()=>Promise<void>){
    setBusy(item.operationId!);setError('');try{await action();}catch(caught){setError((caught as Error).message);}finally{setBusy('');}
  }
  if(!items.length && !editing)return null;
  return <section className="pending-queue" aria-label="待发队列">
    {error && <p role="alert">{error}</p>}<div className="pending-queue-list" role="list">{items.map((item,index)=><div className="pending-queue-row" role="listitem" key={item.operationId || item.clientId} data-pending-operation={item.operationId}>
      <span className="pending-queue-index" title="Pending · 当前任务结束后执行，再按 Enter 插话">{index+1}</span>
      <div className="pending-queue-copy"><span title={item.content}>{item.content}</span></div>
      {!!item.draft.uploads.length && <span className="pending-queue-files" title={item.draft.uploads.map(row=>row.name).join('、')} aria-label={'附件 '+item.draft.uploads.length}><Icon name="attach" size={12}/>{item.draft.uploads.length}</span>}
      {(item.status==='sending' || item.recovery) && <small className="pending-queue-state" role="status" title={item.recovery?'转为插话的结果待确认，内容已保留':'正在提交…'}>{item.recovery?'待重试':'提交中'}</small>}
      <div className="pending-queue-actions"><button title="编辑待发消息" aria-label="编辑待发消息" disabled={disabled || !!busy || !item.operationId || !!item.recovery} onClick={()=>{setError('');setEditing({item,text:item.draft.text,key:'pending-edit-'+crypto.randomUUID()});}}><Icon name="edit" size={13}/></button>
        <SendModePicker value={item.recoveryMode || modes[item.operationId!] || 'append'} disabled={disabled || !!busy || !item.operationId || !!item.recovery} onChange={mode=>onMode(item.operationId!,mode)}/>
        <button title="立即插话" aria-label="立即插话" disabled={disabled || !!busy || !item.operationId} onClick={()=>void act(item,()=>onSend(item))}><Icon name="arrow" size={13}/></button>
        <button title="撤回待发消息" aria-label="撤回待发消息" disabled={disabled || !!busy || !item.operationId || !!item.recovery} onClick={()=>void act(item,()=>onCancel(item))}>×</button></div>
    </div>)}</div>
    {editing && <Dialog label="编辑待发消息" onClose={()=>{if(!busy){setEditing(null);setError('');}}}><form onSubmit={event=>{event.preventDefault();void act(editing.item,async()=>{await onEdit(editing.item,{...editing.item.draft,text:editing.text},editing.key);setEditing(null);});}}>
      <h2>编辑待发消息</h2><textarea aria-label="待发消息内容" autoFocus value={editing.text} onChange={event=>setEditing({...editing,text:event.target.value})}/>
      {!!editing.item.draft.uploads.length && <p className="secondary">保留附件：{editing.item.draft.uploads.map(row=>row.name).join('、')}</p>}
      {error && <p role="alert" className="dialog-error">{error}</p>}<div className="dialog-actions"><button type="button" disabled={!!busy} onClick={()=>setEditing(null)}>取消</button><button className="primary" disabled={!!busy || (!editing.text.trim() && !editing.item.draft.uploads.length && !editing.item.draft.contexts.length && !editing.item.draft.selectedSkills.length)}>保存并排队</button></div>
    </form></Dialog>}
  </section>;
}
