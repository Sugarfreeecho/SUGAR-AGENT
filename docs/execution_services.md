# DSH execution and Computer Use adaptation

The bundled `execution-tools` plugin supplies background jobs, persistent PTYs,
and a session panel. The `computer-use` plugin owns one optional Cua provider.
Python execution services run on a dedicated loop; tool return, a finished chat
run, and browser disconnection do not own their lifetime.

## Model tools

- `run_shell(command, workdir?, timeout_ms?, login?, run_in_background?)` retains
  legacy arguments and shell selection. An authorized session defaults to a
  30-second foreground wait; timeout promotes its still-running process to a
  visible job. Explicit background execution returns a job ID after startup.
  When the job quota is full, ordinary foreground calls fall back to bounded
  legacy execution; explicit background calls report the quota error.
  Standalone callers without a trusted session retain the original timeout/kill
  behavior and cannot launch an unowned background task.
- `job_output(job_id, wait=false, timeout_ms=30000)` consumes new model output.
  Waits are capped at 600 seconds and do not kill the job on timeout.
  `job_list()` lists the owner's jobs; `job_kill(job_id, reason?)` requests
  cancellation. Nonzero exit codes are completed process results, while startup
  or execution-service failures are failed jobs.
- `terminal_open(type="shell", name?, cwd?)` opens PowerShell on Windows or
  Bash on POSIX. `terminal_send(sessionId, text, submit=true,
  run_in_background=false)` preserves shell/REPL state between calls.
  `terminal_read(sessionId, offset=0, count=500)` reads newest-relative retained
  lines. `terminal_signal(sessionId, signal)`, `terminal_close(sessionId)` and
  `terminal_list()` manage only that Agent's terminals.
- Background terminal sends are `pty-send` jobs. Their completion means the
  send wait finished: `stdin_read`, `inferred_idle`, `timeout`, or `session_exit`.
  Silence and timeout never prove command exit. Cancellation sends Ctrl+C and
  retains the shell. Unsupported platform signals fail explicitly; use close
  to kill a shell.
  `job_output` streams new terminal text during the send and returns the final
  viewport/wait result once to the model after settlement.

Defaults match DSH where applicable: 10 active jobs per Agent; 256 KiB model
output buffer, reduced to 16 KiB after a finished job's first model read; 8
terminals per owner/actor; 160×40 model viewport; at most 10,000 history lines
within a conservative 4 MiB text budget; 256 KiB read results; 64 KiB input.
Raw persisted output rolls at 32 MiB per resource. Truncation is explicit.
Shell readiness uses a private per-terminal prompt marker and foreground process
checks. A submitted line must be echoed before the new prompt is accepted;
delayed earlier prompts and generic OSC sequences are not readiness. Applications
without echo/controlled prompts conservatively return silence or timeout.

## UI and authorization

The session Execution panel displays jobs and model/user terminals. Opening a
user terminal is a direct system-user action; it does not inherit Agent approval
mode. Model terminals and user terminals have separate input ownership. Model
tools cannot list, send to, close, or consume user terminals. User output is not
inserted into model history.

REST endpoints live under `/sessions/{id}/jobs` and `/sessions/{id}/terminals`.
Job output endpoints use independent byte cursors and never consume model
output. User terminal output uses SSE with a connection token; the latest
connection owns input and resize. Reconnection resumes by byte offset, and an
overwritten cursor receives a viewport snapshot plus a truncation flag.
Closing the view disconnects; the explicit End button closes the process.
Writes require same-origin browser requests.

Agent calls pass the existing central policy and digest-bound approvals.
Interactive inputs retain destructive/self-protection checks and require fresh
approval in restricted modes. Mode changes close affected model PTYs and stop
process jobs launched under full access when permission is tightened. The
optional egress helper's per-command tickets cannot safely authorize a whole
interactive PTY: restricted model PTYs report unavailable when that helper is
enabled, while ordinary `run_shell` continues using its existing helper path.

Windows ordinary processes start suspended, join a Job Object, then resume.
POSIX uses process groups and process-tree cleanup. PTY cleanup uses platform
capabilities; this is application-level protection, not a hard OS sandbox.

## Notifications and persisted state

Completion queues a source-tagged system notice. Running Agents consume it at
iteration/final boundaries; a server runner uses the existing session startup
reservation for idle continuation. Reconciliation retries a busy-to-idle edge,
without creating duplicate simultaneous runs or fake user messages. A result
reported to a waiter, a model-requested kill, or lifecycle teardown does not
generate a duplicate completion notice.

Clicking Stop cancels owned jobs across the existing descendant stop scope and
suppresses automatic job wakeup. It also interrupts foreground model PTY work;
idle shells remain available. User terminals remain independent. Deletion and
feature/application shutdown close their execution resources.

State uses Runtime V2 extension namespaces `execution-tools/job.<id>` and
`terminal.<id>` in the existing session event log. Output files live under the
session's `execution/<id>/output.bin`. There is no separate domain event log.
An `output.offset` sidecar tracks the log's absolute byte position after rolling;
model read cursors are checkpointed in extension state and survive restart.
Restart reconciles stale active records to interrupted/closed history; it never
replays commands or reattaches shells. PID cleanup requires a matching process
creation time and a dead previous controller. Copied session records do not
transfer resource ownership.

## Computer Use

Enable explicitly in the Execution panel. Native uses `cua-driver==0.28.0`,
`CuaDriver.create()`, `list_tools_json()`, and `call_tool()`; tools are named
`cua_driver_native__<tool>`. MCP uses a selected, configured local stdio server,
named `mcp__cua-driver-mcp__<tool>`. If registration approvals are enabled, approve
that MCP server's existing registration before selecting it. The provider owns
its catalog/transport exclusively, avoiding duplicate generic MCP tool exposure.

The provider slot is held until admitted calls and shutdown settle. Catalogs
are validated completely before publication; startup failure rolls back names.
Native/MCP never silently fall back to each other. Upstream refusals remain
failed tool outcomes, and images reuse the existing durable attachment store.
Text-only models receive an image capability diagnostic.

Observe the target window freshly before acting, prefer background delivery,
and verify the outcome. Cancellation does not roll back input; a refusal does
not authorize a foreground retry. Desktop state is shared across sessions.
Windows/macOS/Linux adapters depend on the upstream platform facilities;
macOS needs system accessibility/screen-recording permission, and Linux Wayland
support varies by compositor. Upstream references:
[SDK](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/docs/content/docs/reference/cua-driver/sdk-reference.mdx),
[platform support](https://cua.ai/docs/cua-driver/concepts/platform-support).

Environment defaults: `COMPUTER_USE_ENABLED=0`, `COMPUTER_USE_PROVIDER=native`,
`COMPUTER_USE_MCP_SERVER=cua-driver-mcp`. Saved UI settings take precedence.

## Validation

Run the execution/provider tests alongside security, Agent-loop, Host-plugin,
MCP, and frontend regression tests. `MYAGENT_CUA_SMOKE=1` additionally tests
actual SDK catalog discovery and orderly shutdown, without sending desktop
input. Real click/type tests require a dedicated test window and are not run
against the user's desktop automatically. Real Windows PTY/process tests run
locally; POSIX backends require Linux/macOS platform validation.
