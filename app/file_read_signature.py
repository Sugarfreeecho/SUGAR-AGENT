"""Metadata guards for rebuildable read caches, including NTFS ChangeTime."""
import os
from functools import lru_cache


def stat_signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@lru_cache(maxsize=1)
def _windows_query():
    import ctypes
    from ctypes import wintypes

    class BasicInfo(ctypes.Structure):
        _fields_ = [(name, ctypes.c_longlong) for name in ('creation', 'access', 'write', 'change')] + [('attributes', wintypes.DWORD)]

    query = ctypes.WinDLL('kernel32', use_last_error=True).GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    query.restype = wintypes.BOOL
    return query, BasicInfo


def signature(stream):
    """Query the already-open source; None disables reuse if identity is unknown."""
    info = os.fstat(stream.fileno())
    base = stat_signature(info)
    if not info.st_ino:
        return None
    if os.name != 'nt':
        return base
    import ctypes
    import msvcrt

    query, BasicInfo = _windows_query()
    value = BasicInfo()
    if not query(msvcrt.get_osfhandle(stream.fileno()), 0, ctypes.byref(value), ctypes.sizeof(value)):
        return None
    return (*base, value.change)
