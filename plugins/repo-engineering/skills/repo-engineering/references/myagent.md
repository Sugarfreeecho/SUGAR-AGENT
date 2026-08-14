# MyAgent repository reference

## Key paths

- Backend and runtime: `app/`
- Frontend source: `frontend/src/`
- Built frontend checked into the repository: `app/templates/dist/`
- Tests: `tests/`
- Plugin discovery root: `plugins/`
- Project MCP configuration: `mcp_servers.json`

## Verification

- Focused Python test: `.\python\python.exe -m pytest <test-path> -q`
- Frontend production build: run `npm run build` from `frontend/`
- Frontend dist verification: run `npm run verify:dist` from `frontend/`
- Diff whitespace check: `git diff --check`

Build the frontend after source changes because production assets are committed. Preserve unrelated changes already present in the worktree.

## Integration notes

Context7, Playwright, and GitHub are global MCP servers declared in the repository-root `mcp_servers.json`; they are intentionally independent of this Plugin's enablement lifecycle. The MCP bridge supports stdio, SSE, and Streamable HTTP. `${NAME}` references in remote MCP headers resolve from the process environment only when a connection is created, so tracked configuration can name a secret without containing it.
