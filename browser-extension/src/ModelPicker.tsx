import React, { useState } from 'react';
import { Popover } from './Popover';
import { Icon } from './Icon';

export const effortOptions = [
  ['', 'default'], ['low', 'low'], ['medium', 'medium'], ['high', 'high'], ['xhigh', 'xhigh'], ['max', 'max'],
];
export const effortLabel = (value: string) => value || 'default';
export function ModelPicker({ models, value, effort, disabled, loading, error, onModel, onEffort, onReload }: {
  models: any[]; value: string; effort: string; disabled: boolean; loading: boolean; error: string;
  onModel: (value: string) => Promise<void>; onEffort: (value: string) => Promise<void>; onReload: () => void;
}) {
  const [search, setSearch] = useState('');
  const name = models.find(model => model.id === value)?.name || models.find(model => model.id === value)?.model || (value ? '当前模型' : '默认模型');
  const visibleModels = models.filter(model => `${model.name || ''} ${model.model || ''} ${model.id}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <Popover className="model-picker" label="模型" align="end" value={value} disabled={disabled} onOpen={() => setSearch('')} trigger={<><span className="model-name" title={name}>{loading ? '加载模型…' : name}</span><span className="model-effort">{effortLabel(effort)}</span><Icon name="down" size={12} /></>}>
    {close => <><div className="popover-heading">模型与思考</div>{error && <div className="menu-error"><span>{error}</span><button onClick={onReload} disabled={loading}>重试加载模型</button></div>}
      {models.length > 6 && <input className="menu-search" aria-label="搜索模型" value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索模型" />}
      <div className="model-options" role="group" aria-label="选择模型"><button className={!value ? 'selected' : ''} data-model-id="" aria-pressed={!value} disabled={loading || disabled} onClick={() => { close(); void onModel(''); }}><span>默认模型</span>{!value && <Icon name="check" size={13} />}</button>
      {visibleModels.map(model => <button key={model.id} className={model.id === value ? 'selected' : ''} data-model-id={model.id} aria-pressed={model.id === value} disabled={loading || disabled} onClick={() => { close(); void onModel(model.id); }}><span title={model.name || model.model || model.id}>{model.name || model.model || model.id}</span>{model.id === value && <Icon name="check" size={13} />}</button>)}
      {search && !visibleModels.length && <p className="menu-note">没有匹配的模型。</p>}
      {value && !models.some(model => model.id === value) && <p className="menu-note">当前模型未列出，可重新选择。</p>}</div>
      <div className="effort-section"><div className="popover-heading">思考强度</div><div className="effort-options" role="group" aria-label="思考强度">{effortOptions.map(([id, name]) => <button key={id} data-effort={id} aria-pressed={effort === id} disabled={disabled} onClick={() => { close(); void onEffort(id); }}><span>{name}</span>{effort === id && <Icon name="check" size={13} />}</button>)}</div></div>
    </>}
  </Popover>;
}
