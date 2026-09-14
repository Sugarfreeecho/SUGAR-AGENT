"""Bounded validation memo. Callers still hash bytes on every disk read."""
import threading
from collections import OrderedDict

_validated = OrderedDict()
_lock = threading.Lock()


def verify_once(signature, validate):
    with _lock:
        if signature in _validated:
            _validated.move_to_end(signature)
            return
    validate()
    with _lock:
        _validated[signature] = True
        while len(_validated) > 1024:
            _validated.popitem(last=False)
