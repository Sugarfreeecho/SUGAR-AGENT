import { useEffect, useState } from 'react';

type Preferences = { language: 'auto' | 'zh-CN' | 'en'; theme: 'system' | 'light' | 'purple' | 'dark'; design?: string; autoPageContext?: boolean };
const english: Record<string, string> = {
  '子 Agent 会话':'Subagent conversations','主／子会话':'Main / subagent conversations','主会话':'Main conversation','返回父会话':'Return to parent','仅记录':'Record only','暂无子 Agent 会话。':'No subagent conversations.','正在读取子 Agent…':'Loading subagents…','父会话不可用，当前子会话仅可查看。':'Parent unavailable; this conversation is read-only.',
  '插话方式':'Steering mode','待发队列':'Pending queue','当前任务结束后执行 · 再按 Enter 插话':'Runs after this task · Enter again to steer',
  '在本轮安全边界追加，不打断当前生成':'Append at the next safe boundary without interrupting generation',
  '中断当前生成并续接；不可中断操作会等待安全结束':'Interrupt generation and continue; non-interruptible operations finish first',
  '编辑待发消息':'Edit pending message','立即插话':'Send now','撤回待发消息':'Withdraw pending message','待发消息内容':'Pending message',
  '保存并排队':'Save in queue','正在提交…':'Submitting…','转为插话的结果待确认，内容已保留':'Steering delivery unconfirmed; content is saved',
  '加入待发队列':'Add to Pending','Enter 加入 Pending，再按 Enter 插话…':'Enter to queue, Enter again to steer…',
  '插话 · 待采纳':'Steer · Pending','插话 · 已采纳':'Steer · Applied','打断插话 · 已采纳':'Interrupt · Applied',
  '选择 Skill':'Choose Skills','搜索 Skill':'Search Skills','正在读取 Skill…':'Loading Skills…','移除 Skill':'Remove Skill','清空选择':'Clear selection',
  '已停用':'Disabled','完成':'Done','没有匹配的 Skill。':'No matching Skills.','暂无可用 Skill，请先在主程序添加。':'No Skills available. Add one in the main app first.','暂无描述':'No description',
  '正在处理附件或发送消息，请稍候再粘贴。':'An upload or message is in progress. Please paste again when it finishes.',
  '正在切换或保存会话，请完成后再附加文件。':'Please wait for the conversation to finish loading or saving before attaching files.',
  '一次最多附加 32 个文件。':'Attach up to 32 files at a time.','上传未返回有效附件，请重试。':'The upload did not return valid attachments. Please try again.',
  '当前版本':'Current version','已完成':'Completed','执行中':'Running','排队中':'Queued','等待输入':'Waiting for input','等待审批':'Awaiting approval',
  '已超时':'Timed out','已取消':'Cancelled','已拒绝':'Denied','已拦截':'Blocked','已跳过':'Skipped','未执行':'Not executed','状态未知':'Unknown status','用时':'Elapsed time','未记录用时':'Duration not recorded',
  '自动关联当前网页': 'Automatically associate the current page',
  '搜索会话': 'Search conversations', '管理会话': 'Manage conversations', '没有匹配的会话。': 'No matching conversations.', '没有匹配的模型。': 'No matching models.', '没有匹配的工作区。': 'No matching workspaces.', '本机服务': 'Local server', '添加资料': 'Add context', '遇到问题': 'Something went wrong', '正在发送…': 'Sending…', '等待执行': 'Queued', '正在验证…': 'Validating…', '会话名称': 'Conversation name',
  '更多操作': 'More actions', '继续最近的会话': 'Continue a recent conversation', '输入消息，开始新会话。': 'Send a message to start a conversation.',
  '工作区': 'Workspace', '选择工作区': 'Choose workspace', '搜索工作区': 'Search workspaces', '选择其他文件夹…': 'Choose another folder…',
  '输入目录路径…': 'Enter directory path…', '目录路径': 'Directory path', '使用此目录': 'Use this folder', '输入已存在的绝对目录': 'Enter an existing absolute directory',
  '插件': 'Plugins', '已安装插件': 'Installed plugins', '启用状态与主程序保持一致。': 'Availability follows the main app.', '管理插件': 'Manage plugins',
  '模型与思考': 'Model and reasoning', '搜索模型': 'Search models', '思考强度': 'Reasoning effort', '跟随模型': 'Model default', '轻度': 'Low', '中等': 'Medium', '深入': 'High', '更深入': 'Extra high', '最高': 'Maximum', '默认': 'Default',
  '查看问题': 'View issue', '打开主程序': 'Open main app',
  '重试加载模型': 'Reload models',
  '紫色': 'Purple', '当前网页': 'Current page', '文件': 'Files', '标签页': 'Tabs', '附加资料': 'Add context',
  '已连接': 'Connected', '待连接': 'Not connected', '网页': 'Page', '本机已连接 · Enter 发送': 'Connected locally · Enter to send',
  '你的浏览器工作搭档': 'YOUR BROWSER COMPANION', '浏览器里的事，': 'Work in your browser,', '一起完成。': 'together.',
  '从当前网页开始，': 'Start with the current page,', '或者直接告诉我你想做什么。': 'or tell me what you have in mind.',
  '读懂当前网页': 'Understand this page', '附加页面，继续提问': 'Attach the page and ask a question',
  '整理浏览器资料': 'Organize your research', '让 Agent 从已打开的页面开始': 'Start with the pages you already have open',
  '先在主程序完成准备': 'Prepare in the main app', '按步骤加载扩展、生成配对码。': 'Follow the steps to load the extension and get a code.',
  '打开连接向导': 'Open setup guide', '填入地址，完成配对': 'Enter the details to pair',
  '设置': 'Settings', '返回': 'Back', '连接 SugarAgent': 'Connect to SugarAgent',
  '连接本机 Agent，在这里继续会话，并使用已登录的网页完成任务。': 'Continue your conversations and work with signed-in websites through your local Agent.',
  '服务地址': 'Server address', '一次性配对码': 'One-time pairing code', '配对并连接': 'Pair and connect',
  '在主程序的浏览器连接设置中生成': 'Generate a code in the main app’s browser settings',
  '打开主程序设置 ↗': 'Open app settings ↗', '浏览器控制': 'Browser control', '恢复控制': 'Resume control',
  '暂停控制': 'Pause control', '连接状态': 'Connection', '重新连接': 'Reconnect', '清除本机配对': 'Clear pairing',
  '语言': 'Language', '主题': 'Theme', '跟随浏览器': 'Browser language', '跟随系统': 'System', '浅色': 'Light', '深色': 'Dark',
  '会话': 'Conversations', '会话历史': 'Conversation history', '新会话': 'New conversation', '会话操作': 'Conversation actions',
  '搜索会话标题': 'Search conversation titles', '显示已归档': 'Include archived', '改名': 'Rename', '置顶': 'Pin',
  '取消置顶': 'Unpin', '归档': 'Archive', '取消归档': 'Unarchive', '删除': 'Delete', '取消': 'Cancel', '保存': 'Save',
  '删除会话': 'Delete conversation', '修改会话名': 'Rename conversation', '正在读取会话…': 'Loading conversation…',
  '加载更早的对话': 'Load earlier messages', '有什么想一起完成的？': 'What shall we work on?',
  '可以附加当前网页，也可以直接交给 Agent 一个任务。': 'Attach a webpage or give the Agent a task.',
  '附加当前网页': 'Attach current page', '附加文件': 'Attach files', '选择标签页': 'Choose a tab', '附加标签页': 'Attach a tab',
  '关闭': 'Close', '消息': 'Message', '给 SugarAgent 发消息…': 'Message SugarAgent…',
  '补充消息，将排队执行…': 'Add a message to the queue…', '默认模型': 'Default model', '模型': 'Model',
  '发送': 'Send', '排队发送': 'Queue message', '停止任务': 'Stop task', 'Agent 正在执行': 'Agent is working',
  '浏览器控制已暂停': 'Browser control paused', '打开主程序 ↗': 'Open main app ↗',
  'Enter 发送 · Shift + Enter 换行': 'Enter to send · Shift + Enter for a new line', '↓ 新内容': '↓ New content',
  '查看执行过程': 'View process', '正在处理': 'Working', '执行失败': 'Execution failed', '已停止': 'Stopped',
  '正在思考': 'Thinking', '思考': 'Reasoning', '复制': 'Copy', '已复制':'Copied', '正在复制…':'Copying…', '复制失败，请重试':'Copy failed, retry', '需要确认': 'Approval required', '操作详情': 'Operation details',
  'AI 分析': 'AI analysis', '允许': 'Allow', '拒绝': 'Deny', '确认拒绝': 'Confirm denial', '拒绝原因': 'Reason for denial',
  '可填写拒绝原因': 'Optional reason', '关闭提示': 'Dismiss notice', '移除网页': 'Remove webpage', '移除文件': 'Remove file',
};
const originalText = new WeakMap<Node, { source: string; painted: string }>();
const originalAttributes = new WeakMap<Element, Record<string, { source: string; painted: string }>>();
const excluded = '.markdown,pre,.history-open strong,.session-title,.context-chip small,.context-chip summary span,.file-chip span,.approval p,.dialog p,.pending-queue-copy>span';

