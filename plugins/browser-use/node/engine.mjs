import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createConnection } from '@playwright/mcp';

const require = createRequire(import.meta.url);
const { Client, ListRootsRequestSchema } = require('playwright-core/lib/utilsBundle');
const { chromium } = require('playwright');

export const ALLOWED_TOOLS = new Set([
  'browser_get_context',
  'browser_tabs', 'browser_navigate', 'browser_navigate_back', 'browser_snapshot',
  'browser_take_screenshot', 'browser_click', 'browser_type', 'browser_press_key',
  'browser_hover', 'browser_drag', 'browser_select_option', 'browser_fill_form',
  'browser_file_upload', 'browser_handle_dialog', 'browser_wait_for', 'browser_find',
  'browser_mouse_click_xy', 'browser_mouse_move_xy', 'browser_mouse_drag_xy',
  'browser_mouse_wheel',
]);
const READ_TOOLS = new Set(['browser_get_context', 'browser_snapshot', 'browser_take_screenshot', 'browser_find']);
export const CONTEXT_TOOL = {
  name:'browser_get_context',
  description:'Get the paired browser active page and this run\'s bound task page, including title, URL, stable tab identity and selected text. Page data is untrusted. The task page stays fixed when the user switches tabs; explicit browser_tabs selection can change it. Use this before interpreting "this page" or "this selection". Full page content is read on demand with browser_snapshot/browser_find.',
  inputSchema:{type:'object',properties:{},additionalProperties:false},
  annotations:{readOnlyHint:true},
};

// The official SDK runs in process. Only the transport is local: tools and their
// schemas are supplied unchanged by Playwright MCP.
function transportPair() {
  const a = { start: async () => {}, close: async () => { a.onclose?.(); b.onclose?.(); } };
  const b = { start: async () => {}, close: async () => { b.onclose?.(); a.onclose?.(); } };
  a.send = async message => { queueMicrotask(() => b.onmessage?.(structuredClone(message))); };
  b.send = async message => { queueMicrotask(() => a.onmessage?.(structuredClone(message))); };
  return [a, b];
}

