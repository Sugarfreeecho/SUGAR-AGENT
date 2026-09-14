# DSH first-token latency (TTFT) report

- Workspace: `D:\AI\AI Agent\MyAgent Developer`
- Session logs: 7 (C:\Users\Sugarfreeecho\.dsh\sessions\--D-AI-AI~0020Agent-MyAgent~0020Developer--)
- Model filter: `deepseek/deepseek-v4.1-flash`
- Log window: 2026-09-11 .. 2026-09-11 (local time)
- Latest recorded step: 2026-09-11 18:08:38; report generated 2026-09-11 18:08:53
- Note: the session `session-6fc3c8e9` is still live and keeps appending steps, so its row grows after this cutoff.
- Note: DSH home was initialized 2026-09-11, so no session logs exist for earlier days in this workspace.
- Definition: `step/start` -> first non-empty token delta in the step stream (DSH sessionStats rule; an in-step retry keeps the original step start)

## Sessions

| session | created | depth | steps | llm steps (model) | with first token |
|---|---|---|---|---|---|
| 5d38204d-b24a-4268-997e-db71b1b7ee73 | 2026-09-11 11:32 | 2 | 31 | 31 | 31 |
| 8083629e-a669-41bd-8d52-7515428f963a | 2026-09-11 11:31 | 1 | 41 | 41 | 41 |
| a894cb85-f6c7-4e68-88c9-bae645e91398 | 2026-09-11 11:32 | 2 | 50 | 50 | 50 |
| c6ec2e03-361d-4149-bd75-22e4c4597391 | 2026-09-11 11:31 | 1 | 63 | 63 | 63 |
| e7d509a5-5b9c-4039-ade9-b4fdc784d361 | 2026-09-11 11:32 | 2 | 18 | 18 | 18 |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 2026-09-11 11:10 | 0 | 145 | 144 | 144 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 2026-09-11 11:28 | 0 | 230 | 230 | 230 |

## Per-day TTFT, `deepseek/deepseek-v4.1-flash`

| day | n | mean | min | p25 | median | p75 | p90 | p95 | max |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-11 | 577 | 4.52 | 2.06 | 2.86 | 3.34 | 4.20 | 5.65 | 6.91 | 130.61 |
| **all** | 577 | 4.52 | 2.06 | 2.86 | 3.34 | 4.20 | 5.65 | 6.91 | 130.61 |

All figures are seconds.

- Harness-side pre-request work inside a step (`step/start` -> `request/header`): n=7, mean 0.01s, median 0.01s, p90 0.01s, max 0.01s
- API-only view (`request/header` -> first token): mean 4.11s, median 3.39s, p90 6.27s, max 6.78s

## By hour of day (local)

| hour | n | median | p90 | max | steps >= 10s |
|---|---|---|---|---|---|
| 11:00 | 289 | 2.94 | 3.87 | 46.34 | 3 |
| 14:00 | 48 | 4.22 | 23.84 | 29.66 | 6 |
| 15:00 | 74 | 3.11 | 7.04 | 29.04 | 6 |
| 16:00 | 115 | 4.00 | 5.64 | 130.61 | 1 |
| 17:00 | 50 | 4.54 | 6.13 | 8.96 | 0 |
| 18:00 | 1 | 7.58 | 7.58 | 7.58 | 0 |

## TTFT against prompt size (input + cache-read tokens)

| prompt tokens | n | median | p90 | max |
|---|---|---|---|---|
| 0k-10k | 8 | 3.47 | 6.19 | 6.79 |
| 10k-30k | 29 | 2.73 | 3.61 | 36.24 |
| 30k-100k | 137 | 2.69 | 3.31 | 31.66 |
| >=100k | 402 | 3.73 | 6.03 | 130.61 |

Spearman rho (prompt tokens vs TTFT) = 0.718 over 576 steps

## Distribution

- 2026-09-11: 0-1s:0  1-2s:0  2-3s:191  3-5s:299  5-10s:71  10-20s:1  >=20s:15
- all: 0-1s:0  1-2s:0  2-3s:191  3-5s:299  5-10s:71  10-20s:1  >=20s:15

## Turn-opening TTFT (step 1 of each turn: what a human waits for after sending a prompt)

