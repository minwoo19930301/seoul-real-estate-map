"""Verify deployment assets without downloading shared geometry per instance."""
import hashlib


class AssetVerifier:
    def __init__(self, read):
        self.read = read
        self.expected = {}
        self.verified = {}

    def expect(self, path, expected_sha):
        previous = self.expected.get(path)
        if previous is not None and previous != expected_sha:
            raise AssertionError('Conflicting asset hashes: ' + path)
        self.expected[path] = expected_sha

    def verify(self, path, expected_sha, label, require_glb=False):
        self.expect(path, expected_sha)
        if path not in self.verified:
            body = self.read(path)
            assert hashlib.sha256(body).hexdigest() == expected_sha, label
            self.verified[path] = body.startswith(b'glTF')
        if require_glb:
            assert self.verified[path], '3D model unavailable: ' + path

    def verify_models(self, assets, label):
        # Check every record before issuing requests, including conflicting clones.
        for asset in assets:
            self.expect('/models/' + asset['model'], asset['sha256'])
        for asset in assets:
            self.verify('/models/' + asset['model'], asset['sha256'], label + asset['id'])
