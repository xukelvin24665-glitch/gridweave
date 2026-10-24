from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gridweave.models import Scenario
from gridweave.server import Handler
from test_scheduler import tiny


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, data=None, headers=None):
        request = Request(self.base + path, data=data, headers=headers or {})
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, response.read(), response.headers
        except HTTPError as response:
            return response.code, response.read(), response.headers

    def test_health_and_assets(self):
        status, body, headers = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ok")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        for path in ("/", "/app.js", "/styles.css", "/favicon.svg"):
            self.assertEqual(self.request(path)[0], 200, path)

    def test_invalid_query_and_traversal(self):
        for query in ("seed=-1", "seed=3.5", "scenario=unknown", "carbon_price=nan", "battery=11"):
            with self.subTest(query=query):
                self.assertEqual(self.request("/api/experiment?" + query)[0], 400)
        self.assertEqual(self.request("/../../pyproject.toml")[0], 404)

    def test_custom_scenario_end_to_end(self):
        payload = json.dumps({"scenario": tiny().to_dict(), "carbon_price": 80}).encode()
        status, body, _ = self.request("/api/solve", payload, {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["errors"], {})
        self.assertEqual(len(result["policies"]), 5)

    def test_rejects_malformed_and_cross_origin_writes(self):
        for payload in (b"{", b"[]", b'{"scenario":{}}'):
            self.assertEqual(self.request("/api/solve", payload, {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("/api/solve", b"{}", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/api/solve", b"{}", {"Content-Type": "application/json", "Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/api/solve", b" " * 262145, {"Content-Type": "application/json"})[0], 413)
        self.assertEqual(self.request("/api/health", headers={"Host": "attacker.example"})[0], 403)


if __name__ == "__main__":
    unittest.main()
