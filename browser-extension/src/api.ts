import { applicationMethod } from './application-api.mjs';
import { controlResult } from './control.mjs';
import { loopbackUrl } from './shared.mjs';

async function compatibleApi(request: { path: string; body?: unknown }) {
  const method = applicationMethod(request.path, request.body);
  const connection = (await chrome.storage.local.get('sugar.connection'))['sugar.connection'];
  if (!connection?.token) throw new Error('配对已失效，请重新连接 SugarAgent');
  const url = loopbackUrl(connection.baseUrl); url.pathname = request.path;
  const response = await fetch(url.href, { method, credentials: 'omit', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + connection.token }, body: request.body === undefined ? undefined : JSON.stringify(request.body) });
  if (response.status === 404 || response.status === 405) throw new Error('本机服务尚未加载此功能，请在主程序连接设置中重启后端后重试。');
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : data.error?.message || data.detail || 'HTTP ' + response.status);
  return controlResult(data);
}

export async function extension(request: object): Promise<any> {
  const reply = await chrome.runtime.sendMessage(request);
  // A development sidebar may refresh before its older MV3 worker is reloaded.
  // This rejection happens before HTTP dispatch; the allowlisted authenticated
  // request can safely run in the sidebar without repeating an accepted write.
  if ((request as any).type === 'api' && reply?.ok === false && reply.error === 'Unsupported application endpoint') return compatibleApi(request as any);
  if (!reply?.ok) throw new Error(reply?.error || '扩展后台暂时不可用');
  return reply.result;
}
export const rpc = (method: string, params: object = {}, key = crypto.randomUUID()) => extension({ type: 'rpc', method, params, key });
