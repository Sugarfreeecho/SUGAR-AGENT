// Run against the same @agentclientprotocol/sdk version used by DSH.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { Readable, Writable } from 'node:stream';
import { pathToFileURL } from 'node:url';

const [sdkPath, python, entry, backend, cwd] = process.argv.slice(2);
const { client: createAcpClientApp, methods, ndJsonStream, PROTOCOL_VERSION } = await import(pathToFileURL(sdkPath).href);
const child = spawn(python, [entry, '--server-url', backend], {
  stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
});
let stderr = '';
child.stderr.on('data', chunk => { stderr += chunk; });
const updates = [];
const app = createAcpClientApp({ name: 'sugaragent-dsh-conformance' })
  .onNotification(methods.client.session.update, ({ params }) => { updates.push(params); })
  .onRequest(methods.client.session.requestPermission, ({ params }) => {
    assert.deepEqual(params.options.map(option => option.kind), ['allow_once', 'reject_once']);
    return { outcome: { outcome: 'selected', optionId: 'allow-once' } };
  });
const connection = app.connect(ndJsonStream(Writable.toWeb(child.stdin), Readable.toWeb(child.stdout)));
const agent = connection.agent;
const deadline = setTimeout(() => { child.kill(); process.exitCode = 1; }, 25000);
try {
  const init = await agent.request(methods.agent.initialize, { protocolVersion: PROTOCOL_VERSION, clientCapabilities: {} });
  assert.equal(init.protocolVersion, 1);
  assert.deepEqual(Object.keys(init.agentCapabilities.sessionCapabilities).sort(), ['close', 'list', 'resume']);
  assert.equal(init.agentCapabilities.mcpCapabilities.http, true);
  const created = await agent.request(methods.agent.session.new, { cwd, mcpServers: [] });
  const sessionId = created.sessionId;
  const changed = await agent.request(methods.agent.session.setConfigOption, { sessionId, configId: 'model', value: 'model-b' });
  assert.equal(changed.configOptions.find(option => option.id === 'model').currentValue, 'model-b');
  const answer = await agent.request(methods.agent.session.prompt, { sessionId, prompt: [{ type: 'text', text: 'permission' }] });
  assert.equal(answer.stopReason, 'end_turn');
  assert.equal(updates.filter(row => row.update.sessionUpdate === 'agent_message_chunk').map(row => row.update.content.text).join(''), 'answer');
  await agent.request(methods.agent.session.close, { sessionId });
  const beforeResume = updates.length;
  await agent.request(methods.agent.session.resume, { sessionId, cwd, mcpServers: [] });
  assert.equal(updates.length, beforeResume, 'resume must not replay history');
  const listing = await agent.request(methods.agent.session.list, { cwd });
  assert.equal(listing.sessions[0].sessionId, sessionId);
  await agent.request(methods.agent.session.close, { sessionId });
  console.log(JSON.stringify({ protocol: 1, sdk: 'DSH TypeScript SDK', checks: ['initialize', 'new', 'config', 'permission', 'prompt', 'close', 'resume-without-replay', 'list'] }));
} catch (error) {
  console.error(error);
  if (stderr) console.error(stderr);
  process.exitCode = 1;
} finally {
  connection.close();
  child.stdin.end();
  await new Promise(resolve => {
    if (child.exitCode !== null) return resolve();
    child.once('exit', resolve);
    setTimeout(() => { child.kill(); resolve(); }, 3000).unref();
  });
  clearTimeout(deadline);
}
