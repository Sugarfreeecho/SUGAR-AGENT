import readline from 'node:readline';
import { BrowserRelay } from './relay.mjs';
import { BrowserEngine } from './engine.mjs';

const output = value => process.stdout.write(JSON.stringify(value) + '\n');
const relay = new BrowserRelay({ token: process.env.SUGAR_BROWSER_RELAY_TOKEN,
  allowedOrigin: process.env.SUGAR_BROWSER_EXTENSION_ORIGIN,
  onChange: state => output({ event: 'browser_state', ...state }) });
await relay.start();
const engine = new BrowserEngine(relay, { outputDir: process.env.SUGAR_BROWSER_OUTPUT_DIR });
const catalog = await engine.catalog();
output({ event: 'ready', ...relay.status(), tools: catalog });
let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  await engine.close();
  await relay.close();
}
const input = readline.createInterface({ input: process.stdin });
input.on('line', async line => {
  let request;
  try {
    request = JSON.parse(line);
    let result;
    switch (request.method) {
      case 'catalog': result = catalog; break;
      case 'status': result = { ...relay.status(), paused: engine.paused }; break;
      case 'call': result = await engine.call(request.params); break;
      case 'cancel': engine.cancel(request.params.run_id); result = { cancelled: true }; break;
      case 'release': engine.release(request.params.run_id); result = { released: true }; break;
      case 'pause': result = engine.pause(request.params.paused); break;
      default: throw new Error('Unknown internal method');
    }
    output({ id: request.id, result });
  } catch (error) { output({ id: request?.id, error: error.message }); }
});
input.on('close', () => { close().finally(() => process.exit(0)); });
process.on('SIGTERM', () => { close().finally(() => process.exit(0)); });
