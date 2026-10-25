// A keyless peer implemented with DSH's exact official SDK, without DSH boot.
import { Readable, Writable } from 'node:stream';
import { pathToFileURL } from 'node:url';
const { agent, methods, ndJsonStream } = await import(pathToFileURL(process.argv[2]).href);
let connection;
const app = agent({ name: 'dsh-sdk-peer' })
  .onRequest(methods.agent.initialize, () => ({ protocolVersion: 1, agentCapabilities: {}, authMethods: [] }))
  .onRequest(methods.agent.session.new, () => ({ sessionId: 'typescript-session' }))
  .onRequest(methods.agent.session.prompt, async ({ params }) => {
    const result = await connection.client.request(methods.client.session.requestPermission, {
      sessionId: params.sessionId, toolCall: { toolCallId: 'one' },
      options: [{ optionId: 'once', kind: 'allow_once', name: 'Once' }],
    });
    const text = result.outcome.outcome === 'selected' ? 'allowed' : 'denied';
    await connection.client.notify(methods.client.session.update, {
      sessionId: params.sessionId,
      update: { sessionUpdate: 'agent_message_chunk', content: { type: 'text', text } },
    });
    return { stopReason: 'end_turn' };
  });
connection = app.connect(ndJsonStream(Writable.toWeb(process.stdout), Readable.toWeb(process.stdin)));
await connection.closed;
