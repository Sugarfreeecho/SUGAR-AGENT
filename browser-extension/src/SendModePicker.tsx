import React from 'react';
import {Popover} from './Popover';
import {Icon} from './Icon';
export type SteerMode='append'|'interrupt';
export type SendMode='pending'|SteerMode;
const modes=[
  {id:'append',label:'Steer append',icon:'plus',description:'在本轮安全边界追加，不打断当前生成'},
  {id:'interrupt',label:'Steer interrupt',icon:'interrupt',description:'中断当前生成并续接；不可中断操作会等待安全结束'},
];
export function SendModePicker({value,disabled,onChange}:{value:SteerMode;disabled:boolean;onChange:(mode:SteerMode)=>void}){
  return <Popover className="send-mode-picker" label="插话方式" value={value} role="menu" align="end" width={276} disabled={disabled}
    trigger={<><Icon name={modes.find(row=>row.id===value)!.icon} size={14}/><Icon name="down" size={10}/></>}>
    {close=><><div className="popover-heading">插话方式</div>{modes.map(mode=><button key={mode.id} className={'menu-item send-mode-option'+(value===mode.id?' selected':'')} role="menuitemradio" aria-checked={value===mode.id} data-send-mode={mode.id} onClick={()=>{onChange(mode.id as SteerMode);close();}}>
      <Icon name={mode.icon} size={15}/><span><strong>{mode.label}</strong><small>{mode.description}</small></span>{value===mode.id && <Icon name="check" size={13}/>}</button>)}</>}
  </Popover>;
}