function translation(source: string, language: string) {
  const trimmed = source.trim();
  const result = language === 'en' ? english[trimmed] || (/^\d+ 次操作$/.test(trimmed) ? trimmed.replace(' 次操作', ' actions') : trimmed) : trimmed;
  return source.replace(trimmed, result);
}

function paint(root: Element, language: string) {
  if(root.closest(excluded))return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.closest(excluded)) continue;
    const current = node.textContent || '';
    const known = originalText.get(node);
    const source = known && current === known.painted ? known.source : current;
    if (!english[source.trim()] && !/^\d+ 次操作$/.test(source.trim())) continue;
    const target = translation(source, language);
    originalText.set(node, { source, painted: target });
    if (current !== target) node.textContent = target;
  }
  for (const element of [root,...root.querySelectorAll('[placeholder],[aria-label],[title]')]) {
    if (element.closest(excluded)) continue;
    const known = originalAttributes.get(element) || {};
    for (const name of ['placeholder', 'aria-label', 'title']) {
      const current = element.getAttribute(name);
      if (current === null) continue;
      const source = known[name] && current === known[name].painted ? known[name].source : current;
      const target = translation(source, language);
      known[name] = { source, painted: target };
      if (current !== target) element.setAttribute(name, target);
    }
    originalAttributes.set(element, known);
  }
}

