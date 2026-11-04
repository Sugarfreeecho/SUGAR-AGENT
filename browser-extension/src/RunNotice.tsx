import React from 'react';
import {Icon} from './Icon';

export function RunNotice({block}:{block:any}){
  const content=String(block.content || ''),detail=String(block.detail || '');
  const brief=content.split('\n')[0].slice(0,160),expandable=!!detail || brief!==content;
  const className='run-notice '+(block.outcome || 'failed'),role=block.outcome==='interrupted'?'status':'alert';
  const summary=<><Icon name="alert" size={13}/><span><strong>{block.title}</strong><span>{brief}</span></span>{expandable && <span className="chevron entry-chevron"><Icon name="chevron" size={12}/></span>}</>;
  if(!expandable)return <div className={className}><div className="run-notice-summary" role={role}>{summary}</div></div>;
  return <details className={className}>
    <summary className="run-notice-summary" role={role}>{summary}</summary>
    <pre>{[content,detail].filter(Boolean).join('\n\n')}</pre>
  </details>;
}
