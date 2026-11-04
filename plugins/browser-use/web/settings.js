import {markup} from './view.js?v=20261031-native';
import {mountBrowserSettings} from './app.js?v=20261031-native';

export function mountSettings({root,settings}){
  root.classList.add('browser-settings');root.innerHTML=markup;
  root.querySelector('.eyebrow')?.remove();root.querySelector('h1')?.remove();
  root.querySelectorAll('button,a.button').forEach(node=>{
    if(node.classList.contains('step-heading')){node.classList.add('st-card-head');return;}
    node.classList.add('st-btn');
    if(node.classList.contains('text-button'))node.classList.add('text');
  });
  root.querySelectorAll('input').forEach(node=>node.classList.add('st-input'));
  root.querySelectorAll('.step,.connections').forEach(node=>node.classList.add('st-card'));
  root.querySelectorAll('.badge,.number').forEach(node=>node.classList.add('st-chip'));
  root.querySelectorAll('.check-row').forEach(row=>{
    row.classList.add('st-row');row.querySelector('strong').classList.add('st-label');row.querySelector('small').classList.add('st-hint');
    const controls=document.createElement('div');controls.className='st-ctl';
    [...row.children].slice(1).forEach(node=>controls.append(node));row.append(controls);
  });
  root.querySelector('.segmented').classList.add('st-seg');
  for(const browser of ['chrome','edge']){
    const button=root.querySelector('#'+browser);button.classList.remove('st-btn');
    button.classList.toggle('is-on',browser==='chrome');button.setAttribute('aria-pressed',String(browser==='chrome'));
  }
  root.querySelectorAll('.chevron').forEach(node=>{node.innerHTML='<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>';});
  root.querySelectorAll('.device-actions button').forEach(node=>node.classList.add('st-btn','sm'));
  const dispose=mountBrowserSettings(root,{native:true,onToast:settings.toast});
  return ()=>{dispose();root.replaceChildren();root.classList.remove('browser-settings');};
}
