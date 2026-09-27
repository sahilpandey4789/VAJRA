import unittest
import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import cache


def _k(name):
    return f"test:{name}:{time.monotonic_ns()}"


class TestInMemoryCache(unittest.TestCase):
    def setUp(self):
        # ensure no REDIS_URL leaks into these tests forcing the redis path
        self._orig_redis_url = os.environ.pop("REDIS_URL", None)
        cache._redis_checked = False
        cache._redis_client = None

    def tearDown(self):
        if self._orig_redis_url is not None:
            os.environ["REDIS_URL"] = self._orig_redis_url
        cache._redis_checked = False
        cache._redis_client = None

    def test_get_on_missing_key_returns_none(self):
        self.assertIsNone(cache.get(_k("missing")))

    def test_set_then_get_roundtrips_the_value(self):
        key = _k("roundtrip")
        cache.set(key, {"hello": "world"}, ttl_seconds=60)
        self.assertEqual(cache.get(key), {"hello": "world"})

    def test_set_then_get_roundtrips_a_list_value(self):
        key = _k("listval")
        cache.set(key, [1, 2, 3], ttl_seconds=60)
        self.assertEqual(cache.get(key), [1, 2, 3])

    def test_overwriting_a_key_returns_the_newest_value(self):
        key = _k("overwrite")
        cache.set(key, "first", ttl_seconds=60)
        cache.set(key, "second", ttl_seconds=60)
        self.assertEqual(cache.get(key), "second")

    def test_delete_removes_the_key(self):
        key = _k("todelete")
        cache.set(key, "value", ttl_seconds=60)
        cache.delete(key)
        self.assertIsNone(cache.get(key))

    def test_delete_on_nonexistent_key_does_not_raise(self):
        cache.delete(_k("never-existed"))  # should simply not throw

    def test_expired_entry_returns_none(self):
        key = _k("expired")
        # write directly into the store with an already-past expiry,
        # bypassing set()'s ttl_seconds-from-now math to test expiry
        # deterministically without sleeping in a test.
        with cache._lock:
            cache._store[key] = (time.time() - 1, "stale-value")
        self.assertIsNone(cache.get(key))

    def test_expired_entry_is_evicted_from_store_on_read(self):
        key = _k("evict")
        with cache._lock:
            cache._store[key] = (time.time() - 1, "stale-value")
        cache.get(key)  # triggers eviction
        with cache._lock:
            self.assertNotIn(key, cache._store)

    def test_unexpired_entry_is_returned(self):
        key = _k("fresh")
        with cache._lock:
            cache._store[key] = (time.time() + 60, "fresh-value")
        self.assertEqual(cache.get(key), "fresh-value")

    def test_backend_name_is_in_memory_without_redis_url(self):
        self.assertEqual(cache.backend_name(), "in-memory")

    def test_set_accepts_default_ttl_without_error(self):
        key = _k("defaultttl")
        cache.set(key, "value")  # no explicit ttl_seconds
        self.assertEqual(cache.get(key), "value")

    def test_concurrent_sets_from_multiple_threads_do_not_corrupt_store(self):
        keys = [_k(f"thread{i}") for i in range(20)]

        def worker(k, v):
            cache.set(k, v, ttl_seconds=60)

        threads = [threading.Thread(target=worker, args=(k, i)) for i, k in enumerate(keys)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i, k in enumerate(keys):
            self.assertEqual(cache.get(k), i)

    def test_get_redis_returns_none_when_no_redis_url_set(self):
        self.assertIsNone(cache._get_redis())

    def test_get_redis_result_is_memoized_after_first_check(self):
        cache._get_redis()
        self.assertTrue(cache._redis_checked)


if __name__ == "__main__":
    unittest.main()
