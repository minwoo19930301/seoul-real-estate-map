"""Restore large, immutable assets from the same commit during a hosted build.

GitHub Actions supplies its short-lived, read-only token only to the build.
No token is written to disk or included in client/runtime output.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]


def verify_assets(root=ROOT):
    manifest = json.loads((root / 'public/data/deployment-assets.json').read_text())
    for name, expected in manifest['files'].items():
        path = root / name
        if not path.is_file():
            raise ValueError(f'Missing deployment asset: {name}')
        with path.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() != expected:
                raise ValueError(f'Deployment asset checksum mismatch: {name}')
    return len(manifest['files'])


def extract_assets(archive, root):
    for member in archive:
        parts = PurePosixPath(member.name).parts[1:]
        if not member.isfile() or '..' in parts:
            continue
        relative = PurePosixPath(*parts)
        if not (relative.is_relative_to('public/models') or relative.is_relative_to('public/data/terrain')):
            continue
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile(member) as source, destination.open('wb') as output:
            shutil.copyfileobj(source, output)


def restore_assets(root=ROOT):
    ref = os.environ.get('SEOUL_ASSET_REF', '')
    token = os.environ.get('SEOUL_ASSET_TOKEN', '')
    if not re.fullmatch(r'[0-9a-f]{40}', ref) or not token:
        raise ValueError('A full immutable SEOUL_ASSET_REF and build-only SEOUL_ASSET_TOKEN are required')
    request = urllib.request.Request(
        f'https://api.github.com/repos/minwoo19930301/seoul-real-estate-map/tarball/{ref}',
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'User-Agent': 'seoul-real-estate-map-deploy'},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with tarfile.open(fileobj=response, mode='r|gz') as archive:
                extract_assets(archive, root)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'GitHub asset download failed (HTTP {error.code})') from None


if __name__ == '__main__':
    # Local builds can use the existing verified assets without any credentials.
    if not (ROOT / 'public/models').is_dir() or not (ROOT / 'public/data/terrain/14').is_dir():
        restore_assets()
    print(f'Verified {verify_assets()} deployment assets')