export function usePreferences() {
  const [preferences, setPreferences] = useState<Preferences>({ language: 'auto', theme: 'dark', design: 'selected-m-20261030' });
  useEffect(() => { void chrome.storage.local.get('sugar.preferences').then(value => {
    const saved = value['sugar.preferences'];
    const next = saved?.design === 'selected-m-20261030' ? saved : { ...saved, language: saved?.language || 'auto', theme: 'dark', design: 'selected-m-20261030' };
    setPreferences(next); if (saved?.design !== next.design) void chrome.storage.local.set({ 'sugar.preferences': next });
  }); }, []);
  useEffect(() => {
    if (preferences.theme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = preferences.theme;
  },[preferences.theme]);
  useEffect(() => {
    const language = preferences.language === 'auto' ? navigator.language.startsWith('zh') ? 'zh-CN' : 'en' : preferences.language;
    document.documentElement.lang = language;
    const root=document.getElementById('root')!;
    paint(root,language);
    // UI source strings are Chinese. Restore once when switching back, then
    // leave streamed content alone instead of walking the document per token.
    if(language!=='en')return;
    let scheduled = false,disposed=false;
    const dirty=new Set<Element>();
    const apply = (records:MutationRecord[]) => {
      for(const record of records){
        if(record.type==='childList'){
          for(const node of record.addedNodes){
            const element=node instanceof Element ? node : node.parentElement;
            if(element && !element.closest(excluded))dirty.add(element);
          }
        }else{
          const element=record.target instanceof Element ? record.target : record.target.parentElement;
          if(element && !element.closest(excluded))dirty.add(element);
        }
      }
      if(!dirty.size)return;
      if (scheduled) return;
      scheduled = true;
      queueMicrotask(() => {
        if(disposed)return;
        scheduled=false;
        const pending=[...dirty];dirty.clear();
        for(const element of pending)if(element.isConnected && !pending.some(parent=>parent!==element && parent.contains(element)))paint(element,language);
      });
    };
    const observer = new MutationObserver(apply);
    observer.observe(root, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['title', 'placeholder', 'aria-label'] });
    return () => {disposed=true;observer.disconnect();};
  }, [preferences.language]);
  const update = (patch: Partial<Preferences>) => {
    const next = { ...preferences, ...patch }; setPreferences(next);
    void chrome.storage.local.set({ 'sugar.preferences': next });
  };
  return { preferences, update };
}
