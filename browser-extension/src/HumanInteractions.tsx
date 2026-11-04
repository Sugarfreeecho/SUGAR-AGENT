import React, { useEffect, useRef, useState } from 'react';
import { extension } from './api';
import { RichMarkdown as Markdown } from './Markdown';
import { AttachmentImage, MediaSession } from './media';
import { approvalChoices, humanKey, questionAnswers, questionError } from './human.mjs';

type Record = {[key:string]:any};
type Draft = {answers:{[key:string]:any};step:number;review:boolean;reason:string;rejecting:boolean};
const emptyDraft = ():Draft => ({answers:{},step:0,review:false,reason:'',rejecting:false});
const labels:{[key:string]:string}={resolved:'已处理',cancelled:'已取消',expired:'已过期',allow_once:'已允许本次操作',allow_session:'已允许当前任务内的同类操作',allow_always:'已保存长期规则',allow_external_workspace:'已允许后续目录处理',allow_external_workspace_once:'已允许本次目录处理',deny:'已拒绝执行'};

export function HumanCard({record, onUpdate, onRefresh}: {record:Record;onUpdate:(record:Record)=>void;onRefresh:()=>void}) {
  const question = record.kind === 'question', pending = record.status === 'pending';
  const [draft,setDraft] = useState<Draft>(emptyDraft), [ready,setReady]=useState(false), [busy,setBusy]=useState(''), [error,setError]=useState('');
  const lock=useRef(false), alive=useRef(true), current=useRef(record);current.current=record;
  const draftKey='sugar.human.'+humanKey(record)+'.'+(record.request_version || 1);
  useEffect(()=>{alive.current=true;let disposed=false;
    void chrome.storage.local.get(draftKey).then(saved=>{if(!disposed){setDraft({...emptyDraft(),...saved[draftKey]});setReady(true);}}).catch(()=>{if(!disposed)setReady(true);});
    return()=>{disposed=true;alive.current=false;};
  },[draftKey]);
  useEffect(()=>{
    if(!pending){void chrome.storage.local.remove(draftKey);return;}
    if(!ready)return;
    void chrome.storage.local.set({[draftKey]:draft});
  },[draft,draftKey,pending,ready]);
  const patch=(value:Partial<Draft>)=>setDraft(previous=>({...previous,...value}));
  async function act(operation:string,extra:Record={}) {
    if(lock.current || current.current.status!=='pending')return;
    lock.current=true;setBusy(operation);setError('');
    try{
      const path=operation==='analyze'?'/approvals/analyze':question?'/questions/'+operation:'/approvals/resolve';
      const result=await extension({type:'api',path:'/api/browser/v1'+path,body:{session_id:record.session_id,...(question?{interaction_id:record.interaction_id}:{approval_id:record.approval_id}),request_digest:record.request_digest,...extra}});
      const updated=result.approval || result.interaction;
      if(updated){if(alive.current)onUpdate({...record,...updated,_sidebarHandled:true});}
      else if(result.analysis){if(alive.current)onUpdate({...record,analysis:result.analysis});}
      else throw new Error('后端未返回处理结果，请刷新卡片重试。');
      if(operation!=='analyze')void chrome.storage.local.remove(draftKey);
      if(alive.current)onRefresh();
    }catch(caught){if(alive.current){setError((caught as Error).message);onRefresh();}}
    finally{lock.current=false;if(alive.current)setBusy('');}
  }
  const answers=questionAnswers(record,draft);
  function submit(){
    const invalid=(record.questions || []).findIndex((q:Record)=>questionError(q,draft.answers[q.question_id]));
    if(invalid>=0){patch({step:invalid,review:false});setError(questionError(record.questions[invalid],draft.answers[record.questions[invalid].question_id]));return;}
    void act('resolve',{answers});
  }
  const title=question?'需要你的回答':record.title || '需要操作审批';
  const terminalSummary=question?(record.status==='resolved'?'已回答':labels[record.status]):record.status==='resolved'?labels[record.decision] || '已处理':labels[record.status];
  function answered(){return <div className="human-answer-summary">{(record.questions || []).map((q:Record)=>{
    const a=(record.answers || answers).find((item:Record)=>item.question_id===q.question_id) || {};
    const selected=q.options?.filter((option:Record)=>a.selected_option_ids?.includes(option.option_id)).map((option:Record)=>option.label) || a.selected_labels || [];
    return <div key={q.question_id}><strong>{q.header}</strong><span>{a.skipped?'未回答':[...selected,a.other_text].filter(Boolean).join('、')}</span>{a.notes && <small>{a.notes}</small>}</div>;
  })}</div>;}
  if(!pending)return <section className="human-card human-terminal" data-human-id={record.approval_id || record.interaction_id} data-status={record.status}><details><summary>{terminalSummary || '已处理'}<span>{title}</span></summary>{question?answered():<><p>{record.message || record.subtitle}</p>{record.rejection_reason && <p>拒绝原因：{record.rejection_reason}</p>}{record.reason && <p>{record.reason}</p>}</>}</details></section>;
  const q=record.questions?.[Math.min(draft.step,Math.max(0,(record.questions?.length || 1)-1))], answer=draft.answers[q?.question_id] || {};
  function changeAnswer(value:Record){patch({answers:{...draft.answers,[q.question_id]:{...answer,...value}}});setError('');}
  function next(){const message=questionError(q,answer);if(message){setError(message);return;}setError('');if(draft.step<record.questions.length-1)patch({step:draft.step+1});else patch({review:true});}
  const analysis=record.analysis;
  return <MediaSession.Provider value={record.session_id}><section className={'human-card '+(question?'human-question':'human-approval')+(record.force_approval?' is-danger':'')} aria-label={question?'Agent 提问':'操作审批'} data-human-id={record.approval_id || record.interaction_id} data-status="pending">
    <header><strong title={title}>{title}</strong><span>{question?'待回答':'待审批'}</span></header>
    {!ready || !record.request_digest?<p className="secondary">正在读取交互内容…</p>:question ? <>
      {draft.review ? <><h3>确认回答</h3>{answered()}<button className="human-edit" disabled={!!busy} onClick={()=>patch({review:false})}>返回修改</button></> : q ? <fieldset disabled={!!busy}><div className="human-question-heading"><strong>{q.header}</strong><span>{draft.step+1} / {record.questions.length} · {q.multi_select?'可多选':'单选'}</span></div><Markdown text={q.question} />
        {!!q.images?.length && <div className="human-images">{q.images.map((image:Record,index:number)=><figure key={index}><AttachmentImage identity={image.attachment?.attachmentId || String(index)} source={`question-image:${record.interaction_id}/${q.question_id}/${index}`} alt={image.alt} />{image.caption && <figcaption>{image.caption}</figcaption>}</figure>)}</div>}
        <div className="human-options">{(q.options || []).map((option:Record)=><div className="human-option" key={option.option_id}><label><input type={q.multi_select?'checkbox':'radio'} name={draftKey+q.question_id} checked={!!answer.selected?.includes(option.option_id)} onChange={()=>{
          const selected=q.multi_select?(answer.selected?.includes(option.option_id)?answer.selected.filter((id:string)=>id!==option.option_id):[...(answer.selected || []),option.option_id]):[option.option_id];
          changeAnswer({selected,skipped:false,...(!q.multi_select?{other:false}:{})});
        }} /><span><strong>{option.label}</strong><small>{option.description}</small></span></label>{option.preview && <details><summary>查看预览</summary><Markdown text={option.preview} /></details>}</div>)}
        <div className="human-option"><label><input type={q.multi_select?'checkbox':'radio'} name={draftKey+q.question_id} checked={!!answer.other} onChange={()=>changeAnswer({other:!answer.other,skipped:false,...(!q.multi_select?{selected:[]}:{})})} /><span>其他答案</span></label>{answer.other && <textarea aria-label="其他答案" maxLength={2000} value={answer.text || ''} onChange={event=>changeAnswer({text:event.target.value,skipped:false})} placeholder="输入你的答案…" />}</div></div>
        <details className="human-notes"><summary>补充说明（可选）</summary><textarea aria-label="补充说明" maxLength={2000} value={answer.notes || ''} onChange={event=>changeAnswer({notes:event.target.value,skipped:false})} /></details>
        {answer.skipped && <p className="secondary">已跳过当前题目</p>}
      </fieldset>:<p role="alert">提问内容不完整，请刷新卡片。</p>}
      <div className="human-actions"><button disabled={!!busy} onClick={()=>void act('cancel')}>取消提问</button><span className="human-actions-spacer" />{draft.review?<button className="primary" disabled={!!busy} onClick={submit}>{busy==='resolve'?'正在提交…':'提交答案'}</button>:<>{draft.step>0 && <button disabled={!!busy} onClick={()=>{setError('');patch({step:draft.step-1});}}>上一题</button>}<button disabled={!!busy || !q} onClick={()=>{changeAnswer({skipped:true,selected:[],other:false,text:'',notes:''});if(draft.step<record.questions.length-1)patch({step:draft.step+1});else patch({review:true});}}>不回答</button><button className="primary" disabled={!!busy || !q} onClick={next}>{draft.step<record.questions.length-1?'下一题':'确认回答'}</button></>}</div>
    </> : <>
      {record.subtitle && <p className="human-subtitle">{record.subtitle}</p>}<Markdown text={record.message || '是否允许 Agent 执行此操作？'} />
      {record.tool && <div className="human-tool">工具 <code>{record.tool}</code></div>}{record.consequence && <p className="human-consequence">{record.consequence}</p>}
      {!!record.required_dirs?.length && <div className="human-resource">{record.required_dirs.map((path:string)=><code key={path}>{path}</code>)}</div>}
      {record.egress_intent && record.egress_intent!=='none' && <p className="human-subtitle">{record.egress_intent==='upload'?'数据发送':'网络访问'}：{record.destinations?.map((item:Record)=>item.host+(item.port?':'+item.port:'')).join('、') || '目标由运行时确定'}{record.data_sources?.length?' · 数据来源：'+record.data_sources.join('、'):''}</p>}
      {record.rule_pattern && record.allow_always_available && !record.force_approval && <p className="human-scope">长期规则：<code>{record.rule_pattern}</code></p>}
      {record.external_workspace_grantable && !record.force_approval && <p className="human-scope">此处只确认工作区外处理权限，工具操作会另行审批。</p>}
      {analysis && <div className="human-analysis" role="status"><strong>{analysis.available===false?'分析暂不可用':analysis.recommendation==='allow'?'分析建议：允许':'分析建议：拒绝'}{analysis.risk?' · '+analysis.risk:''}</strong>{[['拦截原因',analysis.intercept_reason],['命令风险',analysis.risk_analysis],['命令目的',analysis.command_purpose],['说明',analysis.reason]].filter(([,text])=>text).map(([label,text])=><p key={label}><span>{label}</span>{text}</p>)}<small>分析仅供参考，审批仍由你决定。</small></div>}
      {draft.rejecting && <label className="human-rejection">拒绝原因<textarea aria-label="拒绝原因" maxLength={2000} value={draft.reason} onChange={event=>patch({reason:event.target.value})} disabled={!!busy} placeholder="可说明原因，让 Agent 调整后续操作" /></label>}
      <div className="human-actions"><button disabled={!!busy} onClick={()=>void act('analyze')}>{busy==='analyze'?'正在分析…':'替我分析'}</button><button disabled={!!busy} onClick={()=>draft.rejecting?void act('resolve',{decision:'deny',rejection_reason:draft.reason.trim()}):patch({rejecting:true,reason:draft.reason || record.rejection_reason_suggestion || ''})}>{draft.rejecting?'确认拒绝':'拒绝执行'}</button>{draft.rejecting && <button disabled={!!busy} onClick={()=>patch({rejecting:false})}>返回</button>}{approvalChoices(record).slice().reverse().map((choice:any)=><button key={choice.decision} disabled={!!busy} className={choice.decision.endsWith('once')?'primary':''} onClick={()=>void act('resolve',{decision:choice.decision})}>{choice.label}</button>)}</div>
    </>}
    {error && <div className="human-error" role="alert">{error}<button disabled={!!busy} onClick={onRefresh}>刷新卡片</button></div>}
  </section></MediaSession.Provider>;
}
