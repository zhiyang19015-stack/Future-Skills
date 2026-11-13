import gzip
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main  # noqa: E402


class TestLowData(unittest.TestCase):
    def test_text_is_compressed_when_the_browser_accepts_gzip(self):
        res = main.dispatch("GET", "/static/app.js")
        status, data, headers = main.low_data(res, "GET", {"Accept-Encoding": "gzip, br"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(data), res.body)
        self.assertLess(len(data), len(res.body) * 0.5)

    def test_no_compression_without_accept_encoding(self):
        res = main.dispatch("GET", "/static/app.js")
        _, data, headers = main.low_data(res, "GET", {})
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(data, res.body)

    def test_unchanged_file_costs_no_body(self):
        res = main.dispatch("GET", "/api/fields")
        _, _, first = main.low_data(res, "GET", {})
        status, data, _ = main.low_data(res, "GET", {"If-None-Match": first["ETag"]})
        self.assertEqual((status, data), (304, b""))
        status, _, _ = main.low_data(res, "GET", {"If-None-Match": '"something-else"'})
        self.assertEqual(status, 200)

    def test_post_answers_get_no_etag(self):
        res = main.dispatch("POST", "/api/questionnaire/score", b'{"answers": []}')
        _, _, headers = main.low_data(res, "POST", {"Accept-Encoding": "gzip"})
        self.assertNotIn("ETag", headers)

    def test_real_server_sends_gzip_and_304(self):
        server = main.ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/static/i18n.js"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})) as r:
                self.assertEqual(r.headers["Content-Encoding"], "gzip")
                etag, body = r.headers["ETag"], gzip.decompress(r.read())
            self.assertIn(b"LANG_KEY", body)
            with self.assertRaises(urllib.error.HTTPError) as again:
                urllib.request.urlopen(urllib.request.Request(url, headers={"If-None-Match": etag}))
            self.assertEqual(again.exception.code, 304)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
