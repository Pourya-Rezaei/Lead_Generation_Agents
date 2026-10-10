import sqlite3

from src.execution.cache import ExecutionCache
from src.migrations import migrate


def test_cache_hit_and_force_refresh_key():
    with sqlite3.connect(":memory:") as db:
        migrate(db)
        cache = ExecutionCache(db)
        request = {"query": "cafe", "location": "Tehran"}
        cache.put(request, {"completed_steps": ["places"]})
        assert cache.get(request)["completed_steps"] == ["places"]
        assert cache.get({**request, "force_refresh": True}) is None
