"""
Cache layer for live blockchain API responses.

Uses real Redis if the `redis` package is importable AND REDIS_URL is
set - that is the production path (docs/BUILT_VS_ROADMAP.md documents
Redis as a next-step dependency). Otherwise falls back to a thread-safe
in-memory TTL dict with the exact same get/set/delete interface, so
`engine.chain_adapters` never has to know which backend it's talking
to, and this build still runs with zero extra pip installs.
"""
import json
import os
import threading
import time

_lock = threading.Lock()
_store = {}  # key -> (expires_at_epoch, value)

_redis_client = None
_redis_checked = False


def _get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis  # optional dependency - not in requirements.txt by default
        client = redis.from_url(url, socket_connect_timeout=1.5, socket_timeout=1.5)
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


def get(key):
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return None
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            _store.pop(key, None)
            return None
        return value


def set(key, value, ttl_seconds=120):
    client = _get_redis()
    if client is not None:
        try:
            client.setex(key, ttl_seconds, json.dumps(value))
            return
        except Exception:
            pass
    with _lock:
        _store[key] = (time.time() + ttl_seconds, value)


def delete(key):
    client = _get_redis()
    if client is not None:
        try:
            client.delete(key)
        except Exception:
            pass
    with _lock:
        _store.pop(key, None)


def backend_name():
    return "redis" if _get_redis() is not None else "in-memory"