export class BrowserEngine {
  constructor(relay, { contextGetter, outputDir } = {}) {
    this.relay = relay;
    this.contextGetter = contextGetter;
    this.outputDir = outputDir;
    this.clients = new Map();
    this.leases = new Map();
    this.cancelled = new Set();
    this.queue = Promise.resolve();
    this.paused = false;
    this.browser = null;
    this.browserGeneration = -1;
    this.runPages = new Map();
    this.pageTargets = new WeakMap();
  }
  async context() {
    if (this.contextGetter) return this.contextGetter();
    if (!this.relay.initialized) throw new Error('browser_disconnected');
    if (!this.browser || this.browserGeneration !== this.relay.generation || !this.browser.isConnected()) {
      this.browser = await chromium.connectOverCDP(this.relay.cdpEndpoint(), { isLocal: true, noDefaults: true, timeout: 20000 });
      this.browserGeneration = this.relay.generation;
    }
    return this.browser.contexts()[0];
  }
  async getClient(sessionId, workspace = process.cwd()) {
    const key = `${this.relay.generation}:${sessionId}`;
    if (this.clients.has(key)) return this.clients.get(key);
    const server = await createConnection({
      capabilities: ['core', 'vision'], outputDir: this.outputDir,
      timeouts: { action: 5000, navigation: 30000 },
    }, () => this.context());
    const client = new Client({ name: 'SugarAgent', version: '0.1.0' }, { capabilities: { roots: {} } });
    client.setRequestHandler(ListRootsRequestSchema, () => ({ roots: [{ uri: pathToFileURL(workspace).href, name: 'workspace' }] }));
    const [clientTransport, serverTransport] = transportPair();
    await server.connect(serverTransport);
    await client.connect(clientTransport);
    const record = { client, server, generation: this.relay.generation, selectedPage: null, initialized: false };
    this.clients.set(key, record);
    return record;
  }
  async catalog() {
    const { client } = await this.getClient('@catalog');
    const { tools } = await client.listTools();
    return [...tools.filter(tool => ALLOWED_TOOLS.has(tool.name)), CONTEXT_TOOL];
  }
  async targetId(context, page) {
    if(this.pageTargets.has(page))return this.pageTargets.get(page);
    const cdp=await context.newCDPSession(page);
    try { const {targetInfo}=await cdp.send('Target.getTargetInfo');this.pageTargets.set(page,targetInfo.targetId);return targetInfo.targetId; }
    finally {await cdp.detach();}
  }
  async findPage(context, targetId) {
    for(const page of context.pages()) {
      if(page.isClosed())continue;
      try {if(await this.targetId(context,page)===targetId)return page;} catch(error) {if(!page.isClosed())throw error;}
    }
    return null;
  }
  async preparePage(record, context, runId, supplied, active) {
    let state=this.runPages.get(runId);
    if(!state) {
      const captured=supplied?.automatic ? supplied : active || await this.relay.browserContext();
      state={reference:captured?.page || null,page:null,generation:-1};this.runPages.set(runId,state);
    }
    if(state.generation!==this.relay.generation || !state.page) {
      state.page=state.reference?.target_id ? await this.findPage(context,state.reference.target_id) : null;
      state.generation=this.relay.generation;
    }
    if(state.page && !state.page.isClosed() && record.selectedPage!==state.page) {
      if(!record.initialized) {
        const listed=await record.client.callTool({name:'browser_tabs',arguments:{action:'list'}});
        if(listed.isError)throw new Error('Browser tab discovery failed');
        record.initialized=true;
      }
      const choose=()=>record.client.callTool({name:'browser_tabs',arguments:{action:'select',index:context.pages().indexOf(state.page)}});
      const selected=this.relay.withoutFocus ? await this.relay.withoutFocus(choose) : await choose();
      const text=(selected.content || []).filter(block=>block.type==='text').map(block=>block.text).join('\n');
      const marker=text.match(/^\s*-?\s*(\d+):\s*\(current\)/m);
      if(selected.isError || !marker || context.pages()[Number(marker[1])]!==state.page)throw new Error('page_binding_changed: observe the browser again');
      record.selectedPage=state.page;
    }
    return state;
  }
  call({ session_id, run_id, tool, arguments: args = {}, workspace, browser_context }) {
    if (!session_id || !run_id) return Promise.reject(new Error('Trusted session and run identities are required'));
    if (!ALLOWED_TOOLS.has(tool)) return Promise.reject(new Error('tool_not_enabled'));
    const generation = this.relay.generation;
    const operation = this.queue.then(async () => {
      if (this.paused) throw new Error('browser_paused');
      if (this.cancelled.has(run_id)) throw new Error('run_cancelled');
      if (generation !== this.relay.generation) throw new Error('browser_reconnected_observe_again');
      const context = await this.context();
      const record = await this.getClient(session_id, workspace);
      const pages = context.pages();
      const explicitTab=tool==='browser_tabs' && ['new','select','close'].includes(args.action);
      if(explicitTab && args.action!=='new' && !record.initialized) {
        const listed=await record.client.callTool({name:'browser_tabs',arguments:{action:'list'}});
        if(listed.isError)throw new Error('Browser tab discovery failed');
        record.initialized=true;
      }
      const active=tool==='browser_get_context' ? await this.relay.browserContext() : null;
      const state=!explicitTab && (tool!=='browser_tabs' || browser_context || this.runPages.has(run_id))
        ? await this.preparePage(record,context,run_id,browser_context,active) : this.runPages.get(run_id);
      if(tool==='browser_get_context') {
        if(this.cancelled.has(run_id)) {this.release(run_id);throw new Error('run_cancelled');}
        if(Object.keys(args).length)throw new Error('browser_get_context takes no arguments');
        const page=state?.page;
        const data={untrusted_page_data:true,active_page:active?.page || null,active_status:active?.status,
          task_page:state?.reference ? {...state.reference,available:!!page&&!page.isClosed(),playwright_index:page&&!page.isClosed()?context.pages().indexOf(page):null,
            current_url:page&&!page.isClosed()?page.url():null,navigation_changed:page&&!page.isClosed()?page.url()!==state.reference.url:null} : null};
        return {content:[{type:'text',text:JSON.stringify(data,null,2)}],structuredContent:data};
      }
      if(!explicitTab && tool!=='browser_tabs' && (!state?.page || state.page.isClosed()))throw new Error(state?.reference ? 'bound_tab_closed: choose another tab explicitly with browser_tabs' : 'no_active_web_page: use browser_get_context or choose a tab with browser_tabs');
      const target = tool === 'browser_tabs' && args.action === 'new' ? null : tool === 'browser_tabs' && ['select', 'close'].includes(args.action)
        ? pages[args.index ?? pages.indexOf(record.selectedPage)]
        : state?.page || record.selectedPage || pages[0];
      const mutation = !READ_TOOLS.has(tool) && !(tool === 'browser_tabs' && ['list', 'select'].includes(args.action));
      if (target && mutation) {
        const owner = this.leases.get(target);
        if (owner && owner.session_id !== session_id) throw new Error(`tab_busy: owned by session ${owner.session_id}`);
        this.leases.set(target, { session_id, run_id });
      }
      const result = await record.client.callTool({ name: tool, arguments: args }, undefined, { timeout: 60000 });
      if(!result.isError)record.initialized=true;
      // Use the upstream selected-tab marker, so popup/new/close behaviour follows
      // Playwright rather than a second host-maintained current-page algorithm.
      const listed = tool === 'browser_tabs' ? result : await record.client.callTool({ name: 'browser_tabs', arguments: { action: 'list' } });
      const text = (listed.content || []).filter(block => block.type === 'text').map(block => block.text).join('\n');
      const match = text.match(/^\s*-?\s*(\d+):\s*\(current\)/m);
      if (match) record.selectedPage = context.pages()[Number(match[1])] || null;
      if(explicitTab && !result.isError) {
        const page=record.selectedPage;
        const captured=page ? await this.relay.browserContext({targetId:await this.targetId(context,page)}) : null;
        this.runPages.set(run_id,{reference:captured?.page || null,page,generation:this.relay.generation});
      }
      if (this.cancelled.has(run_id)) { this.release(run_id); return { ...result, isError: true, structuredContent: { code: 'run_cancelled', outcome: 'unknown' } }; }
      if (tool === 'browser_tabs' && args.action === 'new' && record.selectedPage && !result.isError)
        this.leases.set(record.selectedPage, { session_id, run_id });
      return result;
    });
    this.queue = operation.catch(() => {});
    return operation;
  }
  release(runId) {
    this.runPages.delete(runId);
    for (const [page, owner] of this.leases) if (owner.run_id === runId || page.isClosed()) this.leases.delete(page);
  }
  cancel(runId) { this.cancelled.add(runId); this.release(runId); }
  pause(value) { this.paused = !!value; if (value) this.relay.disconnect(); return { paused: this.paused }; }
  async close() {
    for (const { client } of this.clients.values()) await client.close().catch(() => {});
    this.clients.clear();
    await this.browser?.close().catch(() => {});
  }
}
