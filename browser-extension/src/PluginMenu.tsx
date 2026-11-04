import React from 'react';
import { Icon } from './Icon';
import { Popover } from './Popover';
export function PluginMenu({ plugins, loading, error, onOpen, onManage }: {
  plugins: any[]; loading: boolean; error: string; onOpen: () => void; onManage: (id?: string) => void;
}) {
  return <Popover className="plugin-picker" label="插件" onOpen={onOpen} trigger={<><Icon name="plugin" size={15} /><span>插件</span></>}>
    {close => <><div className="popover-heading">已安装插件</div><p className="menu-note">启用状态与主程序保持一致。</p>{loading && <p className="menu-note">正在读取插件…</p>}{error && <div className="menu-error"><span>{error}</span><button onClick={onOpen}>重试</button></div>}
      <div className="plugin-options">{plugins.map(plugin => <button key={plugin.id} onClick={() => { close(); onManage(plugin.id); }}><Icon name="plugin" size={15} /><span><strong title={plugin.name}>{plugin.name}</strong><small title={plugin.description}>{plugin.description}</small></span><small>{plugin.enabled ? plugin.loaded ? '已启用' : '待加载' : '未启用'}</small><Icon name="external" size={12} /></button>)}</div>
      {!loading && !error && !plugins.length && <p className="menu-note">主程序中暂无可管理的插件。</p>}<div className="menu-divider" /><button className="menu-item" onClick={() => { close(); onManage(); }}>管理插件 <Icon name="external" size={13} /></button>
    </>}
  </Popover>;
}
