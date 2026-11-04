import { ordinaryTab } from './shared.mjs';

export type BrowserPage = {
  tab_id: number; target_id: string; window_id: number; title: string; url: string; captured_at: string;
  document_id?: string; selection?: { text: string; frame_id: number; frame_url: string; truncated: boolean };
};
export type BrowserContext = { page: BrowserPage | null; status: string; reason?: string };

export async function readBrowserContext(options: { windowId?: number; tabId?: number; targetId?: string } = {}): Promise<BrowserContext> {
  try {
    const targets = await chrome.debugger.getTargets();
    let tabId = options.tabId;
    if (options.targetId) tabId = targets.find(target => target.id === options.targetId)?.tabId;
    if (options.targetId && tabId === undefined) return {page:null,status:'unavailable',reason:'tab_closed'};
    const windowId = options.windowId ?? (await chrome.windows.getLastFocused({windowTypes:['normal']})).id;
    const tab = tabId === undefined ? (await chrome.tabs.query({active:true,...(windowId === undefined ? {} : {windowId})}))[0] : await chrome.tabs.get(tabId);
    if (!tab?.id || !ordinaryTab(tab)) return {page:null,status:'unavailable',reason:'no_active_web_page'};
    const target = targets.find(item => item.tabId === tab.id && item.type === 'page');
    if (!target?.id) return {page:null,status:'unavailable',reason:'page_target_unavailable'};
    const page: BrowserPage = {tab_id:tab.id,target_id:target.id,window_id:tab.windowId,title:(tab.title || '').slice(0,500),url:tab.url || tab.pendingUrl || '',captured_at:new Date().toISOString()};
    try {
      const frames = await chrome.scripting.executeScript({target:{tabId:tab.id,allFrames:true},func:()=>{
        const text=window.getSelection()?.toString() || '';
        return {text:text.slice(0,8000),truncated:text.length>8000,url:location.href,title:document.title,focused:document.hasFocus()};
      }});
      const main = frames.find(frame => frame.frameId === 0);
      if(main?.result) {page.url=main.result.url;page.title=main.result.title.slice(0,500);page.document_id=main.documentId;}
      const selection = frames.find(frame => frame.result?.text && frame.result.focused) || frames.find(frame => frame.result?.text);
      if(selection?.result)page.selection={text:selection.result.text,frame_id:selection.frameId,frame_url:selection.result.url,truncated:selection.result.truncated};
    } catch { /* Restricted documents still have a usable tab identity. */ }
    return {page,status:'available'};
  } catch { return {page:null,status:'unavailable',reason:'browser_context_unavailable'}; }
}
