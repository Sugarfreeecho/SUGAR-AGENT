export function logUnhandledError(error) {
  // stdout belongs exclusively to the host RPC transport.
  process.stderr.write(`Playwright relay: ${error?.message || 'operation failed'}\n`);
}
