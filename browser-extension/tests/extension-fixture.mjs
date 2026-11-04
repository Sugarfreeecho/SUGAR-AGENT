import { cp, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

export async function extensionFixture(work) {
  const built = resolve(import.meta.dirname, '../dist');
  if (process.env.SUGAR_TEST_LEGACY_API !== '1') return built;
  const copy = resolve(work, 'legacy-worker-extension');
  await cp(built, copy, { recursive: true });
  const worker = resolve(copy, 'background.js');
  const prefix = `let __sugarLegacyApiRejects = 0;
const __sugarLegacyApiAdd = chrome.runtime.onMessage.addListener.bind(chrome.runtime.onMessage);
chrome.runtime.onMessage.addListener = listener => __sugarLegacyApiAdd((request, sender, respond) => {
  if (request.type === 'api' && (request.path?.startsWith('/api/browser/v1/workspaces') || request.path === '/api/browser/v1/messages')) {
    void chrome.storage.session.set({'sugar.testLegacyApiRejects':++__sugarLegacyApiRejects});
    if(request.path === '/api/browser/v1/messages')void chrome.storage.session.set({'sugar.testLegacyMessageRejected':true});
    respond({ok:false,error:'Unsupported application endpoint'}); return false;
  }
  return listener(request,sender,respond);
});\n`;
  await writeFile(worker, prefix + await readFile(worker, 'utf8'));
  return copy;
}
