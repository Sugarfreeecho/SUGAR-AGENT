// Lightweight UI internationalisation. The UI is rendered by several legacy
// modules, so translations are applied at the DOM boundary (including nodes
// added later) instead of coupling every renderer to a framework.
const LS_UI_LANGUAGE = 'myagent-language';
const UI_TRANSLATIONS_EN = {
    '自优化通用智能平台': 'Self-optimizing general intelligence platform',
    '界面设置': 'Interface settings', '新建会话': 'New session', '新建对话': 'New chat', '切换语言': 'Switch language', '切换为英文': 'Switch to English', '切换为中文': 'Switch to Chinese',
    '会话列表': 'Session list', '拖动调整侧栏宽度': 'Drag to resize sidebar', '聊天': 'Chat',
    '选择或新建会话': 'Select or create a session', '展开 Subagent 面板': 'Expand Subagent panel',
    '当前计划': 'Current plan', '清除计划': 'Clear plan', '清除当前计划': 'Clear current plan',
    '消息': 'Messages', '历史记录': 'History', '折叠计划面板': 'Collapse plan panel',
    '折叠历史面板': 'Collapse history panel', '继续综合子任务': 'Continue synthesizing subtasks',
    '撤销': 'Undo', '说说你想做什么…': 'What would you like to do?', '选择文件': 'Choose file',
    '选择 Skill': 'Select Skill', '发送 / 停止': 'Send / Stop', '发送': 'Send', '停止': 'Stop',
    '模型': 'Model', '正在加载模型配置': 'Loading model configuration', '模型配置': 'Model configuration',
    '操作提示': 'Notifications', '已复制': 'Copied', '提示': 'Notice', '取消': 'Cancel', '确定': 'Confirm',
    '暂停': 'Pause', '继续': 'Resume', '增加预算并继续': 'Add budget and resume', '无限制': 'Unlimited', '分钟': 'min',
    '进行中': 'Active', '已暂停': 'Paused', '已完成': 'Completed', '已阻塞': 'Blocked', '已取消': 'Cancelled',
    'Token 预算已耗尽': 'Token budget exhausted', '连续运行失败': 'Consecutive run failures', '手动暂停': 'Paused manually',
    '续跑': 'continuations', '失败': 'failures',
    '请输入要增加的 Token 预算': 'Enter the additional Token budget', '预算必须是大于 0 的整数。': 'The budget must be a positive integer.',
    'Goal 操作失败': 'Goal action failed',
    '关闭': 'Close', '语言': 'Language', '中文': 'Chinese', '英文': 'English',
    '字体大小': 'Font size', '小号': 'Small', '标准': 'Default', '大号': 'Large',
    '界面风格': 'Appearance', '深色': 'Dark', '浅色（默认）': 'Light (default)',
    '会话目录': 'Session list', '会话目录风格': 'Session list style', '会话目录显示模式': 'Session list display mode',
    '紧凑': 'Compact', '详细': 'Detailed', '环境与 API': 'Environment & API', '高级设置': 'Advanced settings',
    '编辑完整 .env，保存后立即写回磁盘（部分项需重启服务）。': 'Edit the complete .env file. Changes are saved to disk immediately (some require a service restart).',
    '如需帮助或反馈，请联系GitHub @sugarfreeecho': 'For help or feedback, contact @sugarfreeecho on GitHub.',
    '运行诊断': 'Diagnostics', '打开执行状态看板': 'Open execution dashboard',
    '更多操作': 'More actions', '更多': 'More', '删除': 'Delete', '置顶': 'Pin', '取消置顶': 'Unpin',
    '归档': 'Archive', '取消归档': 'Unarchive', '删除会话': 'Delete session', '此操作不可恢复': 'This action cannot be undone',
    '未命名': 'Untitled', '重新加载': 'Reload', '加载中...': 'Loading...', '加载中…': 'Loading…',
    '生成中': 'Generating', '任务失败，点击查看': 'Task failed — click to view', '有新回复，点击查看': 'New response — click to view',
    '追问': 'Follow up', '立即发送': 'Send now', '撤回': 'Withdraw', '待发送': 'Pending', '发送中': 'Sending',
    '打断': 'Interrupt', '追加': 'Append', '追问发送模式': 'Follow-up mode', '已追加，等待下一轮': 'Appended, waiting for the next round',
    '已发送': 'Sent', '提交中': 'Submitting', '撤回中': 'Withdrawing', '已接收，等待插入': 'Received, waiting to insert',
    '正在接管当前任务': 'Taking over the current task', '选择 Skill ': 'Select Skill ', '清空': 'Clear',
    '当前没有已注册 Skill': 'No registered skills', '正在加载 Skill': 'Loading skills',
    '加载详情中…': 'Loading details…', '知道了': 'Got it', '允许执行': 'Allow', '拒绝': 'Deny',
    '需要确认': 'Confirmation required', '任务已中断': 'Task interrupted', '已请求停止当前任务': 'Stop requested',
    '展开': 'Expand', '收起': 'Collapse', '复制': 'Copy', '改写': 'Rewrite', '重试': 'Retry'
};
Object.assign(UI_TRANSLATIONS_EN, {
    // Todo / goal panel
    '已完成': 'Completed', '进行中': 'In progress', '待处理': 'Pending', '已暂停': 'Paused', '已阻塞': 'Blocked', '已取消': 'Cancelled',
    '无限制': 'Unlimited', '分钟': 'min', '续跑': 'Continue run', '增加预算并继续': 'Increase budget and continue',
    '继续': 'Continue', 'Token 预算已耗尽': 'Token budget exhausted', '连续运行失败': 'Consecutive run failures', '手动暂停': 'Paused manually',
    '请输入要增加的 Token 预算': 'Enter additional Token budget', '预算必须是大于 0 的整数。': 'Budget must be an integer greater than 0.',
    'Goal 操作失败': 'Goal operation failed', '目标操作失败': 'Goal operation failed', '待办事项': 'Todo items',
    '规划': 'Plan', '计划': 'Plan', '清除当前计划': 'Clear current plan',
    // Runtime status lines
    '正在思考中...': 'Thinking...', '正在重连': 'Reconnecting', '任务已中断': 'Task interrupted',
    '已请求停止当前任务': 'Stop requested for the current task', '解析事件失败': 'Failed to parse event',
    '验证': 'Verification', '正在根据对话更新要点': 'Updating key points from the conversation',
    '上下文窗口已满，开始压缩': 'Context window full; starting compression', '上下文压缩已完成': 'Context compression completed',
    '上下文摘要': 'Context summary', '要点': 'Key points', '历史/旧版事件': 'History/legacy event',
    '立即发送': 'Send now', '追问发送模式': 'Follow-up send mode', '打断': 'Interrupt', '追加': 'Append', '撤回': 'Withdraw',
    '撤回中': 'Withdrawing', '提交中': 'Submitting', '已追加，等待下一轮': 'Appended, waiting for the next round',
    '已接收，等待插入': 'Received, waiting to insert', '正在接管当前任务': 'Taking over the current task', '发送中': 'Sending', '已发送': 'Sent', '待发送': 'Pending send',
    '已选择 Skill：': 'Selected Skill: ', '追问接管已保留，等待发送通道释放。': 'Follow-up takeover retained; waiting for the send channel to become available.',
    '请求失败': 'Request failed', '撤销失败，请重试。': 'Undo failed. Please try again.'
});
Object.assign(UI_TRANSLATIONS_EN, {
    '新会话': 'New session', '停止 <span class="loader">': 'Stop <span class="loader">', '加载会话': 'Load session',
    '取消置顶': 'Unpin', '取消归档': 'Unarchive', '删除会话': 'Delete session', '此操作不可恢复': 'This action cannot be undone',
    '无法同步服务器。': 'Could not sync with the server.', '当前没有选中的会话。': 'No session is currently selected.',
    '消息定位索引无效，可能需要刷新当前会话。': 'The message index is invalid. Refresh the current session.',
    '服务端拒绝清空整个会话。': 'The server rejected clearing the entire session.',
    '服务端裁剪历史失败，可能是历史索引已变化或会话文件暂时不一致。': 'The server could not trim history; the index may have changed or the session file may be inconsistent.',
    '原因：': 'Reason: ', '无法改写': 'Cannot rewrite', '改写内容不能为空。': 'Rewrite content cannot be empty.',
    '生成中不可操作': 'Unavailable while generating', '当前会话仍在生成。请等待完成或停止后再修改历史。': 'This session is still generating. Wait for completion or stop it before editing history.',
    '无法删除该条': 'Cannot delete this message', '消息索引异常，已阻止清空整个会话。请刷新后再试。': 'The message index is invalid; clearing the session was blocked. Refresh and try again.',
    '删除消息': 'Delete message', '将同步到服务器': 'Will sync to server', '确定删除本条及之后的所有对话内容吗？': 'Delete this message and all following conversation content?',
    '同步失败': 'Sync failed', '删除未生效。': 'The deletion was not applied.', '无法改写该条': 'Cannot rewrite this message',
    '该消息尚未与服务器索引对齐，请刷新当前会话后再试。': 'This message is not aligned with the server index. Refresh the session and try again.',
    '无法分支': 'Cannot fork', '该回答尚未与服务器同步，请刷新页面后重试。': 'This response is not synced with the server. Refresh and try again.',
    '创建分支会话': 'Create fork session', '原会话不会被修改': 'The original session will not be modified',
    '问题': 'Question', '已完成': 'Completed', '进行中': 'In progress', '未开始': 'Not started',
    '折叠文件夹': 'Collapse folder', '展开文件夹': 'Expand folder', '下载保存 Mermaid 流程图为图片': 'Download Mermaid diagram as image',
    '调用工具': 'Tool calls', '次': 'times', '轮': 'rounds', '分': 'm', '秒': 's',
    '工具调用生成中...': 'Preparing tool call...', '执行中...': 'Running...', '执行结果': 'Result',
    '平均': 'Average', '累计': 'Total', '占比': 'Share', '暂无数据': 'No data', '暂无执行统计': 'No execution statistics',
    '暂无子事件': 'No sub-events', '无用户消息': 'No user message', '成功': 'Success', '会话数': 'Sessions',
    'LLM 请求': 'LLM requests', 'API 累计耗时': 'Cumulative API duration', '平均首 token': 'Average first token',
    '累计输入 token': 'Cumulative input tokens', '累计输出 token': 'Cumulative output tokens', '工具调用总数': 'Total tool calls',
    '累计网络流量': 'Cumulative network traffic', 'API 总耗时': 'Total API duration', '首 token': 'First token',
    '输入 token': 'Input tokens', '输出 token': 'Output tokens', '上下文长度': 'Context length', '工具调用': 'Tool calls',
    '网络等待': 'Network wait', '网络流量': 'Network traffic', '时间': 'Time', '执行轮次': 'Execution round',
    '模型': 'Model', '会话': 'Session', '运行 ID': 'Run ID', 'Session ID': 'Session ID', '当前会话筛选': 'Current session filter',
    '所有会话': 'All sessions', '累计总值': 'Cumulative totals', '平均首 token': 'Average first token'
});
Object.assign(UI_TRANSLATIONS_EN, {
    // Session navigation and lifecycle
    '置顶目录': 'Pinned', '归档目录': 'Archived', '刷新归档目录': 'Refresh archived sessions',
    '加载归档目录': 'Load archived sessions', '加载更多': 'Load more', '今天': 'Today', '昨天': 'Yesterday', '近7天': 'Last 7 days',
    '近14天': 'Last 14 days', '加载会话': 'Load session', '加载会话列表失败': 'Failed to load sessions',
    '加载历史消息失败': 'Failed to load message history', '创建新会话失败': 'Failed to create session',
    '未选择会话': 'No session selected', '暂无提问': 'No questions yet', '打开工作目录': 'Open workspace',
    '打开会话目录': 'Open session folder', '确定删除会话': 'Delete this session',

    // Subagents
    '后台运行': 'Running in background', '运行中': 'Running', '完成': 'Completed', '失败': 'Failed',
    '已中断': 'Interrupted', '缺少 final 结果': 'Missing final result', '查看输出': 'View output',
    '放大显示': 'Expand view', '在浮窗内全屏显示': 'Show full-size in overlay', '无 Subagent': 'No subagents',
    '(暂无事件)': '(No events yet)', '(暂无 final 结果)': '(No final result)', '(无输出)': '(No output)',
    '删除 Subagent': 'Delete subagent', '删除失败': 'Deletion failed',
    '将删除该 subagent 的会话记录、过程卡片及其嵌套子任务。该操作不可撤销。': 'This will delete the subagent session, process card, and nested subtasks. This cannot be undone.',
    '无法删除该 Subagent，请稍后重试。': 'Could not delete this subagent. Please try again later.',
    '继续任务': 'Continue task', '继续中…': 'Continuing…', '等待主任务完成': 'Waiting for main task',

    // Model and skill controls
    '默认方案': 'Default profile', '未命名方案': 'Unnamed profile', '未加载模型配置': 'Model configuration not loaded',
    '没有可用模型配置': 'No model configurations available', '没有启用的模型配置': 'No enabled model profiles',
    '暂无已保存模型配置，可到模型配置页中保存': 'No saved model configurations. Save one on the model configuration page.',
    '请稍候': 'Please wait', '模型配置加载失败': 'Failed to load model configuration', '切换失败': 'Switch failed',
    'Skill 加载失败': 'Failed to load skills', '启用': 'Enable', '禁用': 'Disable',
    '模型配置启停失败': 'Failed to change model profile status', 'Skill 启停失败': 'Failed to change Skill status',

    // Messages, history and composer
    '开始一段新的对话': 'Start a new conversation',
    '在左侧侧栏新建或选择会话。Enter 发送，Ctrl+Enter / Shift+Enter 换行。': 'Create or select a session in the sidebar. Press Enter to send; Ctrl+Enter or Shift+Enter for a new line.',
    '分支': 'Fork', '创建分支': 'Create fork', '创建失败': 'Creation failed',
    '将在当前回答之后创建独立分支会话。分支点之前的内容与原会话相同，可在分支中继续提问且不影响原会话。': 'A separate fork session will be created after this response. Earlier messages remain the same, and continuing in the fork will not affect the original session.',
    '创建分支未生效。': 'The fork was not created.', '工具': 'Tool', '执行过程': 'Execution process',
    '本段过程已折叠': 'This process section is collapsed', '信息': 'Info', '错误': 'Error', '回复': 'Response',
    '思考': 'Reasoning', '压缩': 'Compression', '裁剪': 'Trim', '要点': 'Key points', '状态': 'Status',
    '工具调用生成中...': 'Preparing tool call...', '执行中...': 'Running...', '执行结果': 'Result',
    '正在思考中...': 'Thinking...', '正在重连': 'Reconnecting', '验证': 'Verification',
    'Mermaid 无法解析此图': 'Mermaid could not render this diagram',
    'Mermaid 流程图放大预览': 'Expanded Mermaid diagram preview', '关闭放大预览': 'Close expanded preview',
    '下载保存 Mermaid 流程图为图片': 'Download Mermaid diagram as an image', '下载图片': 'Download image',
    '放大显示 Mermaid 流程图': 'Expand Mermaid diagram', '点击查看图片': 'Click to view image',
    '移除文件路径': 'Remove file path', '响应异常': 'Invalid response', '已调用系统打开文件': 'Asked the system to open the file',
    '无法打开文件': 'Could not open file', '无法连接服务': 'Could not connect to the service',
    '取消改写': 'Cancel rewrite', '已截断历史，可撤销恢复': 'History truncated; you can undo to restore it',
    '已填入输入框，可撤销': 'Inserted into the input; you can undo',
    '改写待生效：发送消息后才会截断历史并发送；点此取消改写。': 'Rewrite pending: history will be truncated only when the message is sent. Click here to cancel.',
    '无法定位该条': 'Could not locate this message',

    // File picker
    '请求失败': 'Request failed', '无法打开选择对话框': 'Could not open the file picker', '上传失败': 'Upload failed',
    '正在取消上传…': 'Cancelling upload…', '上传已取消。': 'Upload cancelled.',
    '上传失败：网络连接异常。': 'Upload failed: network connection error.', '上传超时，请重试。': 'Upload timed out. Please try again.',
    '已有文件正在上传，请等待完成或先取消。': 'A file upload is already in progress. Wait for it to finish or cancel it first.',
    '本次上传总大小超过 200 MB 限制。': 'The total upload exceeds the 200 MB limit.',
    '读取工作区文件失败': 'Failed to read workspace files', '搜索工作区文件': 'Search workspace files',
    '未选择文件': 'No files selected', '选择工作目录外文件': 'Choose a file outside the workspace',
    '加载中': 'Loading', '没有匹配文件': 'No matching files', '折叠文件夹': 'Collapse folder',
    '展开文件夹': 'Expand folder', '读取失败': 'Failed to read', '浏览路径': 'Browse path', '工作区文件': 'Workspace files',

    // Confirmations, recovery and errors
    '粘贴文件失败': 'Failed to paste file', '文件上传失败': 'File upload failed', '无法保存剪贴板中的文件或图片。': 'Could not save the file or image from the clipboard.',
    '无法上传所选文件或剪贴板中的图片。': 'Could not upload the selected file or clipboard image.',
    '截断失败': 'Truncation failed', '无法同步服务器，改写未生效。': 'Could not sync with the server; the rewrite was not applied.',
    '撤销失败，请重试。': 'Undo failed. Please try again.', '检测到上次运行未完成，正在自动恢复任务…': 'The previous run was incomplete. Restoring it automatically…',
    '恢复实时流失败': 'Failed to restore the live stream', '续接失败': 'Failed to continue',
    '追问插入失败': 'Failed to insert follow-up', '追问已被接收，无法撤回': 'The follow-up was accepted and can no longer be withdrawn'
});
Object.assign(UI_TRANSLATIONS_EN, {
    'Agent Team（实验功能）': 'Agent Team (experimental)',
    'Agent Team 功能开关': 'Agent Team feature switch',
    '关闭（默认）': 'Off (default)', '启用': 'Enable',
    '正在读取状态…': 'Reading status…', '管理当前会话团队': 'Manage current session team',
    '当前会话团队控制面板': 'Current session team control panel',
    '刷新': 'Refresh', '请求关停': 'Request shutdown', '完成关停': 'Complete shutdown',
    '当前会话还没有团队。': 'This session does not have a team yet.',
    '团队名称（可选）': 'Team name (optional)', '创建团队': 'Create team',
    '成员': 'Members', '共享任务': 'Shared tasks', '权限请求': 'Permission requests',
    '持久成员由 Agent 调用 team(action="spawn_member") 创建和派工。': 'The agent creates and dispatches persistent members with team(action="spawn_member").',
    '新任务标题': 'New task title', '添加任务': 'Add task',
    '允许一次': 'Allow once', '暂无成员': 'No members', '暂无任务': 'No tasks',
    '暂无权限请求': 'No permission requests', '请先选择或新建一个会话。': 'Select or create a session first.'
});
const UI_I18N_ATTRS = ['aria-label', 'data-ui-tip', 'title', 'placeholder'];
const uiI18nTextOriginal = new WeakMap();
const uiI18nAttrOriginal = new WeakMap();
var uiLanguage = localStorage.getItem(LS_UI_LANGUAGE) === 'en' ? 'en' : 'zh-CN';
var uiI18nObserver = null;

