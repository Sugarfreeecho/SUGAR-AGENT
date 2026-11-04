import React, {useState} from 'react';
import { Icon } from './Icon';
import { Popover } from './Popover';

export type SkillChoice={name:string;description:string;enabled:boolean};
export function AttachmentMenu({onPage,onFile,onTabs,disabled=false,skills,selectedSkills,skillsLoading,skillsError,onSkillsOpen,onSkillsChange}:{
  onPage:()=>void;onFile:()=>void;onTabs:()=>void;disabled?:boolean;
  skills:SkillChoice[];selectedSkills:string[];skillsLoading:boolean;skillsError:string;onSkillsOpen:()=>void;onSkillsChange:(names:string[])=>void;
}) {
  const [choosing,setChoosing]=useState(false),[search,setSearch]=useState('');
  const query=search.trim().toLocaleLowerCase();
  const rows=skills.filter(skill=>(skill.name+' '+skill.description).toLocaleLowerCase().includes(query));
  return <Popover className={'attachment-menu'+(choosing ? ' choosing-skills' : '')} label="附加资料" role="menu" width={choosing ? 280 : 220} disabled={disabled}
    onOpen={()=>{setChoosing(false);setSearch('');}} trigger={<Icon name="plus" size={20}/>}>
    {close=>choosing ? <>
      <div className="skill-menu-heading"><button className="skill-menu-back" onClick={()=>setChoosing(false)}><Icon name="chevron" size={12}/><span>返回</span></button><strong>选择 Skill</strong><small>{selectedSkills.length}/32</small></div>
      <input className="menu-search" aria-label="搜索 Skill" placeholder="搜索 Skill" autoFocus value={search} onChange={event=>setSearch(event.target.value)} onKeyDown={event=>{
        if(!['ArrowDown','ArrowUp'].includes(event.key))return;
        const options=event.currentTarget.closest('[data-menu-id]')?.querySelectorAll<HTMLButtonElement>('[role="menuitemcheckbox"]:not(:disabled)');
        if(options?.length){event.preventDefault();options[event.key==='ArrowDown' ? 0 : options.length-1].focus();}
      }}/>
      {skillsError && <div className="menu-error" role="alert"><span>{skillsError}</span><button onClick={onSkillsOpen}>重试</button></div>}
      {skillsLoading && <p className="menu-note">正在读取 Skill…</p>}
      <div className="skill-options menu-scroll">{rows.map(skill=>{
        const selected=selectedSkills.includes(skill.name);
        return <button key={skill.name} className={'menu-item skill-option'+(selected ? ' selected' : '')} role="menuitemcheckbox" aria-checked={selected}
          disabled={!selected && (!skill.enabled || selectedSkills.length>=32)} title={skill.description || skill.name}
          onClick={()=>onSkillsChange(selected ? selectedSkills.filter(name=>name!==skill.name) : [...selectedSkills,skill.name])}>
          <span className="skill-option-check">{selected && <Icon name="check" size={13}/>}</span><span><strong>{skill.name}</strong><small>{skill.description || '暂无描述'}</small>{!skill.enabled && <small>已停用</small>}</span>
        </button>;
      })}</div>
      {!skillsLoading && !skillsError && !rows.length && <p className="menu-note">{skills.length ? '没有匹配的 Skill。' : '暂无可用 Skill，请先在主程序添加。'}</p>}
      <div className="menu-divider"/><div className="skill-menu-actions"><button disabled={!selectedSkills.length} onClick={()=>onSkillsChange([])}>清空选择</button><button onClick={close}>完成</button></div>
    </> : <>
      <div className="popover-heading">添加资料</div>
      <button className="menu-item" role="menuitem" onClick={()=>{setChoosing(true);onSkillsOpen();}}><Icon name="skill" size={15}/><span>选择 Skill</span>{!!selectedSkills.length && <small aria-hidden="true">{selectedSkills.length}</small>}</button>
      <button className="menu-item" role="menuitem" onClick={()=>{close();onFile();}}><Icon name="attach" size={15}/><span>附加文件</span></button>
      <button className="menu-item" role="menuitem" onClick={()=>{close();onPage();}}><Icon name="globe" size={15}/><span>附加当前网页</span></button>
      <button className="menu-item" role="menuitem" onClick={()=>{close();onTabs();}}><Icon name="tabs" size={15}/><span>选择标签页</span></button>
    </>}
  </Popover>;
}
