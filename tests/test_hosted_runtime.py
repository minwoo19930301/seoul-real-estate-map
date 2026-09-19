"""Focused checks for the hosted runtime seams (no source databases required)."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.app import APIError, Handler, hosted_origin
from server.database import route


class HostedRuntimeTests(unittest.TestCase):
    def test_host_allowlist_requires_exact_canonical_host(self):
        env = {
            "SEOUL_ALLOW_HOSTED": "1",
            "SEOUL_ALLOWED_ORIGINS": "https://seoul-elevation.vercel.app",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(hosted_origin("https://seoul-elevation.vercel.app", "seoul-elevation.vercel.app"))
            self.assertFalse(hosted_origin("https://evil.vercel.app", "evil.vercel.app"))
            self.assertFalse(hosted_origin("https://seoul-elevation.vercel.app.evil.test", "seoul-elevation.vercel.app.evil.test"))

    def test_handler_rejects_unlisted_host_and_origin(self):
        request = SimpleNamespace(headers={"Host": "evil.example", "Origin": "https://evil.example"})
        with patch.dict(os.environ, {"SEOUL_ALLOW_HOSTED": "1", "SEOUL_ALLOWED_ORIGINS": "https://seoul-elevation.vercel.app"}, clear=False):
            with self.assertRaises(APIError):
                Handler.check_local(request)

    def test_turso_config_json_routes_without_a_file(self):
        payload = {"databases": {"terrain.sqlite": {"hostname": "example.turso.io", "token": "test", "metadata_table": "terrain_metadata", "bytes": 1}}}
        with patch.dict(os.environ, {"SEOUL_TURSO_CONFIG_JSON": json.dumps(payload)}, clear=False):
            self.assertEqual(route("/tmp/terrain.sqlite")["hostname"], "example.turso.io")

    def test_vercel_handler_routes_only_allowed_api_requests(self):
        import api.index as vercel_api
        from http.server import ThreadingHTTPServer

        class FakeAPI:
            metadata = {"source_year": 2023}

        previous = vercel_api._api
        vercel_api._api = FakeAPI()
        server = ThreadingHTTPServer(("127.0.0.1", 0), vercel_api.handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        env = {
            "SEOUL_ALLOW_HOSTED": "1",
            "SEOUL_ALLOWED_ORIGINS": "https://seoul-elevation.vercel.app",
        }

        def request(path, method="GET", host="seoul-elevation.vercel.app", origin="https://seoul-elevation.vercel.app"):
            req = urllib.request.Request(url + path, method=method, headers={"Host": host, "Origin": origin})
            try:
                with urllib.request.urlopen(req, timeout=3) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                return error.code

        try:
            with patch.dict(os.environ, env, clear=False):
                self.assertEqual(request("/api/health"), 200)
                self.assertEqual(request("/api/health", host="evil.example", origin="https://evil.example"), 403)
                self.assertEqual(request("/api/bookmarks", method="POST"), 405)
                self.assertEqual(request("/index.py", method="GET"), 404)
                self.assertEqual(request("/api/health", method="HEAD"), 404)
                self.assertEqual(request("/api/health", origin="http://localhost:4173"), 403)
        finally:
            server.shutdown()
            server.server_close()
            vercel_api._api = previous


if __name__ == "__main__":
    unittest.main()