function translateUiString(value) {
    if (uiLanguage !== 'en') return value;
    var exact = UI_TRANSLATIONS_EN[value];
    if (exact) return exact;
    return String(value)
        .replace(/^更早 (\d+) 轮对话$/, 'Earlier $1 conversations')
        .replace(/^(\d+) \/ (\d+) 已完成$/, '$1 / $2 completed')
        .replace(/^(\d+) \/ (\d+) 完成$/, '$1 / $2 completed')
        .replace(/^(\d+)分钟$/, '$1 min')
        .replace(/^(\d+) 分钟$/, '$1 min')
        .replace(/^已选择 (\d+) 个 Skill$/, '$1 skills selected')
        .replace(/^已选择 (\d+) 项$/, '$1 items selected')
        .replace(/^正在上传 (\d+) 个文件… (\d+)%$/, 'Uploading $1 files… $2%')
        .replace(/^已选 (\d+) \/ 共 (\d+)$/, '$1 selected / $2 total')
        .replace(/^已选 (\d+) \/ 已启用 (\d+) \/ 共 (\d+)$/, '$1 selected / $2 enabled / $3 total')
        .replace(/^加载失败: (.+)$/, 'Failed to load: $1')
        .replace(/^请求失败: (.+)$/, 'Request failed: $1')
        .replace(/^无法打开：(.+)$/, 'Could not open: $1')
        .replace(/^移除 (.+)$/, 'Remove $1')
        .replace(/^确定删除会话「(.+)」吗？其中的消息与记录将被移除。$/, 'Delete session “$1”? Its messages and records will be removed.')
        .replace(/^工具 (\d+) 次$/, '$1 tool calls')
        .replace(/^失败 (\d+) 次$/, '$1 failures')
        .replace(/工具\s*(\d+)\s*次/g, '$1 tool calls')
        .replace(/失败\s*(\d+)\s*次/g, '$1 failures')
        .replace(/(\d+)\s*分\s*(\d+)\s*秒/g, '$1m $2s')
        .replace(/^(\d+) 轮$/, '$1 rounds')
        .replace(/^(\d+)分(\d+)秒$/, '$1m $2s')
        .replace(/^调用工具 (.+) (\d+)次$/, 'Called tool $1 $2 times')
        .replace(/^检测到系统睡眠约 (\d+) 秒，任务已恢复$/, 'System sleep detected for about $1 seconds; task resumed')
        .replace(/^检测到 Agent 进程暂停约 (\d+) 秒，任务已恢复$/, 'Agent process pause detected for about $1 seconds; task resumed')
        .replace(/^模型配置切换失败: (.+)$/, 'Failed to switch model configuration: $1')
        .replace(/^模型配置启停失败: (.+)$/, 'Failed to change model profile status: $1')
        .replace(/^Skill 启停失败：(.+)$/, 'Failed to change Skill status: $1')
        .replace(/^续接失败: (.+)$/, 'Failed to continue: $1')
        .replace(/^恢复实时流失败: (.+)$/, 'Failed to restore live stream: $1')
        .replace(/^追问插入失败: (.+)$/, 'Failed to insert follow-up: $1')
        .replace(/^追问已被接收，无法撤回: (.+)$/, 'The follow-up was accepted and cannot be withdrawn: $1')
        .replace(/^验证：(.+)$/, 'Verification: $1')
        .replace(/【上下文窗口已满，开始压缩】/g, '[Context window full; starting compression]')
        .replace(/【上下文压缩已完成】/g, '[Context compression completed]')
        .replace(/【上下文摘要】/g, '[Context summary]')
        .replace(/【上下文裁剪】/g, '[Context trimming]')
        .replace(/【要点】/g, '[Key points]')
        .replace(/上下文窗口已满，开始压缩/g, 'Context window full; starting compression')
        .replace(/上下文压缩已完成/g, 'Context compression completed')
        .replace(/正在进行上下文裁剪以控制 token（可能需数秒，请稍候）…/g, 'Trimming context to control tokens (this may take a few seconds; please wait)…')
        .replace(/摘要模型仍在生成或等待响应中，请稍候…/g, 'The summary model is still generating or waiting for a response; please wait…')
        .replace(/模型仍在更新要点或等待响应中，请稍候…/g, 'The model is still updating key points or waiting for a response; please wait…')
        .replace(/已完成上下文裁剪与摘要以控制长度/g, 'Context trimming and summarization completed to control length')
        .replace(/已完成上下文裁剪以控制长度/g, 'Context trimming completed to control length')
        .replace(/正在分析上下文并准备本地裁剪…/g, 'Analyzing context and preparing local trimming…')
        .replace(/正在执行本地裁剪与微压…/g, 'Performing local trimming and micro-compression…')
        .replace(/已对非关键信息进行裁剪/g, 'Non-critical information trimmed')
        .replace(/正在收敛较早段落中的 ReAct 过程…/g, 'Consolidating ReAct steps in earlier sections…')
        .replace(/已对较早段落中的思考过程进行裁剪/g, 'Reasoning in earlier sections trimmed')
        .replace(/裁剪后仍超限，开始生成历史摘要…/g, 'Still over the limit after trimming; generating a history summary…')
        .replace(/没有足够可摘要的历史前缀，已转入截尾兜底。/g, 'Not enough history prefix to summarize; switching to tail truncation fallback.')
        .replace(/没有足够可摘要的历史前缀，继续尝试更窄尾窗…/g, 'Not enough history prefix to summarize; trying a narrower tail window…')
        .replace(/可摘要历史不足，已丢弃更早对话（保留至多约半窗 token 的尾部）。/g, 'Not enough history to summarize; discarded earlier messages and kept up to roughly half a window of recent tokens.')
        .replace(/可摘要历史不足；对话已在半窗预算内未再截断。/g, 'Not enough history to summarize; the conversation was not truncated further within the half-window budget.')
        .replace(/摘要输出格式重试后仍无效，已改用摘录兜底。/g, 'The summary output remained invalid after retries; using an excerpt fallback.')
        .replace(/第 (\d+) 次摘要输出格式无效，已丢弃并准备重试…/g, 'Summary output for attempt $1 was invalid, discarded, and will be retried…')
        .replace(/摘要模型调用失败，已改用摘录兜底：/g, 'Summary model call failed; using an excerpt fallback: ')
        .replace(/流程异常，已切换为失败兜底截尾。/g, 'The process encountered an error; switched to the failure fallback truncation.')
        .replace(/当前上下文无需进一步裁剪或摘要/g, 'The current context needs no further trimming or summarization')
        .replace(/正在进行上下文裁剪（可能需数秒，请稍候）…/g, 'Trimming context (this may take a few seconds; please wait)…')
        .replace(/第 (\d+) 轮：正在生成历史摘要与要点…/g, 'Round $1: generating history summary and key points…')
        .replace(/第 (\d+) 轮摘要完成/g, 'Round $1 summary completed')
        .replace(/第 (\d+) 轮要点已写入/g, 'Key points for round $1 written')
        .replace(/正在根据编辑说明更新要点…/g, 'Updating key points from the edit instructions…')
        .replace(/已按说明更新要点/g, 'Key points updated according to the instructions')
        .replace(/完成 (\d+) 轮历史摘要；完成关键 信息、经验与结论 的记录/g, 'Completed $1 rounds of history summarization; recorded key information, experience, and conclusions')
        .replace(/本轮未能继续缩小本地上下文，已转入安全兜底。/g, 'This round could not reduce local context further; switched to safe fallback.')
        .replace(/已完成配置的 (\d+) 轮且尚未达到压缩比，继续进行增量摘要…/g, 'Completed the configured $1 rounds without reaching the compression ratio; continuing incremental summarization…')
        .replace(/连续摘要未再缩小本地上下文（已尝试 (\d+) 轮）/g, 'Repeated summarization did not reduce local context further (tried $1 rounds)')
        .replace(/摘要未达到目标压缩比（已尝试 (\d+) 轮）/g, 'Summary did not reach the target compression ratio (tried $1 rounds)')
        .replace(/已转入安全兜底截尾。/g, 'Switched to safe fallback truncation.')
        .replace(/对话已在半窗预算内未再截断。/g, 'The conversation was not truncated further within the half-window budget.')
        .replace(/上下文已按策略完成裁剪/g, 'Context trimmed according to policy')
        .replace(/对话已摘要，关键信息已写入 key_context/g, 'Conversation summarized; key information written to key_context')
        .replace(/\[系统通知：/g, '[System notice: ')
        .replace(/\[压缩失败，保留截断原文片段\]/g, '[Compression failed; retaining a truncated excerpt]')
        .replace(/检测到同会话仍有未结束的上下文压缩，等待其完成后再继续 ReAct。/g, 'An unfinished context compression was detected for this session; waiting for it to finish before continuing ReAct.')
        .replace(/已按 CONTEXT_COMPRESS_FAILURE_MAX_TOKENS（与压缩失败兜底同款）裁剪对话尾部并继续本步/g, 'The conversation tail was trimmed using CONTEXT_COMPRESS_FAILURE_MAX_TOKENS (same as the compression-failure fallback), then this step continued')
        .replace(/上下文已截尾（Conversation truncated）；更早内容请查本会话目录。/g, 'Context truncated (Conversation truncated); see the session directory for earlier content.')
        .replace(/上下文已截尾（Conversation truncated），保留约半窗 token 尾部。/g, 'Context truncated (Conversation truncated), keeping roughly the last half-window of tokens.')
        .replace(/已完成上下文裁剪与摘要/g, 'Context trimming and summarization completed')
        .replace(/已完成上下文裁剪/g, 'Context trimming completed')
        .replace(/【自动·长度策略】/g, '[Automatic length policy]')
        .replace(/(\d+)\s*轮/g, '$1 rounds')
        .replace(/正在根据对话更新要点/g, 'Updating key points from the conversation')
        .replace(/正在思考中\.\.\./g, 'Thinking...')
        .replace(/正在重连/g, 'Reconnecting')
        .replace(/^\[历史\/旧版事件\] (.+)$/, '[History/legacy event] $1')
        .replace(/^已选择 Skill：(.+)$/, 'Selected Skill: $1')
        .replace(/^追问暂未发出（发送通道繁忙），已保留待重试: (.+)$/, 'Follow-up not sent (send channel busy); retained for retry: $1')
        .replace(/^追问降级发送未成功，已保留待重试: (.+)$/, 'Fallback follow-up send failed; retained for retry: $1')
        .replace(/^思·/, 'Reasoning · ')
        .replace(/^答·/, 'Response · ')
        .replace(/^平均 (.+)$/, 'Average $1')
        .replace(/^累计 (.+)$/, 'Total $1')
        .replace(/^占本阶段 (.+)$/, 'Share of phase $1')
        .replace(/^(.+) 次 LLM 请求$/, '$1 LLM requests')
        .replace(/^(.+) 个模型。$/, '$1 models.')
        .replace(/^\.\.\. \[中间省略 (\d+) 行\] \.\.\.$/, '... [$1 lines omitted] ...')
        .replace(/^\.\.\. \[中间省略约 (\d+) 字符\] \.\.\.$/, '... [about $1 characters omitted] ...');
}

function translateUiNode(root) {
    if (!root) return;
    var elements = [];
    if (root.nodeType === Node.ELEMENT_NODE) elements.push(root);
    if (root.querySelectorAll) elements = elements.concat(Array.from(root.querySelectorAll('*')));
    elements.forEach(function (el) {
        if (el.closest && el.closest('.sidebar-brand-sub')) return;
        if (el.matches('script,style,code,pre,[contenteditable="true"]')) return;
        var originals = uiI18nAttrOriginal.get(el) || {};
        UI_I18N_ATTRS.forEach(function (attr) {
            if (!el.hasAttribute(attr)) return;
            if (!(attr in originals)) originals[attr] = el.getAttribute(attr);
            el.setAttribute(attr, uiLanguage === 'en' ? translateUiString(originals[attr]) : originals[attr]);
        });
        uiI18nAttrOriginal.set(el, originals);
        Array.from(el.childNodes).forEach(function (node) {
            if (node.nodeType !== Node.TEXT_NODE || !node.nodeValue.trim()) return;
            if (!uiI18nTextOriginal.has(node)) uiI18nTextOriginal.set(node, node.nodeValue);
            var original = uiI18nTextOriginal.get(node);
            var trimmed = original.trim();
            var translated = uiLanguage === 'en' ? translateUiString(trimmed) : trimmed;
            node.nodeValue = original.replace(trimmed, translated);
        });
    });
}

function applyUiLanguage(language, persist) {
    uiLanguage = language === 'en' ? 'en' : 'zh-CN';
    document.documentElement.lang = uiLanguage;
    document.documentElement.setAttribute('data-language', uiLanguage);
    document.title = uiLanguage === 'en' ? 'General Agent · Intelligent Chat' : 'General Agent · 智能会话';
    if (persist) localStorage.setItem(LS_UI_LANGUAGE, uiLanguage);
    if (uiI18nObserver) uiI18nObserver.disconnect();
    translateUiNode(document.body);
    var languageButton = document.getElementById('sidebar-language-btn');
    if (languageButton) {
        languageButton.setAttribute('aria-label', uiLanguage === 'en' ? 'Switch to Chinese' : '切换为英文');
        languageButton.setAttribute('title', uiLanguage === 'en' ? 'Switch language' : '切换语言');
    }
    if (uiI18nObserver) uiI18nObserver.observe(document.body, { childList: true, subtree: true });
    document.dispatchEvent(new CustomEvent('myagent:language-change', { detail: { language: uiLanguage } }));
}

function initUiI18n() {
    uiI18nObserver = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === Node.ELEMENT_NODE) translateUiNode(node);
                else if (node.nodeType === Node.TEXT_NODE && node.parentElement) translateUiNode(node.parentElement);
            });
            if (mutation.type === 'characterData' && mutation.target.parentElement) {
                var textNode = mutation.target;
                var current = textNode.nodeValue || '';
                var original = uiI18nTextOriginal.get(textNode);
                if (!original || !original.trim()) {
                    original = current;
                    uiI18nTextOriginal.set(textNode, original);
                }
                var trimmed = original.trim();
                var translated = uiLanguage === 'en' ? translateUiString(trimmed) : trimmed;
                var nextValue = original.replace(trimmed, translated);
                if (nextValue !== current) textNode.nodeValue = nextValue;
            }
        });
    });
    applyUiLanguage(uiLanguage, false);
}
initUiI18n();
