import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.prepare_hosted_assets import extract_assets, restore_assets, verify_assets


class HostedAssetTests(unittest.TestCase):
    def test_restores_assets_from_renamed_repository_at_exact_commit(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            item = tarfile.TarInfo('repo/public/models/a.glb')
            item.size = 4
            archive.addfile(item, io.BytesIO(b'data'))
        data.seek(0)
        commit = 'a' * 40
        with tempfile.TemporaryDirectory() as temp, \
                patch.dict('os.environ', {'SEOUL_ASSET_REF': commit, 'SEOUL_ASSET_TOKEN': 'test-only'}), \
                patch('scripts.prepare_hosted_assets.urllib.request.urlopen', return_value=data) as download:
            root = Path(temp)
            restore_assets(root)
            request = download.call_args.args[0]
            self.assertEqual(request.full_url, f'https://api.github.com/repos/minwoo19930301/seoul-real-estate-map/tarball/{commit}')
            self.assertEqual((root / 'public/models/a.glb').read_bytes(), b'data')

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
