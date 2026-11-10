import http.client
from pathlib import Path
import threading
import unittest

from ariadne_mark.server import make_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.paths = []
        self.sizes = []
        outer = self
        class SDK:
            def verify(self, path):
                outer.paths.append(Path(path))
                outer.sizes.append(path.stat().st_size)
                if path.read_bytes() == b"bad":
                    raise ValueError("private content must not be in the response")
                return {"label": "Test fixture", "size": path.stat().st_size}
        self.server = make_server(SDK(), port=0, max_upload_mb=1)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_no_account_and_cleanup_on_success(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        status, body = self.request("POST", "/verify?format=png", b"fixture")
        self.assertEqual(status, 200)
        self.assertIn(b'Test fixture', body)
        self.assertNotIn(b'"size"', body)
        self.assertEqual(self.sizes, [7])
        self.assertFalse(self.paths[0].exists())
        self.assertFalse(self.paths[0].parent.exists())

    def test_error_is_not_a_negative_detection_and_temp_is_deleted(self):
        status, body = self.request("POST", "/verify?format=png", b"bad")
        self.assertEqual(status, 422)
        self.assertIn(b"not_checked", body)
        self.assertNotIn(b"private content", body)
        self.assertFalse(self.paths[0].parent.exists())

    def test_reject_unsupported_and_oversized_upload_before_inference(self):
        self.assertEqual(self.request("POST", "/verify?format=../../secret", b"x")[0], 415)
        self.assertEqual(self.request("POST", "/verify?format=png", b"", {"Content-Length": "1048577"})[0], 413)
        self.assertEqual(self.paths, [])


if __name__ == "__main__":
    unittest.main()
