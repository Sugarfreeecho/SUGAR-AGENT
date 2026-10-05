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
  `completion_scope=terminal_send` and `command_state` explicitly distinguish
  observation completion from command exit or success. The job retains its
  `terminal_id` so subsequent output can be collected with `terminal_read`.
  Silence and timeout never prove command exit. Cancellation interrupts the
  foreground and retains the shell; its `interruption` receipt reports whether
  readiness was observed. Unsupported platform signals fail explicitly; use
  close to kill a shell.
  `job_output` streams new terminal text during the send and returns the final
  viewport/wait result once to the model after settlement. Text is rendered by
  terminal lines before appending, so cursor rewrites do not concatenate every
  intermediate repaint. A partial line is flushed at observation settlement.

Windows SIGINT writes Ctrl+C to the owned PTY and waits for a new shell prompt.
If it does not return, a bounded fallback terminates the original owned child
process tree after rechecking shell creation time. It never terminates or
replaces the shell. Receipts identify forced termination and retain its targets,
errors and readiness verification. This may end a REPL program whose Ctrl+C did
not return to the shell. An in-process PowerShell cmdlet has no separate child
target: it can remain `interruptVerified:false`, with explicit `terminal_close`
as the force-stop action. `delivered` does not prove interruption; a ready shell
or exited targets do not imply exit code zero. The old console-attachment helper
has been removed. POSIX interruption retains its previous PTY behavior.

Model terminals use DSH's plain environment (`TERM=dumb`, `PAGER=cat`,
`GIT_PAGER=cat`, `NO_COLOR=1`). PowerShell model sessions additionally disable
PSReadLine to avoid prompt-input startup races and repaint noise. User terminals
retain rich color and their interactive line editor. Empty pywinpty reads are
treated as temporary no-data; actual EOF and read failures have distinct close
diagnostics and an exit code when available.

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
approval in restricted modes. Changing from full access to either restricted
mode closes affected model PTYs and stops process jobs launched under full
access. Loosening permissions or switching between the two restricted presets
keeps existing work alive; retained model PTYs use the new mode for future
input admission. User terminals are unaffected. Session creation and direct
permission changes apply the same cleanup and notification path. The
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

Both providers now project Cua's `structuredContent` into model-visible text.
Snapshot IDs, original element indexes/tokens, completeness/degradation flags,
delivery verification, refusal codes and screenshot dimensions are preserved.
The canonical structured payload is also retained in the tool outcome metadata.
Structured element JSON lines replace duplicate tokenless tree markdown; large
results still use the normal offloader, with routing/status fields first.
Use `query` with the accessibility tree enabled to select controls. Use
`include_screenshot:false` for tree-only refresh and
`include_accessibility_tree:false` for image-only observation.

Window input tools accept the optional host extension `_verify`. It is removed
before invoking Cua and applies `verify_state` to the same pid/window/session
after one successful delivery. Defaults are `timeout_ms:1000` and
`include_screenshot:false`; the upstream stable-sample default remains in effect.
The complete verification request is validated before sending input. Example:

```json
{
  "pid": 123,
  "window_id": 456,
  "element_token": "<fresh token>",
  "_verify": {
    "expect": [{"element": {"selector": {"label_contains": "Logs"}, "exists": true}}]
  }
}
```

Only a stable `satisfied` result completes the combined operation. An
`unsatisfied` result fails with `postcondition_unsatisfied`; an unknown,
unstable or unavailable observation fails with `postcondition_unknown`.
These results preserve the input receipt: failure does not mean input was
rolled back. No input replay, foreground fallback or implicit session revival
occurs. A bare delivery receipt stays an unverified tool completion and must
not be treated as task success. Verification proves only its supplied
predicates; an already-present element alone may not prove a new transition.
Desktop targeting requires a separate explicit verification call.

Provider calls are serialized, including action-plus-verification sequences;
all Cua calls disable early streaming execution and parallel execution so a read
later in a model tool batch cannot overtake its earlier start/stop/input. This
ordering does not span independent Agent calls. During recording, a pixel input
without cached host image evidence first obtains an image-only observation of
its exact window; failure refuses the input, rather than writing an empty map.
queued calls are cancellable and recheck the admitted permission mode before
delivery. This cannot prevent the user or another application from changing
the desktop between observations. An ended implicit session needs
`start_session({})`; starting a named session does not revive implicit tools.

