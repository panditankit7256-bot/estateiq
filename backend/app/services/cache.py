"""Tiny per-facility memoisation. Any ingestion bumps the facility version, which invalidates its cache."""
from __future__ import annotations
import functools, threading
from collections import defaultdict

_version: dict[str, int] = defaultdict(int)
_store: dict[tuple, object] = {}
_lock = threading.RLock()


def bump(fid: str) -> None:
    with _lock:
        _version[fid] += 1
        for k in [k for k in _store if k[1] == fid]:
            _store.pop(k, None)


def cached(fn):
    @functools.wraps(fn)
    def wrapper(fid: str, *args, **kwargs):
        key = (fn.__name__, fid, _version[fid], args, tuple(sorted(kwargs.items())))
        with _lock:
            if key in _store:
                return _store[key]
        val = fn(fid, *args, **kwargs)
        with _lock:
            _store[key] = val
        return val
    return wrapper
