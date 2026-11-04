const endpoints = Object.freeze({
  '/api/browser/v1/models': 'GET',
  '/api/browser/v1/approvals/analyze': 'POST',
  '/api/browser/v1/workspaces': 'GET',
  '/api/browser/v1/workspaces/pick': 'POST',
  '/api/browser/v1/workspaces/validate': 'POST',
  '/api/browser/v1/plugins': 'GET',
  '/api/browser/v1/skills': 'GET',
  '/api/browser/v1/messages': 'POST',
  '/api/browser/v1/steers': 'POST',
  '/api/browser/v1/subagents': 'POST',
  '/api/browser/v1/pending/cancel': 'POST',
  '/api/browser/v1/session-state': 'POST',
  '/api/browser/v1/permissions': 'POST',
  '/api/browser/v1/human/list': 'POST',
  '/api/browser/v1/questions/resolve': 'POST',
  '/api/browser/v1/questions/cancel': 'POST',
  '/api/browser/v1/approvals/resolve': 'POST',
});

export function applicationMethod(path, body) {
  const method = body === undefined ? 'GET' : 'POST';
  if (endpoints[path] !== method) throw new Error('Unsupported application endpoint');
  return method;
}
