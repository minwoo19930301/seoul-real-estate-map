"""Local HTTP transport checks without production databases or external requests."""
import gzip
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from server.app import Handler, create_server


class TransportAPI:
    metadata = {'source_year': 2023}

    def meta(self):
        return {'source_year': 2023, 'name': '서울 원본 도형',
                'features': [{'id': i, 'name': '서울 나무·건물', 'height_m': 17.25} for i in range(200)]}


class CompressionTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        assets = cls.directory / 'assets'
        assets.mkdir()
        cls.javascript = ("export const names = " + json.dumps(['서울숲', '남산'] * 400, ensure_ascii=False) + ';\n').encode()
        cls.gzip_javascript = gzip.compress(cls.javascript, mtime=0)
        (assets / 'app-test.js').write_bytes(cls.javascript)
        (assets / 'app-test.js.gz').write_bytes(cls.gzip_javascript)
        cls.small_javascript = b'export const ready = true;\n'
        (assets / 'small.js').write_bytes(cls.small_javascript)
        cls.api = TransportAPI()
        cls.server = create_server(cls.api, 0, cls.directory)
        cls.addClassCleanup(cls.server.server_close)
        cls.log_patch = patch.object(Handler, 'log_message')
        cls.log_patch.start()
        cls.addClassCleanup(cls.log_patch.stop)
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)

    @classmethod
    def stop_server(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def request(self, path, encoding=None, origin=None):
        headers = {}
        if encoding is not None:
            headers['Accept-Encoding'] = encoding
        if origin is not None:
            headers['Origin'] = origin
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
            return response.status, {name.lower(): value for name, value in response.getheaders()}, response.read()
        finally:
            connection.close()

    def assert_vary(self, headers, *expected):
        fields = {field.strip().lower() for field in headers.get('vary', '').split(',')}
        self.assertTrue(set(expected).issubset(fields), f'Vary missing {expected}: {headers.get("vary")}')

    def test_large_json_gzip_round_trip_retains_exact_original_bytes(self):
        plain_status, plain_headers, plain = self.request('/api/meta', 'identity')
        status, headers, compressed = self.request('/api/meta', 'br, gzip;q=0.8', 'http://localhost:4173')
        self.assertEqual((plain_status, status), (200, 200))
        self.assertGreater(len(plain), 1024)
        self.assertNotIn('content-encoding', plain_headers)
        self.assertEqual(headers['content-encoding'], 'gzip')
        self.assertEqual(gzip.decompress(compressed), plain)
        self.assertEqual(json.loads(plain), self.api.meta())
        self.assertLess(len(compressed), len(plain))
        self.assertEqual(int(headers['content-length']), len(compressed))
        self.assertEqual(int(plain_headers['content-length']), len(plain))
        self.assertEqual(headers['content-type'], 'application/json; charset=utf-8')
        self.assertEqual(headers['access-control-allow-origin'], 'http://localhost:4173')
        self.assertEqual(headers['cache-control'], 'no-store')
        self.assert_vary(headers, 'accept-encoding', 'origin')
        self.assert_vary(plain_headers, 'accept-encoding', 'origin')

    def test_json_explicit_gzip_rejection_and_identity_remain_unencoded(self):
        for encoding in [None, 'identity', 'gzip;q=0', 'gzip;q=0.000, br;q=1', 'gzip;q=0, *;q=1']:
            with self.subTest(encoding=encoding):
                status, headers, body = self.request('/api/meta', encoding)
                self.assertEqual(status, 200)
                self.assertNotIn('content-encoding', headers)
                self.assertEqual(json.loads(body), self.api.meta())
                self.assertEqual(int(headers['content-length']), len(body))
                self.assert_vary(headers, 'accept-encoding', 'origin')

    def test_small_json_is_not_compressed_even_when_gzip_is_accepted(self):
        status, headers, body = self.request('/api/health', 'gzip')
        self.assertEqual(status, 200)
        self.assertLess(len(body), 1024)
        self.assertNotIn('content-encoding', headers)
        self.assertEqual(json.loads(body), {'status': 'ok', 'source_year': 2023, 'database': 'ready'})
        self.assertEqual(int(headers['content-length']), len(body))
        self.assert_vary(headers, 'accept-encoding', 'origin')

    def test_precompressed_javascript_has_original_mime_and_encoded_length(self):
        status, headers, body = self.request('/assets/app-test.js?v=transport-test', 'gzip')
        self.assertEqual(status, 200)
        self.assertEqual(headers['content-encoding'], 'gzip')
        self.assertIn(headers['content-type'].split(';')[0], ['text/javascript', 'application/javascript'])
        self.assertEqual(body, self.gzip_javascript)
        self.assertEqual(gzip.decompress(body), self.javascript)
        self.assertEqual(int(headers['content-length']), len(body))
        self.assert_vary(headers, 'accept-encoding')

    def test_precompressed_javascript_identity_also_varies_by_accept_encoding(self):
        for encoding in [None, 'identity', 'gzip;q=0', 'br, gzip;q=0.000']:
            with self.subTest(encoding=encoding):
                status, headers, body = self.request('/assets/app-test.js', encoding)
                self.assertEqual(status, 200)
                self.assertNotIn('content-encoding', headers)
                self.assertEqual(body, self.javascript)
                self.assertEqual(int(headers['content-length']), len(body))
                self.assertIn(headers['content-type'].split(';')[0], ['text/javascript', 'application/javascript'])
                self.assert_vary(headers, 'accept-encoding')

    def test_small_static_asset_without_sidecar_remains_original(self):
        status, headers, body = self.request('/assets/small.js', 'gzip')
        self.assertEqual(status, 200)
        self.assertNotIn('content-encoding', headers)
        self.assertEqual(body, self.small_javascript)
        self.assertEqual(int(headers['content-length']), len(body))


if __name__ == '__main__':
    unittest.main()
