"""Scoped review diagnostics carried by the existing tool/UI event commit."""
from __future__ import annotations

import logging
import time

logger = logging.getLogger('agent_harness')


def review_status(state, *, status, stage, tool='', tool_call_id='', reason='', coverage=''):
    return {
        'session_id': str(state.get('session_id') or ''),
        'run_id': str(state.get('_runtime_v2_run_id') or ''),
        'turn_id': str(state.get('_change_review_turn_id') or state.get('_runtime_v2_run_id') or ''),
        'tool_call_id': str(tool_call_id or ''), 'tool': tool,
        'status': status, 'stage': stage, 'coverage': coverage,
        'reason': str(reason)[:200],
        'at': time.time(),
    }


class ChangeReviewCapture:
    """One instance per invocation; concurrent tools never share error slots."""

    def __init__(self, callbacks, state, tool, args, tool_call_id):
        self.callbacks = callbacks
        self.state = state
        self.tool = tool
        self.args = args
        self.tool_call_id = tool_call_id
        self.status = None

    def _failed(self, stage, exc):
        logger.warning('change review %s snapshot failed for %s', stage, self.tool, exc_info=True)
        self.status = review_status(self.state, status='failed', stage=stage,
                                    tool=self.tool, tool_call_id=self.tool_call_id, reason=exc)

    def before(self, worktree_root='', *, observe_workspace=False):
        try:
            return self.callbacks().call('before_native_file_tool', self.state, self.tool,
                                         self.args, self.tool_call_id, worktree_root, observe_workspace)
        except Exception as exc:
            self._failed('before', exc)
            return None

    def after(self, capture, successful):
        if capture is None:
            return []
        try:
            result = self.callbacks().call('after_native_file_tool', self.state, capture, successful)
            self.status = review_status(self.state, status='checked', stage='after',
                                        tool=self.tool, tool_call_id=self.tool_call_id,
                                        coverage=getattr(result, 'coverage', getattr(capture, 'coverage', 'declared_paths')))
            return result or []
        except Exception as exc:
            self._failed('after', exc)
            return []

    def attach(self, response, changes):
        if changes or self.status:
            ui = dict(response.get('ui') or {})
            if changes:
                ui['changes'] = changes
            if self.status:
                ui['change_review_status'] = self.status
            response['ui'] = ui
        return response
