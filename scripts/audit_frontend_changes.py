"""Static audit of every change our subagent work made to the FRONTEND.

Classifies changes into:
  A. 子代理专属新增（隔离，不影响主对话）
  B. 共享文件里的接线改动（可能影响主对话——逐个列出并给出风险评级）
  C. CSS 影响面（子代理规则是否可能命中主对话元素）

Run: python scripts/audit_frontend_changes.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(r'D:\AI\AI Agent\MyAgent Developer')

SHARED = [
    'frontend/src/app/index.js',
    'frontend/src/app/modules/event-dispatch.js',
    'frontend/src/app/modules/i18n.js',
    'frontend/src/app/modules/message-rendering.js',
    'frontend/src/app/modules/session-management.js',
    'frontend/src/app/modules/session-scroll-history.js',
    'frontend/src/app/modules/shared-state-and-dialogs.js',
    'frontend/src/app/modules/sse-handling.js',
    'frontend/src/app/state/session-event-reducer.js',
    'frontend/src/app/modules/dock/embedder/right-column.js',
    'frontend/index.html',
    'frontend/src/shell-body.html',
    'frontend/src/styles/app.css',
]


def git(*args: str) -> str:
    return subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8', cwd=ROOT).stdout


print('=' * 100)
print('A. 新增文件（子代理专属，运行时互相隔离）')
print('=' * 100)
status = git('status', '--short')
for line in status.splitlines():
    if line.startswith('??') and ('subagent' in line or 'ui-slot' in line):
        path = line[3:].strip()
        size = (ROOT / path).stat().st_size if (ROOT / path).is_file() else 0
        print(f'  + {path}  ({size} bytes)')

print()
print('=' * 100)
print('B. 共享文件的改动量（可能影响主对话）')
print('=' * 100)
for path in SHARED:
    diff = git('diff', '--numstat', '--', path).strip()
    if not diff:
        continue
    added, removed, _ = diff.split('\t')
    print(f'  ~ {path}: +{added} -{removed}')

print()
print('=' * 100)
print('C. 共享文件改动详情：只看"会影响主对话行为"的部分')
print('=' * 100)
INTERESTING = [
    'updateSessionTitle', 'renderSubagentAddressedTitle', 'switchSession',
    'clearOptionalPanelsForSessionLoad', 'clearTocForSessionLoad',
    'subagentCatalogUi', 'subagentComposerUi', 'subagentAddressing',
    'noteSubagentActivity', 'noteSubagentLifecycleFrame', 'agent_id',
    'smooth-follow', 'msg-wrap', 'process-aggregate', 'chat-stream',
]
for path in SHARED:
    diff = git('diff', '-U1', '--', path)
    if not diff.strip():
        continue
    lines = [ln for ln in diff.splitlines() if ln[:1] in '+-' and ln[:3] not in ('+++', '---')]
    hits = [ln for ln in lines if any(k in ln for k in INTERESTING)]
    if not hits:
        continue
    print(f'--- {path} ---')
    for ln in hits[:24]:
        print('   ', ln[:160])
    if len(hits) > 24:
        print(f'    ... 另有 {len(hits) - 24} 行')
    print()
