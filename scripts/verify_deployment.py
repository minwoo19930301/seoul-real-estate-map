"""Check the deployed revision, real source counts, terrain, and a GLB asset."""
import json
import sys
import time
import urllib.request
import urllib.error

base, expected_sha = sys.argv[1:]


def read(path):
    with urllib.request.urlopen(base.rstrip('/') + path, timeout=60) as response:
        return response.read()


for attempt in range(12):
    try:
        health = json.loads(read('/api/health'))
        if health.get('status') == 'ok' and health.get('release_sha') == expected_sha:
            break
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass
    time.sleep(5)
else:
    raise SystemExit('The live deployment did not report the expected release SHA')

meta = json.loads(read('/api/meta'))
assert meta['contours'] == 8570 and meta['spots'] == 45870, 'Source terrain data is missing'
assert read('/data/terrain/14/13970/6344.png').startswith(b'\x89PNG'), 'Terrain tile unavailable'
manifest = json.loads(read('/data/deployment-assets.json'))
model = next(path.removeprefix('public') for path in manifest['files'] if path.endswith('.glb'))
assert read(model).startswith(b'glTF'), '3D model unavailable'
assert b'<html' in read('/').lower(), 'Frontend unavailable'
print(f'Live release {expected_sha}: API, source data, terrain, 3D model, and frontend verified')
