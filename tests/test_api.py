"""Integration checks against the imported public source and a temporary HTTP API.

Run after scripts/build_database.py with: python -m unittest discover -s tests -v
No production server or production bookmark database is started or modified.
"""
from __future__ import annotations

import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode

import numpy as np
from shapely.geometry import shape, box

from scripts.build_database import build_database, DEFAULT_SOURCE
from server.app import TerrainAPI, create_server, MAX_CONTOURS, MAX_COORDINATES, MAX_SPOTS

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "terrain.sqlite"


class APIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DATABASE.exists():
            raise RuntimeError("Build the source database before running integration tests")
        cls.temp = tempfile.TemporaryDirectory()
        cls.bookmark_path = Path(cls.temp.name) / "bookmarks.sqlite"
        cls.api = TerrainAPI(DATABASE, cls.bookmark_path)
        cls.server = create_server(cls.api, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def request(self, path, method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=30)
        headers = dict(headers or {})
        if isinstance(body, dict):
            body = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read()), dict(response.getheaders())
        finally:
            connection.close()

    def features(self, bbox="127.04,37.535,127.06,37.555", **options):
        return self.request("/api/features?" + urlencode({"bbox": bbox, **options}))

    def test_health_and_metadata_retain_source_provenance(self):
        status, health, _ = self.request("/api/health")
        self.assertEqual((status, health["status"]), (200, "ok"))
        status, meta, _ = self.request("/api/meta")
        self.assertEqual(status, 200)
        self.assertEqual((meta["contours"], meta["spots"]), (8570, 45870))
        self.assertEqual(meta["source_crs_epsg"], 5174)
        self.assertEqual(meta["source_year"], 2023)
        self.assertEqual(meta["vertical_datum"], "unverified")
        self.assertEqual(meta["database_bytes"], DATABASE.stat().st_size)
        self.assertEqual(meta["source_bytes"], DEFAULT_SOURCE.stat().st_size)
        self.assertLess(meta["spot_height_range_m"][0], 0)
        self.assertIn("OA-22241", meta["source_url"])

    def test_mobility_http_uses_bounded_local_ground_routes(self):
        status, result, _ = self.request('/api/mobility?' + urlencode({'bbox': '126.980,37.545,126.994,37.557'}))
        self.assertEqual(status, 200)
        self.assertTrue(result['metadata']['available'])
        self.assertGreater(len(result['routes']), 0)
        self.assertLessEqual(len(result['routes']), 60)
        self.assertEqual({r['kind'] for r in result['routes']}, {'pedestrian', 'car'})
        for route in result['routes']:
            self.assertGreaterEqual(len(route['coordinates']), 2)
            for point in route['coordinates']:
                self.assertEqual(len(point), 3)
                self.assertTrue(all(np.isfinite(n) for n in point))
                self.assertLess(point[2], 800)
        for query in ['', '?bbox=126,37,128,39', '?bbox=126.98,37.545,126.994,37.557&zoom=17', '?bbox=NaN,37,127,38']:
            with self.subTest(query=query):
                status, _, _ = self.request('/api/mobility' + query)
                self.assertEqual(status, 400)

    def test_actual_source_spot_is_returned_at_its_coordinate(self):
        with self.api.connect() as db:
            row = db.execute("SELECT id,x,y,height_m FROM spots WHERE height_m<0 ORDER BY id LIMIT 1").fetchone()
        lon, lat = self.api.to_wgs.transform(row["x"], row["y"])
        status, result, _ = self.request("/api/elevation?" + urlencode({"lon": lon, "lat": lat}))
        self.assertEqual(status, 200)
        self.assertEqual(result["method"], "nearest_source_spot")
        self.assertEqual(result["nearest"]["id"], f"spot-{row['id']}")
        self.assertEqual(result["nearest"]["height_m"], row["height_m"])
        self.assertLess(result["nearest"]["height_m"], 0)
        self.assertLess(result["nearest"]["distance_m"], 0.1)
        self.assertEqual(result["nearest"]["coordinate"], [lon, lat])

    def test_nearest_result_matches_independent_native_distance(self):
        query = (127.049, 37.544)
        x, y = self.api.to_native.transform(*query)
        with self.api.connect() as db:
            rows = db.execute("SELECT id,x,y,height_m FROM spots").fetchall()
        expected = min(rows, key=lambda row: (row["x"] - x) ** 2 + (row["y"] - y) ** 2)
        distance = ((expected["x"] - x) ** 2 + (expected["y"] - y) ** 2) ** 0.5
        status, result, _ = self.request("/api/elevation?" + urlencode({"lon": query[0], "lat": query[1]}))
        self.assertEqual(status, 200)
        self.assertEqual(result["nearest"]["id"], f"spot-{expected['id']}")
        self.assertEqual(result["nearest"]["height_m"], expected["height_m"])
        self.assertAlmostEqual(result["nearest"]["distance_m"], distance, places=7)
        self.assertNotEqual(result["query"], result["nearest"]["coordinate"])

    def test_no_data_outside_source_extent(self):
        status, result, _ = self.request("/api/elevation?lon=129.0756&lat=35.1796")
        self.assertEqual(status, 200)
        self.assertIsNone(result["nearest"])
        self.assertEqual(result["reason"], "outside_source_extent")
        status, result, _ = self.features("128,35,130,36")
        self.assertEqual(status, 200)
        self.assertEqual(result["features"], [])
        self.assertEqual(result["metadata"]["spots"], 0)

    def test_no_data_for_hole_over_1000m_within_extent(self):
        # Find a real empty corner of the source bounding rectangle, rather
        # than assume that every location in its bounding box has a survey.
        west, south, east, north = self.api.bounds
        empty = None
        for lon in np.linspace(west + 0.0001, east - 0.0001, 12):
            for lat in np.linspace(south + 0.0001, north - 0.0001, 12):
                xy = np.array(self.api.to_native.transform(lon, lat))
                nearest_distance = float(np.sqrt(np.sum((self.api.spot_xy - xy) ** 2, axis=1).min()))
                if nearest_distance > 1100:
                    empty = (lon, lat)
                    break
            if empty:
                break
        self.assertIsNotNone(empty, "Expected an uncovered corner in the source rectangular extent")
        status, result, _ = self.request("/api/elevation?" + urlencode({"lon": empty[0], "lat": empty[1]}))
        self.assertEqual(status, 200)
        self.assertIsNone(result["nearest"])
        self.assertEqual(result["reason"], "no_source_spot_within_1000m")

    def test_geojson_is_clipped_and_retains_source_heights(self):
        bbox = (127.04, 37.535, 127.06, 37.555)
        status, result, headers = self.features(",".join(map(str, bbox)), zoom=14, interval=5, points=1)
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(result["type"], "FeatureCollection")
        metadata = result["metadata"]
        self.assertGreater(metadata["contours"], 0)
        self.assertGreater(metadata["spots"], 0)
        self.assertEqual(len(result["features"]), metadata["contours"] + metadata["spots"])
        window = box(*bbox).buffer(1e-10)
        with self.api.connect() as db:
            for feature in result["features"]:
                props = feature["properties"]
                self.assertIsInstance(props["major"], bool)
                self.assertTrue(window.covers(shape(feature["geometry"])))
                kind, identifier = props["id"].split("-")
                self.assertEqual(props["kind"], kind)
                table = "contours" if kind == "contour" else "spots"
                source = db.execute(f"SELECT height_m FROM {table} WHERE id=?", (int(identifier),)).fetchone()
                self.assertEqual(props["height_m"], source[0])

    def test_contour_only_and_interval_rules(self):
        for zoom, requested, actual in [(11, 5, 25), (12, 5, 10), (13, 5, 5), (14, 10, 10), (14, 25, 25)]:
            with self.subTest(zoom=zoom, requested=requested):
                status, result, _ = self.features(zoom=zoom, interval=requested, points=0)
                self.assertEqual(status, 200)
                self.assertEqual(result["metadata"]["contour_interval_m"], actual)
                self.assertEqual(result["metadata"]["spots"], 0)
                self.assertTrue(all(feature["properties"]["kind"] == "contour" and feature["properties"]["height_m"] % actual == 0 for feature in result["features"]))

    def test_citywide_low_zoom_is_finite_and_reports_point_omission(self):
        started = time.perf_counter()
        status, result, _ = self.features("-180,-90,180,90", zoom=8, interval=5, points=1)
        self.assertEqual(status, 200)
        self.assertGreater(result["metadata"]["contours"], 0)
        self.assertLessEqual(result["metadata"]["contours"], MAX_CONTOURS)
        self.assertLessEqual(result["metadata"]["coordinates"], MAX_COORDINATES + MAX_SPOTS)
        self.assertTrue(result["metadata"]["points_hidden_at_zoom"])
        self.assertGreater(result["metadata"]["simplified_m"], 0)
        self.assertLess(len(json.dumps(result)), 5_000_000)
        print(f"City-wide low zoom: {time.perf_counter() - started:.3f}s, {len(json.dumps(result)):,} bytes")

    def test_citywide_spots_are_sampled_geographically_and_bounded(self):
        status, result, _ = self.features("126,37,128,38", zoom=13, interval=25, points=1)
        self.assertEqual(status, 200)
        self.assertTrue(result["metadata"]["spots_sampled"])
        self.assertLessEqual(result["metadata"]["spots"], MAX_SPOTS)
        self.assertGreater(result["metadata"]["spots"], 100)
        points = [feature["geometry"]["coordinates"] for feature in result["features"] if feature["properties"]["kind"] == "spot"]
        self.assertGreater(max(point[0] for point in points) - min(point[0] for point in points), 0.3)

    def test_invalid_queries_return_json_400(self):
        paths = [
            "/api/features", "/api/features?bbox=1,2,3", "/api/features?bbox=127,37,126,38",
            "/api/features?bbox=126,37,127,37", "/api/features?bbox=nan,37,127,38",
            "/api/features?bbox=-181,37,127,38", "/api/features?bbox=126,37,127,91",
            "/api/features?bbox=126,37,127,38&zoom=nan", "/api/features?bbox=126,37,127,38&zoom=23",
            "/api/features?bbox=126,37,127,38&zoom=-1", "/api/features?bbox=126,37,127,38&interval=1",
            "/api/features?bbox=126,37,127,38&points=true", "/api/features?bbox=126,37,127,38&zoom=12&zoom=13",
            "/api/features?bbox=126,37,127,38&unknown=1", "/api/elevation", "/api/elevation?lon=127",
            "/api/elevation?lon=Infinity&lat=37", "/api/elevation?lon=127&lat=91", "/api/elevation?lon=&lat=37",
        ]
        for path in paths:
            with self.subTest(path=path):
                status, result, _ = self.request(path)
                self.assertEqual(status, 400)
                self.assertIn("error", result)

    def test_bookmark_lifecycle_persists_and_does_not_write_terrain(self):
        before = DATABASE.stat().st_mtime_ns
        status, saved, _ = self.request("/api/bookmarks", "POST", {"name": "  성수 테스트  ", "lon": 127.049, "lat": 37.544})
        self.assertEqual(status, 201)
        self.assertEqual(saved["name"], "성수 테스트")
        status, listed, _ = self.request("/api/bookmarks")
        self.assertIn(saved, listed["bookmarks"])
        restarted = TerrainAPI(DATABASE, self.bookmark_path)
        self.assertIn(saved, restarted.bookmarks()["bookmarks"])
        status, deleted, _ = self.request(f"/api/bookmarks/{saved['id']}", "DELETE")
        self.assertEqual((status, deleted["deleted"]), (200, saved["id"]))
        self.assertNotIn(saved, restarted.bookmarks()["bookmarks"])
        self.assertEqual(self.request(f"/api/bookmarks/{saved['id']}", "DELETE")[0], 404)
        self.assertEqual(DATABASE.stat().st_mtime_ns, before)
        with self.api.connect() as db:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("UPDATE spots SET height_m=0 WHERE id=1")

    def test_invalid_bookmarks_are_not_stored(self):
        before = self.api.bookmarks()
        for payload in [
            {"name": "", "lon": 127, "lat": 37.5}, {"name": " ", "lon": 127, "lat": 37.5},
            {"name": "x" * 81, "lon": 127, "lat": 37.5}, {"name": "line\nbreak", "lon": 127, "lat": 37.5},
            {"name": "test", "lon": True, "lat": 37.5}, {"name": "test", "lon": 129, "lat": 35},
            {"name": "test", "lon": float("nan"), "lat": 37.5}, {"name": "test", "lon": 127},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.request("/api/bookmarks", "POST", payload)[0], 400)
        self.assertEqual(self.request("/api/bookmarks", "POST", "{}", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/api/bookmarks", "POST", "{", {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.api.bookmarks(), before)

    def test_foreign_webpages_cannot_read_or_mutate_local_api(self):
        for method, payload in [("GET", None), ("POST", {"name": "attack", "lon": 127, "lat": 37.5})]:
            status, result, headers = self.request("/api/bookmarks", method, payload, {"Origin": "https://unrelated.example"})
            self.assertEqual(status, 403)
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertEqual(self.request("/api/health", headers={"Host": "unrelated.example"})[0], 403)
        status, _, headers = self.request("/api/health", headers={"Origin": "http://localhost:4173"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:4173")

    def test_reimport_of_identical_source_reuses_database(self):
        before = DATABASE.stat().st_mtime_ns
        result = build_database(DEFAULT_SOURCE, DATABASE)
        self.assertTrue(result["reused"])
        self.assertEqual((result["contours"], result["spots"]), (8570, 45870))
        self.assertEqual(DATABASE.stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main()
