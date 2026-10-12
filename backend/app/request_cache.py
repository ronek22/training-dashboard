"""Per-request memo for expensive read builders that one GET calls several times.

The dashboard alone serializes the same weekly plans three times over and rebuilds the full
strength session index once per strength helper. Inside a single read request the data does
not change, so the first result is kept and later callers get a deep copy (callers are free
to mutate what they receive). Outside a request scope, and for writes, nothing is cached.
"""

from __future__ import annotations

import copy
import os
import pickle
import sqlite3
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any, Callable, Hashable, Iterator, Optional

_cache: ContextVar[Optional[dict]] = ContextVar("request_cache", default=None)


@contextmanager
def request_scope() -> Iterator[None]:
    token = _cache.set({})
    try:
        yield
    finally:
        _cache.reset(token)


def memo(key: Hashable, build: Callable[[], Any]) -> Any:
    cache = _cache.get()
    if cache is None:
        return build()
    if key not in cache:
        value = build()
        try:
            # Plain dicts and lists: a pickle round trip copies several times faster than deepcopy.
            cache[key] = (pickle.dumps(value, pickle.HIGHEST_PROTOCOL), True)
        except (pickle.PicklingError, TypeError, AttributeError):
            cache[key] = (copy.deepcopy(value), False)
        return value
    stored, pickled = cache[key]
    return pickle.loads(stored) if pickled else copy.deepcopy(stored)


# Values derived only from a stored blob (an activity's streams JSON) stay valid for as long as
# the blob does, so they outlive the request. Keyed by the blob's length and hash, never the blob
# itself, so a few hundred entries cost almost nothing to keep.
_BLOB_CACHE_SIZE = 1024
_blob_cache: "OrderedDict[tuple, Any]" = OrderedDict()
_blob_lock = Lock()


def blob_memo(namespace: str, blob: str, build: Callable[[], Any]) -> Any:
    key = (namespace, len(blob), hash(blob))
    with _blob_lock:
        if key in _blob_cache:
            _blob_cache.move_to_end(key)
            return _blob_cache[key]
    value = build()
    with _blob_lock:
        _blob_cache[key] = value
        while len(_blob_cache) > _BLOB_CACHE_SIZE:
            _blob_cache.popitem(last=False)
    return value


# Whole-history builders (personal records) change only when the database does. A commit
# rewrites the database file, so its modification stamp works as a version: any write anywhere
# invalidates every entry. Only reads use it (inside a request scope), so a write request never
# sees a value from before its own uncommitted changes.
_DB_CACHE_SIZE = 64
_db_cache: "OrderedDict[tuple, Any]" = OrderedDict()


def _db_version(conn: sqlite3.Connection) -> Optional[tuple]:
    try:
        path = next((row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main"), "")
    except sqlite3.Error:
        return None
    if not path:
        return None
    try:
        stamps = [(stat.st_mtime_ns, stat.st_size) for stat in (os.stat(path),)]
        if os.path.exists(f"{path}-wal"):
            wal = os.stat(f"{path}-wal")
            stamps.append((wal.st_mtime_ns, wal.st_size))
    except OSError:
        return None
    return (path, *stamps)


def db_memo(conn: sqlite3.Connection, key: Hashable, build: Callable[[], Any]) -> Any:
    """Like ``memo``, but kept across reads until the database changes."""
    if _cache.get() is None:
        return build()
    version = _db_version(conn)
    if version is None:
        return memo(key, build)
    full_key = (key, version)
    with _blob_lock:
        stored = _db_cache.get(full_key)
        if stored is not None:
            _db_cache.move_to_end(full_key)
    if stored is not None:
        return pickle.loads(stored)
    value = build()
    # The build may have written (record caches do); only keep it if nothing changed meanwhile.
    if _db_version(conn) != version:
        return value
    try:
        stored = pickle.dumps(value, pickle.HIGHEST_PROTOCOL)
    except (pickle.PicklingError, TypeError, AttributeError):
        return value
    with _blob_lock:
        _db_cache[full_key] = stored
        while len(_db_cache) > _DB_CACHE_SIZE:
            _db_cache.popitem(last=False)
    return value
