"""Check the deployed revision, real source counts, terrain, and a GLB asset."""
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
print(f'Live release {expected_sha}: health, source data, search, GeoJSON map layers, terrain, 3D model, gzip handling, and frontend verified')
