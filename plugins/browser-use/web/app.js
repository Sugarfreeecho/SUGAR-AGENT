export function mountBrowserSettings(root = document, {native=false,onToast} = {}) {
const $ = id => root.querySelector("#" + CSS.escape(id));
const lifetime = new AbortController();
let disposed=false, observer, resizeObserver;
let setup, devices = [], loaded = false, adding = false, pairBaseline = null, expires = 0, first = true, refreshing = false, lifecycle, restartOperation, restartSubmitted = false, revokeId;
let toastTimer;
const error = message => { if(disposed)return; $('error').textContent = message; $('error').hidden = !message; };
function toast(message) { if(disposed)return;if(onToast){onToast(message);return;} $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 2200); }
async function request(path, body, headers = {}) {
  const cleanupDecision=path.startsWith('/api/lifecycle/restarts/') && path.endsWith('/decision') && body?.decision==='deny';
  if(disposed && !cleanupDecision)throw new DOMException('Settings closed','AbortError');
  const response = await fetch(path.startsWith('/api/') ? path : '/api/browser/v1' + path, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store', signal:cleanupDecision ? undefined : lifetime.signal, keepalive:cleanupDecision });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) { const failure = new Error(data.detail || data.error || (response.status === 404 ? '后端尚未加载新版接口，请重启开发后端后重新检测。' : '请求未完成，请重试。')); failure.data = data; throw failure; }
  return data;
}
function openStep(name) {
  for (const step of root.querySelectorAll('.step')) {
    const open = step.id === 'step-' + name;
    step.querySelector('.step-heading').setAttribute('aria-expanded', String(open));
    step.querySelector('.step-body').hidden = !open;
  }
  $('step-' + name).scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
for (const step of root.querySelectorAll('.step')) step.querySelector('.step-heading').onclick = () => openStep(step.id.slice(5));
function done(name, completed, label) {
  const step = $('step-' + name); step.classList.toggle('done', completed); step.querySelector('.number').textContent = completed ? '✓' : String(['service', 'extension', 'pair', 'ready'].indexOf(name) + 1);
  $(name + '-state').textContent = label;
}
function renderDevices(defaultId) {
  $('devices').replaceChildren();
  if (!devices.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '尚未配对浏览器。完成上方步骤后，它会出现在这里。'; $('devices').append(empty); }
  for (const device of devices) {
    const row = document.createElement('div'); row.className = 'device';
    const icon = document.createElement('span'); icon.className = 'device-icon'; icon.textContent = '▣';
    const info = document.createElement('div'); info.className = 'device-info';
    const title = document.createElement('strong'); title.textContent = device.name;
    const status = document.createElement('small'); status.className = device.runtime.initialized ? 'online' : '';
    status.textContent = device.runtime.paused ? '控制已暂停' : device.runtime.initialized ? '● 已连接' : '○ 等待浏览器上线';
    info.append(title, status);
    const actions = document.createElement('div'); actions.className = 'device-actions';
    const choose = document.createElement('button'); choose.textContent = device.id === defaultId ? '默认浏览器' : '设为默认'; choose.disabled = device.id === defaultId;
    if(native)choose.classList.add('st-btn','sm');
    choose.onclick = () => action(choose, async () => { await request('/default', { browser_id: device.id }); await refresh(); });
    const revoke = document.createElement('button'); revoke.textContent = '撤销配对'; revoke.className = 'danger'; revoke.onclick = () => { revokeId = device.id; $('revoke-dialog').showModal(); };
    if(native)revoke.classList.add('st-btn','sm');
    actions.append(choose, revoke); row.append(icon, info, actions); $('devices').append(row);
  }
}
async function refresh() {
  if (disposed)return;
  if (refreshing) return; refreshing = true;
  try {
    const [info, state] = await Promise.all([request('/setup'), request('/status')]); setup = info; devices = state.devices.filter(item => !item.revoked);
    $('extension-version').textContent = info.version ? '扩展包 v' + info.version : '扩展包未构建';
    $('extension-version').hidden = false;
    const connected = devices.some(device => device.runtime.initialized);
    const serviceReady = info.plugin_enabled && info.node_available && info.runtime_installed;
    $('backend-detail').textContent = '新版接口已生效 · 服务运行中';
    $('plugin-detail').textContent = info.plugin_enabled ? '已启用，可接受浏览器连接' : '启用后即可配对和使用网页工具';
    $('enable').hidden = info.plugin_enabled; $('plugin-ok').hidden = !info.plugin_enabled;
    const installing = info.installation.status === 'running';
    $('runtime-detail').textContent = info.runtime_bundled ? (info.runtime_installed && info.node_available ? '运行组件已随 SugarAgent 提供，无需另行安装' : '运行组件不完整，请修复或重新安装 SugarAgent') : installing ? '正在安装，请稍候…' : info.installation.error || (info.runtime_installed ? 'Playwright 运行组件已安装' : info.node_available ? '需要安装一次运行组件' : '请先安装 Node.js 22.18 或更高版本');
    $('install').hidden = info.runtime_installed || info.runtime_bundled; $('install').disabled = installing || !info.node_available || !info.plugin_enabled; $('runtime-ok').hidden = !info.runtime_installed || !info.node_available;
    $('manual-runtime').hidden = !!info.runtime_bundled;
    $('directory').textContent = info.extension_directory;
    $('reveal').disabled = !info.extension_ready; $('download').hidden = !info.download_ready; $('build-help').hidden = info.extension_ready;
    $('next-service').disabled = !serviceReady;
    $('generate').disabled = !serviceReady; $('loaded').disabled = !serviceReady;
    $('service-summary').textContent = serviceReady ? '服务与运行组件已就绪' : '完成准备后继续下一步';
    done('service', serviceReady, serviceReady ? '已就绪' : '待准备');
    done('extension', loaded || connected, loaded || connected ? '已加载' : '待完成');
    done('pair', connected, connected ? '已连接' : devices.length ? '已配对 · 待上线' : '待配对');
    done('ready', connected, connected ? '可以使用' : '等待连接');
    root.querySelector('.success-note strong').textContent = connected ? '浏览器与 Agent 已连通' : '连接完成后，就可以开始';
    root.querySelector('.success-note>span').textContent = connected ? '✓' : '○';
    $('overall').textContent = connected ? '● 浏览器已连接' : '完成下面的连接步骤'; $('overall').classList.toggle('online', connected);
    $('progress-bar').style.width = (serviceReady ? connected ? 100 : loaded ? 50 : 25 : 0) + '%';
    renderDevices(state.default_browser);
    const newlyConnected = pairBaseline && devices.some(device => !pairBaseline.has(device.id) && device.runtime.initialized);
    if (newlyConnected) { adding = false; pairBaseline = null; expires = 0; $('code-panel').hidden = true; openStep('ready'); toast('配对成功，浏览器已连接'); }
    else if (first) { openStep(connected && !adding ? 'ready' : serviceReady ? 'extension' : 'service'); first = false; }
  } catch (caught) {
    if(disposed)return;
    try {
      const catalog = await request('/api/plugins/catalog');
      const plugin = catalog.plugins?.find(item => item.id === 'browser-use' || item.plugin_id === 'browser-use');
      if (plugin && !plugin.enabled) {
        $('overall').textContent='启用插件后继续';$('overall').classList.remove('online');
        $('service-summary').textContent='启用插件，继续完成连接';
        $('backend-detail').textContent = '后端在线，启用插件后继续检测';
        $('plugin-detail').textContent = catalog.enabled?.plugins === false ? '插件总开关已关闭，请先在插件管理中开启' : '点击启用，继续完成连接';
        $('enable').hidden = false; $('plugin-ok').hidden = true;
        $('runtime-detail').textContent = '启用插件后自动检查';
        done('service', false, '待启用'); first = false; return;
      }
    } catch { /* Retain the original connection error. */ }
    error(caught.message); $('backend-detail').textContent = '需要更新或重新连接后端';
  }
  finally { refreshing = false; }
}
async function action(button, task) {
  button.disabled = true; error('');
  try { await task(); } catch (caught) { error(caught.message); } finally { button.disabled = false; }
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('已复制'); }
  catch { error('浏览器未允许访问剪贴板，请选中旁边的文字手动复制。'); }
}
for (const button of root.querySelectorAll('[data-copy]')) button.onclick = () => void copy($(button.dataset.copy).textContent);
$('server-url').textContent = location.origin;
for (const browser of ['chrome', 'edge']) $(browser).onclick = () => { $('browser-url').textContent = browser + '://extensions'; for (const name of ['chrome', 'edge']) {$(name).classList.toggle('selected', name === browser);$(name).classList.toggle('is-on',name===browser);$(name).setAttribute('aria-pressed',String(name===browser));} };
$('next-service').onclick = () => openStep('extension');
$('loaded').onclick = () => { loaded = true; openStep('pair'); void refresh(); $('name').focus(); };
$('refresh').onclick = () => { error(''); void refresh(); };
$('enable').onclick = () => action($('enable'), async () => { await request('/api/plugins/browser-use/enabled', { enabled: true }); await refresh(); });
$('install').onclick = () => action($('install'), async () => { await request('/setup/install', {}); await refresh(); });
$('reveal').onclick = () => action($('reveal'), async () => { await request('/setup/reveal', {}); toast('已打开扩展目录'); });
$('pair').onsubmit = event => { event.preventDefault(); void action($('generate'), async () => { pairBaseline = new Set(devices.map(item => item.id)); const data = await request('/pairings', { name: $('name').value.trim() }); $('code').textContent = data.code; expires = Date.now() + 600000; $('code-panel').hidden = false; tick(); }); };
$('add-browser').onclick = () => { adding = true; pairBaseline = null; $('code-panel').hidden = true; loaded = false; openStep('extension'); };
$('confirm-revoke').onclick = () => action($('confirm-revoke'), async () => { await request('/devices/' + encodeURIComponent(revokeId) + '/revoke', {}); $('revoke-dialog').close(); await refresh(); });
$('restart').onclick = () => action($('restart'), async () => {
  lifecycle = await request('/api/lifecycle/status');
  if (!lifecycle.restart_available) throw new Error('当前启动方式不支持页面重启。请从托盘重启，或在启动终端重新启动开发后端，然后点击「重新检测」。');
  const result = await request('/api/lifecycle/restarts', { reason: '使浏览器扩展与会话附件接口生效' }, { 'x-myagent-lifecycle-ui': lifecycle.ui_token });
  restartOperation = result.operation;
  restartSubmitted = false;
  const impact = restartOperation.impact || lifecycle.impact || {};
  $('restart-impact').textContent = `重启会影响 ${impact.running_tasks || 0} 个运行任务、${impact.background_jobs || 0} 个后台作业和 ${impact.terminals || 0} 个终端。`;
  $('restart-dialog').showModal();
});
$('confirm-restart').onclick = () => action($('confirm-restart'), async () => {
  let result;
  try { result = await request('/api/lifecycle/restarts/' + encodeURIComponent(restartOperation.restart_id) + '/decision', { decision: 'allow_once', request_digest: restartOperation.request_digest, resume_requester: true }, { 'x-myagent-lifecycle-ui': lifecycle.ui_token }); }
  catch (failure) { if (failure.data?.operation?.confirmation_changed) { restartOperation = failure.data.operation; const impact = restartOperation.impact || {}; $('restart-impact').textContent = `影响已更新：${impact.running_tasks || 0} 个运行任务、${impact.background_jobs || 0} 个后台作业、${impact.terminals || 0} 个终端。请再次确认。`; } throw failure; }
  restartSubmitted = true;
  $('restart-dialog').close(); $('restart-note').textContent = '正在重启，等待本机服务恢复…'; toast('已确认重启');
});
$('restart-dialog').addEventListener('close', () => { if (!restartSubmitted && restartOperation) void request('/api/lifecycle/restarts/' + encodeURIComponent(restartOperation.restart_id) + '/decision', { decision: 'deny', request_digest: restartOperation.request_digest }, { 'x-myagent-lifecycle-ui': lifecycle.ui_token }).catch(() => {}); });
function tick() { if (!expires) return; const seconds = Math.max(0, Math.ceil((expires - Date.now()) / 1000)); $('expiry').textContent = seconds ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} 后过期 · 仅可使用一次` : '配对码已过期，请重新生成'; if (!seconds) { $('code').textContent = '已过期'; for (const button of root.querySelectorAll('[data-copy=code]')) button.disabled = true; } else for (const button of root.querySelectorAll('[data-copy=code]')) button.disabled = false; }
if(!native)window.addEventListener('message', event => {
  if (event.source !== parent || event.origin !== location.origin || event.data?.type !== 'myagent:plugin-settings-context') return;
  const root = document.documentElement;
  root.dataset.theme = event.data.theme === 'theme-dark' ? 'dark' : event.data.theme === 'theme-purple' ? 'purple' : 'light';
  if (Number.isFinite(event.data.fontPx)) {
    const size = Math.max(12, Math.min(20, event.data.fontPx)), base = Math.max(11, size - 2);
    root.style.setProperty('--setup-font', base + 'px'); root.style.setProperty('--setup-title', size + 'px');
    root.style.setProperty('--setup-small', Math.max(10, base - 1) + 'px'); root.style.setProperty('--setup-tiny', Math.max(9, base - 2) + 'px');
  }
}, {signal:lifetime.signal});
if (!native && parent !== window) { document.documentElement.classList.add('embedded'); parent.postMessage({ type: 'myagent:plugin-settings-ready' }, location.origin); resizeObserver = new ResizeObserver(() => parent.postMessage({ type: 'myagent:plugin-settings-resize', height: root.querySelector('main').scrollHeight }, location.origin)); resizeObserver.observe(root.querySelector('main')); }
const visible=()=>!document.hidden && (!native || root.isConnected && root.getClientRects().length>0 && intersecting);
let intersecting=true;
const becameVisible=()=>{if(visible())void refresh();};
if(native){observer=new IntersectionObserver(entries=>{intersecting=entries[0]?.isIntersecting===true;becameVisible();});observer.observe(root);}
document.addEventListener('visibilitychange',becameVisible,{signal:lifetime.signal});
window.addEventListener('pagehide',()=>dispose(),{signal:lifetime.signal});
const timer=setInterval(()=>{if(visible()){tick();void refresh();}},3000);
void refresh();
function dispose(){if(disposed)return;disposed=true;clearInterval(timer);clearTimeout(toastTimer);observer?.disconnect();resizeObserver?.disconnect();root.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());lifetime.abort();}
return dispose;

}
