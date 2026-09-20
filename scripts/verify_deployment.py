"""Check the deployed revision, real source counts, terrain, and a GLB asset."""
import hashlib
import json
import gzip
import sys
import time
from urllib.parse import urlencode
import urllib.request
import urllib.error

base, expected_sha = sys.argv[1:]


def read_response(path, accept_encoding=None):
    url = base.rstrip('/') + path
    request = urllib.request.Request(url)
    if accept_encoding:
        request.add_header('Accept-Encoding', accept_encoding)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        if response.headers.get('Content-Encoding', '').lower() == 'gzip':
            body = gzip.decompress(body)
        return body, response.headers


def read(path, accept_encoding=None):
    return read_response(path, accept_encoding)[0]


def json_response(path, accept_encoding='gzip'):
    body, headers = read_response(path, accept_encoding)
    return json.loads(body), headers


def assert_feature_collection(path, minimum=1):
    payload, _ = json_response(path)
    assert payload.get('type') == 'FeatureCollection', f'{path} did not return GeoJSON'
    features = payload.get('features')
    assert isinstance(features, list) and len(features) >= minimum, f'{path} returned too few features'
    return features


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

meta, _ = json_response('/api/meta')
assert meta['contours'] == 8570 and meta['spots'] == 45870, 'Source terrain data is missing'
assert read('/data/terrain/14/13970/6344.png').startswith(b'\x89PNG'), 'Terrain tile unavailable'
manifest = json.loads(read('/data/deployment-assets.json'))
model = next(path.removeprefix('public') for path in manifest['files'] if path.endswith('.glb'))
assert read(model).startswith(b'glTF'), '3D model unavailable'
assert b'<html' in read('/').lower(), 'Frontend unavailable'
references = json.loads(read('/models/reference-manifest.json'))
assert len(references['assets']) >= 125, 'Current reference models are missing'
for model_id in ['reference-flight-seoul-city-hall', 'reference-flight-ddp', 'maple-xi-210']:
    asset = next(a for a in references['assets'] if a['id'] == model_id)
    assert hashlib.sha256(read('/models/' + asset['model'])).hexdigest() == asset['sha256'], 'Reference model stale or corrupted: ' + model_id
assert any(p['name'] == '메이플자이' for p in references['places']), 'Maple Xi search location missing'
bespoke_bytes = read('/models/bespoke-manifest.json')
assert hashlib.sha256(bespoke_bytes).hexdigest() == manifest['files']['public/models/bespoke-manifest.json'], 'Bespoke manifest is stale'
bespoke = json.loads(bespoke_bytes)
assert {'bespoke-seoul-express-terminal', 'bespoke-skyl65-a', 'bespoke-skyl65-b', 'bespoke-skyl65-c', 'bespoke-skyl65-d', 'bespoke-banpo-jamsu', 'bespoke-culture-station-seoul284', 'bespoke-hyperion-a', 'bespoke-hyperion-b', 'bespoke-hyperion-c', 'bespoke-hyperion-parking-podium', 'bespoke-hyperion-department-store', 'bespoke-maple-xi-210', 'bespoke-maple-xi-211'} <= {a['id'] for a in bespoke['assets']}, 'Reviewed Blender models missing'
for asset in bespoke['assets']:
    assert hashlib.sha256(read('/models/' + asset['model'])).hexdigest() == asset['sha256'], 'Bespoke model stale or corrupted: ' + asset['id']

# Exercise the same calls used by the initial map view instead of accepting a
# deployment that only serves health metadata.  Keep this bbox small enough to
# be deterministic while still crossing populated Seoul source data.
bbox = '126.94,37.495,126.96,37.51'
search, _ = json_response('/api/places?' + urlencode({'q': '서울시청'}))
assert search.get('results'), 'Place search returned no Seoul City Hall result'
query = urlencode({'bbox': bbox, 'zoom': '15'})
assert_feature_collection('/api/features?' + query)
assert_feature_collection('/api/buildings?' + query)
assert_feature_collection('/api/roads?' + query)
assert_feature_collection('/api/landmarks?' + query)

# The server may be behind a CDN that strips Content-Encoding, but if it
# advertises gzip the verifier must decode it before parsing JSON.
_, headers = json_response('/api/features?' + query, accept_encoding='gzip')
if headers.get('Content-Encoding', '').lower() == 'gzip':
    assert headers.get('Vary', '').lower().find('accept-encoding') >= 0, 'gzip response missing Vary header'
print(f'Live release {expected_sha}: health, source data, search, GeoJSON map layers, terrain, all reviewed Blender models, gzip handling, and frontend verified')
