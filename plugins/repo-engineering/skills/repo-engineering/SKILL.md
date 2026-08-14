---
name: repo-engineering
description: Repository engineering workflow for code review, implementation, focused testing, changelog maintenance, and release readiness. Use when the user asks to inspect or change a repository, review uncommitted work, diagnose CI or runtime failures, prepare release notes, validate a frontend, or ready changes for commit or publication.
---

# Repo Engineering

Use the repository's own instructions first. Read `AGENTS.md`, status, nearby tests, and relevant configuration before changing code. Preserve unrelated changes in a dirty worktree.

## Workflow

1. Establish the requested outcome and inspect only the relevant paths.
2. Classify the work as review, diagnosis, implementation, documentation, or release preparation.
3. Prefer the smallest change that satisfies the request and preserves public behavior outside scope.
4. When globally available, use Context7 when current third-party library documentation affects the answer or implementation.
5. When globally available, use Playwright for browser-visible behavior, local UI flows, accessibility state, and console errors.
6. When globally available, use GitHub only for repository, PR, issue, Actions, or release state that is not available locally. Treat write tools as external side effects.
7. Run focused tests first, then broader checks proportional to risk. Report unrelated failures separately.
8. Review the final diff for accidental files, secrets, generated drift, and formatting errors.

## Task guidance

- For review-only requests, do not edit files. Lead with actionable findings and precise locations.
- For diagnosis-only requests, identify the cause and evidence; implement a fix only when requested.
- For frontend changes, build production assets when the repository checks them in and verify the actual interaction in a browser.
- For changelog or release work, derive facts from the diff and test results. Do not invent dates, issue numbers, or compatibility claims.
- Never commit, push, publish, install remote dependencies, or change external systems unless the user requested that action.
- Never write credentials to tracked files. Use environment-variable references supported by the host.

For this repository's layout and verification commands, read [references/myagent.md](references/myagent.md).
