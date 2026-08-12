# Egress helper protocol v1

SugarAgent uses an optional operating-system launcher to enforce the network decision
made by the application policy. The application never reports strong isolation
unless the helper passes the health handshake below.

## Discovery and health

The helper is resolved from `SUGAR_AGENT_EGRESS_HELPER`, then from
`app/native/sugaragent-egress-helper[.exe]`, then from `PATH`.

```text
sugaragent-egress-helper health --json
```

Successful implementations exit with zero and print one JSON object. Full
destination-scoped backends report `strong`; backends that can deny all network
for local commands but cannot constrain an approved connection report `partial`:

```json
{"protocol":1,"enforcement":"strong","backend":"windows-wfp"}
```

Bundled backend names are `windows-appcontainer`, `linux-network-namespace` and
`macos-sandbox-profile`. Future signed system components use `windows-wfp`,
`linux-cgroup-bpf` and `macos-network-extension`. Missing, unhealthy or
incompatible helpers cause an explicit `degraded` application-policy fallback.

Set `EGRESS_HELPER_ENABLED=0` to disable helper discovery and command wrapping
entirely. This keeps application-level command analysis and approvals enabled.

## Atomic launch

```text
sugaragent-egress-helper launch --ticket BASE64URL_JSON -- executable args...
```

The helper must verify the HMAC envelope using the one-process session key,
remove `SUGAR_AGENT_EGRESS_SESSION_KEY` from the child environment, install the
policy before the first child instruction, launch the command, forward standard
I/O and signals, and return the child's exit code.

Ticket payloads contain the protocol version, ticket/session/request IDs,
command digest, `deny` or `allow` network mode, egress intent, normalized
destination constraints, wildcard marker, issue/expiry times and a nonce.
Nonces are single-use. All descendants inherit the root policy and cannot
request a broader policy.

## Bundled implementation

- Windows: the build script creates a small native `.exe`. No-network commands
  run in an AppContainer without network capabilities. The optional
  `-InstallAcl` switch grants that AppContainer read/execute access to the
  application and modify access to the workspace when the repository ACLs do
  not already permit it. While enabled, Windows `run_shell` uses the system
  PowerShell backend because arbitrary Git Bash installations are not normally
  AppContainer-readable.
- Ubuntu: the bundled dependency-free launcher creates a user and network
  namespace for no-network commands with `unshare`.
- macOS: where available, the bundled launcher applies a deny-network sandbox
  profile to no-network commands.

These bundled implementations report `partial`: they block unapproved network
for the complete process tree, but an approved network command is not limited
to the parsed host. The application approval policy still applies before it is
launched.

## Strong backend requirements

- Windows: register the suspended root and descendants with WFP before resume;
  filter IPv4, IPv6 and DNS, and bind policy to the process tree.
- Ubuntu: place the suspended root in a dedicated cgroup before resume and
  attach connect/send eBPF hooks (or an equivalent network namespace policy).
- macOS: register the source process audit token with the Network Extension
  before resume and propagate the policy to descendants.

For known destinations, the helper denies connections outside the ticket's
host/IP, protocol and port set. Wildcard tickets are valid for one execution
only. Full-access mode intentionally bypasses the helper.
