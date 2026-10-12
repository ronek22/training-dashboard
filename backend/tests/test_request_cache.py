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


if __name__ == "__main__":
    unittest.main()