Cua screenshot attachments retain their coordinate space and original driver
image dimensions. Model request previews state the exact x/y conversion back
to driver image pixels, including both attachment and request resizing.
`get_window_state.max_dimension` now resizes only the host preview: the driver
capture always uses its configured default, so changing preview size cannot
change its PID-scoped coordinate registry. `coordinate_mapping` preserves the
driver dimensions even when the preview and attachment are resized. The
driver applies its own screenshot-to-screen mapping; do not scale again by
`window_bounds`, client rectangles or DPI. Zoom captures use the upstream zoom
action contract. Native recording evidence images can have different dimensions
and must not be treated as the input coordinate reference. Refresh after any
window/configuration change or observation of a different window with the same
PID. Other clients can still change the shared desktop/driver state.

New recordings include `myagent-coordinate-contract.json`. Replay refuses legacy
recordings without this contract, changed driver image configuration, changed
image/window dimensions, multiple mapped windows sharing a PID, stale snapshot
tokens/indexes, zoom-bound input, desktop pixel input and trajectories that
change coordinate configuration or window geometry. Fresh image-only observations
check exact-window geometry before any replay input. Native replay bypasses the
host per-action verifier: its success counts prove dispatch only, not application
outcomes. Observe and verify the final state explicitly.

For `get_agent_cursor_state`, the host repairs only `tool_output_invalid` whose
`invalid_output.position` is null and whose entire published success/refusal
schema validates after adding null solely to the required position property.
Other malformed fields remain errors. This is read-only compatibility, with
the original failure receipt retained in metadata.

Explicit nested refusals fail even when the driver omits `isError`. Keyboard/text
receipts with `delivery_failed` and no satisfied host postcondition fail as
`input_delivery_unconfirmed`; neither retry nor foreground fallback occurs.
Unverified action text is labeled as a dispatch receipt rather than UI success.
A contradictory recording getter returns `recording_state_conflict` with unknown
live state and both receipts. Comparison covers enabled state, active directory,
driver owner and counter lower bound. The check is provider-wide; mapping covers
other Agents' recorded actions on this connection as well. A cached start
acknowledgement is not proof the recorder is still running. Control remains
scoped to the Agent that started it; this is not ownership proof against
independent driver clients. The status API and control receipts expose
`recording_evidence` / `host_recording_evidence` with `policy_revision`, tracking
state and Agent owner to distinguish deployed policy from stale observations.

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

### Configure the Cua Driver MCP provider

The installed `cua-driver==0.28.0` package includes the MCP executable, so a
separate MCP package is not required. Add this server to `mcp_servers.json`:

```json
{
  "cua-driver-mcp": {
    "command": "<absolute path to cua-driver executable>",
    "args": ["mcp"],
    "env_allowlist": ["APPDATA", "LOCALAPPDATA"],
    "default_tool_effect": "external_write",
    "tool_timeout": 120
  }
}
```

Place the entry inside the existing `servers` object. On Windows, the bundled
executable is `python/Lib/site-packages/cua_driver/bin/cua-driver.exe`; resolve
that path against the repository root. Update the absolute path if the checkout
moves. The environment allowlist preserves the driver's Windows configuration
locations without inheriting model credentials.

In Execution → Computer Use, select **MCP**, choose **cua-driver-mcp**, and enable
the provider. The saved selection is restored at startup. The Computer Use
provider exclusively owns this server's connection and tool catalog. The MCP
settings and composer inventory show its actual connection and tools as
managed by Computer Use, without generic registration or per-tool toggles;
generic MCP discovery does not expose a duplicate invocation route. Central tool
approvals and screenshot attachments apply through the same Computer Use path.
The settings inventory explains that its enabled labels are status indicators;
enable, disable or switch the provider in Execution → Computer Use.

The MCP-only **Allow access to signed-in browser profiles** checkbox is off by
default (`allow_existing_profile:false`). An explicit Save adds
`--grant existing-profile` to the selected runtime's launch arguments, without
rewriting `mcp_servers.json`. Existing grants in that file still apply. If
registration approvals are enabled, put the grant in the server's configured
arguments and approve that exact configuration first; approval of the original
configuration does not authorize different launch arguments. The UI selection
persists and is restored at application startup. This grant is not unrestricted
mode, does not create a DevTools endpoint, and cannot change the authorization
of an already-running shared upstream daemon. Native grants still require an
embedding authorization host. See the pinned upstream
[authorization guide](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/README.md).

## Validation

Run the execution/provider tests alongside security, Agent-loop, Host-plugin,
MCP, and frontend regression tests. `MYAGENT_CUA_SMOKE=1` additionally tests
actual SDK catalog discovery and orderly shutdown, without sending desktop
input. Real click/type tests require a dedicated test window and are not run
against the user's desktop automatically. Real Windows PTY/process tests run
locally; POSIX backends require Linux/macOS platform validation.
