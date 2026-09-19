import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from scripts.prepare_hosted_assets import extract_assets, verify_assets


class HostedAssetTests(unittest.TestCase):
    def test_extracts_only_regular_assets_without_path_traversal(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w') as archive:
            for name in ['repo/public/models/a.glb', 'repo/public/data/terrain/a.png', 'repo/server/app.py', 'repo/public/models/../../escape']:
                item = tarfile.TarInfo(name)
                item.size = 4
                archive.addfile(item, io.BytesIO(b'data'))
            link = tarfile.TarInfo('repo/public/models/link')
            link.type = tarfile.SYMTYPE
            link.linkname = '/tmp/outside'
            archive.addfile(link)
        data.seek(0)
        with tempfile.TemporaryDirectory() as temp, tarfile.open(fileobj=data) as archive:
            root = Path(temp)
            extract_assets(archive, root)
            self.assertEqual({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}, {'public/models/a.glb', 'public/data/terrain/a.png'})

    def test_manifest_rejects_missing_or_changed_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'public/data').mkdir(parents=True)
            file = root/'public/data/a.png'
            (root/'public/data/deployment-assets.json').write_text(json.dumps({'files': {'public/data/a.png': hashlib.sha256(b'data').hexdigest()}}))
            with self.assertRaises(ValueError): verify_assets(root)
            file.write_bytes(b'data')
            self.assertEqual(verify_assets(root), 1)
            file.write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_assets(root)
