import os
import sqlite3
import tempfile
import time
import unittest

from backend.app import request_cache


class RequestMemoTests(unittest.TestCase):
    def test_builds_once_per_scope_and_hands_out_copies(self):
        calls = []

        def build():
            calls.append(1)
            return {"days": [{"id": 1}]}

        with request_cache.request_scope():
            first = request_cache.memo("plan", build)
            first["days"].append({"id": 2})
            second = request_cache.memo("plan", build)
            second["days"][0]["id"] = 99
            third = request_cache.memo("plan", build)
        self.assertEqual(len(calls), 1)
        self.assertEqual(third, {"days": [{"id": 1}]})

    def test_new_scope_rebuilds(self):
        calls = []
        for _ in range(2):
            with request_cache.request_scope():
                request_cache.memo("plan", lambda: calls.append(1) or [])
        self.assertEqual(len(calls), 2)

    def test_no_scope_never_caches(self):
        calls = []
        request_cache.memo("plan", lambda: calls.append(1))
        request_cache.memo("plan", lambda: calls.append(1))
        self.assertEqual(len(calls), 2)

    def test_unpicklable_values_still_copy(self):
        with request_cache.request_scope():
            first = request_cache.memo("fn", lambda: {"f": lambda: None, "items": []})
            first["items"].append(1)
            self.assertEqual(request_cache.memo("fn", lambda: None)["items"], [])


class BlobMemoTests(unittest.TestCase):
    def test_same_blob_reuses_and_changed_blob_rebuilds(self):
        calls = []
        build = lambda: calls.append(1) or len(calls)
        self.assertEqual(request_cache.blob_memo("t", '{"a": 1}', build), 1)
        self.assertEqual(request_cache.blob_memo("t", '{"a": 1}', build), 1)
        self.assertEqual(request_cache.blob_memo("t", '{"a": 2}', build), 2)
        self.assertEqual(request_cache.blob_memo("other", '{"a": 1}', build), 3)


class DbMemoTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("CREATE TABLE t (v INTEGER)")
        self.conn.commit()
        request_cache._db_cache.clear()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.path)

    def _read(self, calls):
        with request_cache.request_scope():
            return request_cache.db_memo(self.conn, "sum", lambda: calls.append(1) or self.conn.execute("SELECT COALESCE(SUM(v), 0) FROM t").fetchone()[0])

    def test_reuses_across_requests_until_the_database_changes(self):
        calls = []
        self.assertEqual(self._read(calls), 0)
        self.assertEqual(self._read(calls), 0)
        self.assertEqual(len(calls), 1)
        time.sleep(0.01)
        self.conn.execute("INSERT INTO t VALUES (5)")
        self.conn.commit()
        self.assertEqual(self._read(calls), 5)
        self.assertEqual(len(calls), 2)

    def test_outside_a_request_always_builds(self):
        calls = []
        for _ in range(2):
            request_cache.db_memo(self.conn, "sum", lambda: calls.append(1))
        self.assertEqual(len(calls), 2)

    def test_in_memory_database_is_cached_per_request_only(self):
        conn = sqlite3.connect(":memory:")
        calls = []
        for _ in range(2):
            with request_cache.request_scope():
                request_cache.db_memo(conn, "x", lambda: calls.append(1))
                request_cache.db_memo(conn, "x", lambda: calls.append(1))
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