| session | turn | start (local) | TTFT s | prompt tokens |
|---|---|---|---|---|
| session-47250bb0-0125-456c-880f-5cd537a006cf | 2 | 2026-09-11 11:30:59 | 6.79 | 8619 |
| 8083629e-a669-41bd-8d52-7515428f963a | 1 | 2026-09-11 11:31:33 | 3.32 | 9309 |
| c6ec2e03-361d-4149-bd75-22e4c4597391 | 1 | 2026-09-11 11:31:33 | 3.40 | 9411 |
| 5d38204d-b24a-4268-997e-db71b1b7ee73 | 1 | 2026-09-11 11:32:55 | 2.84 | 9338 |
| e7d509a5-5b9c-4039-ade9-b4fdc784d361 | 1 | 2026-09-11 11:32:55 | 3.67 | 9207 |
| a894cb85-f6c7-4e68-88c9-bae645e91398 | 1 | 2026-09-11 11:32:55 | 2.88 | 9314 |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 3 | 2026-09-11 11:56:53 | 6.08 | 172270 |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4 | 2026-09-11 14:39:12 | 7.07 | 196577 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 1 | 2026-09-11 15:50:30 | 5.94 | 8591 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 2 | 2026-09-11 15:56:17 | 7.28 | 79458 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 3 | 2026-09-11 16:03:46 | 8.90 | 151394 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 4 | 2026-09-11 16:18:35 | 6.78 | 205110 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 5 | 2026-09-11 16:30:52 | 7.49 | 232393 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 6 | 2026-09-11 17:04:59 | 6.73 | 265082 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 7 | 2026-09-11 17:27:43 | 6.87 | 265954 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 8 | 2026-09-11 17:45:29 | 8.96 | 332175 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 9 | 2026-09-11 17:48:54 | 4.33 | 346029 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 10 | 2026-09-11 18:08:38 | 7.58 | 352659 |

Turn-opening TTFT: n=18, mean 5.94s, median 6.75s, p90 7.98s, max 8.96s

## Outliers and retry-affected steps (top 15 by TTFT)

| session | turn/step | start (local) | TTFT s | attempt retries | retry delay s | model |
|---|---|---|---|---|---|---|
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 4/6 | 2026-09-11 16:20:12 | 130.61 | 1 | 0.47 | deepseek/deepseek-v4.1-flash |
| 8083629e-a669-41bd-8d52-7515428f963a | 1/21 | 2026-09-11 11:32:56 | 46.34 | 1 | 0.54 | deepseek/deepseek-v4.1-flash |
| c6ec2e03-361d-4149-bd75-22e4c4597391 | 1/4 | 2026-09-11 11:31:47 | 36.24 | 1 | 0.45 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 2/10 | 2026-09-11 11:31:52 | 31.66 | 1 | 0.54 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/25 | 2026-09-11 14:49:09 | 29.66 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/51 | 2026-09-11 15:01:04 | 29.04 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/52 | 2026-09-11 15:01:36 | 28.00 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/54 | 2026-09-11 15:02:44 | 27.54 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/50 | 2026-09-11 15:00:35 | 27.08 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/23 | 2026-09-11 14:48:10 | 26.16 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/26 | 2026-09-11 14:49:40 | 25.83 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/53 | 2026-09-11 15:02:14 | 25.62 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/21 | 2026-09-11 14:47:07 | 25.24 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/22 | 2026-09-11 14:47:45 | 23.98 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 4/24 | 2026-09-11 14:48:37 | 23.77 | 0 | 0.00 | deepseek/deepseek-v4.1-flash |

- Steps with at least one in-step retry: 6 of 577
  - retry-affected TTFT: mean 42.84s, median 33.95s, max 130.61s
- Retry-free steps: mean 4.12s, median 3.33s, p90 5.55s, p95 6.73s, max 29.66s

## Every provider/model seen in these logs (all steps)

- command / deepseek/deepseek-v4.1-flash: 577
- ? / ?: 1

## Steps on the filtered model with no recorded first token: 0

## Per-session TTFT (filtered model)

| session | n | mean | median | p90 | max |
|---|---|---|---|---|---|
| 5d38204d-b24a-4268-997e-db71b1b7ee73 | 31 | 2.83 | 2.74 | 3.16 | 4.10 |
| 8083629e-a669-41bd-8d52-7515428f963a | 41 | 4.26 | 3.10 | 3.89 | 46.34 |
| a894cb85-f6c7-4e68-88c9-bae645e91398 | 50 | 3.07 | 2.92 | 3.56 | 8.32 |
| c6ec2e03-361d-4149-bd75-22e4c4597391 | 63 | 3.94 | 3.00 | 5.25 | 36.24 |
| e7d509a5-5b9c-4039-ade9-b4fdc784d361 | 18 | 2.62 | 2.50 | 2.92 | 3.67 |
| session-47250bb0-0125-456c-880f-5cd537a006cf | 144 | 5.67 | 3.34 | 6.77 | 31.66 |
| session-6fc3c8e9-d8a7-4a93-8252-3465104fb6de | 230 | 4.70 | 3.92 | 5.72 | 130.61 |
