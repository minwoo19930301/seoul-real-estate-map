"""Read-only terrain, bounded map responses, and independently stored bookmarks."""
from __future__ import annotations

import argparse
import gzip
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import sqlite3
from server.database import connect_readonly, available, database_bytes
from urllib.parse import parse_qs, urlsplit, unquote
import uuid

import numpy as np
from pyproj import Transformer
from shapely import from_wkb, get_num_coordinates
from shapely.geometry import box, mapping, MultiLineString
from shapely.ops import transform
from server.buildings import BuildingsAPI
from server.places import PlacesAPI
from server.roads import RoadsAPI
from server.greenery import GreeneryAPI
from server.mobility import MobilityAPI
from server.apartment_details import ApartmentDetailsAPI

ROOT = Path(__file__).resolve().parents[1]
MAX_CONTOURS = 2500
MAX_COORDINATES = 80000
MAX_SPOTS = 1800
MAX_NEAREST_DISTANCE_M = 1000


class APIError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def finite_number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise APIError(f"{label} must be a finite number")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise APIError(f"{label} must be a finite number") from None
    if not math.isfinite(result):
        raise APIError(f"{label} must be a finite number")
    return result


def coordinate(lon, lat) -> tuple[float, float]:
    lon, lat = finite_number(lon, "lon"), finite_number(lat, "lat")
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise APIError("Coordinate is outside the longitude/latitude range")
    return lon, lat


class TerrainAPI:
    def __init__(self, database: Path, bookmarks_database: Path | None = None, buildings_database: Path | None = None):
        self.database = Path(database).resolve()
        self.database_uri = self.database.as_uri() + "?mode=ro"
        self.bookmarks_database = Path(bookmarks_database or self.database.with_name("bookmarks.sqlite"))
        self.buildings = BuildingsAPI(Path(buildings_database or self.database.with_name("buildings.sqlite")))
        self.places = PlacesAPI(self.database.with_name("places.sqlite"))
        self.roads = RoadsAPI(self.database.with_name("roads.sqlite"))
        self.apartment_details = ApartmentDetailsAPI(self.database.with_name("apartment_sources.sqlite"))
        self.greenery = GreeneryAPI(self.buildings.database, self.roads.database)
        self.mobility = MobilityAPI(self.roads.database, ROOT / 'public' / 'data' / 'terrain')
        with self.connect() as db:
            self.metadata = {row[0]: json.loads(row[1]) for row in db.execute("SELECT key,value FROM metadata")}
            rows = db.execute("SELECT id,x,y,height_m FROM spots ORDER BY id").fetchall()
        self.spot_ids = np.array([row[0] for row in rows], dtype=np.int64)
        self.spot_xy = np.array([(row[1], row[2]) for row in rows], dtype=float).reshape((-1, 2))
        self.spot_heights = np.array([row[3] for row in rows], dtype=float)
        self.to_native = Transformer.from_crs(4326, self.metadata["source_crs_epsg"], always_xy=True)
        self.to_wgs = Transformer.from_crs(self.metadata["source_crs_epsg"], 4326, always_xy=True)
        self.bounds = tuple(self.metadata["bounds"])
        self.bookmarks_database.parent.mkdir(parents=True, exist_ok=True)
        with self.bookmark_connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS bookmarks (id TEXT PRIMARY KEY, name TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL)")

    def connect(self):
        db = connect_readonly(self.database)
        db.row_factory = sqlite3.Row
        return db

    def bookmark_connection(self):
        db = sqlite3.connect(self.bookmarks_database, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def meta(self):
        return {**self.metadata, "database_bytes": database_bytes(self.database)}

    def inside(self, lon: float, lat: float) -> bool:
        west, south, east, north = self.bounds
        return west <= lon <= east and south <= lat <= north

    def elevation(self, lon, lat):
        lon, lat = coordinate(lon, lat)
        result = {"query": [lon, lat], "nearest": None, "method": "nearest_source_spot", "max_distance_m": MAX_NEAREST_DISTANCE_M}
        if not self.inside(lon, lat):
            return {**result, "reason": "outside_source_extent"}
        if not len(self.spot_ids):
            return {**result, "reason": "no_source_spots"}
        xy = np.array(self.to_native.transform(lon, lat))
        squared = np.sum((self.spot_xy - xy) ** 2, axis=1)
        index = int(np.argmin(squared))
        distance = math.sqrt(float(squared[index]))
        if distance >= MAX_NEAREST_DISTANCE_M:
            return {**result, "reason": "no_source_spot_within_1000m"}
        x, y = self.spot_xy[index]
        return {**result, "nearest": {
            "id": f"spot-{int(self.spot_ids[index])}",
            "coordinate": list(self.to_wgs.transform(float(x), float(y))),
            "height_m": float(self.spot_heights[index]),
            "distance_m": distance,
        }}

    def features(self, bbox, zoom="14", interval="5", points="1"):
        if not isinstance(bbox, str) or len(bbox.split(",")) != 4:
            raise APIError("bbox must contain west,south,east,north")
        west, south, east, north = [finite_number(part, "bbox") for part in bbox.split(",")]
        coordinate(west, south)
        coordinate(east, north)
        if west >= east or south >= north:
            raise APIError("bbox must have west < east and south < north")
        zoom, interval = finite_number(zoom, "zoom"), finite_number(interval, "interval")
        if not 0 <= zoom <= 22:
            raise APIError("zoom must be between 0 and 22")
        if interval not in (5, 10, 25):
            raise APIError("interval must be 5, 10, or 25 metres")
        if str(points) not in ("0", "1"):
            raise APIError("points must be 0 or 1")
        zoom_level = math.floor(zoom)
        interval = int(max(interval, 25 if zoom_level <= 11 else 10 if zoom_level == 12 else 5))
        tolerance = 60 if zoom_level <= 10 else 25 if zoom_level == 11 else 8 if zoom_level == 12 else 2 if zoom_level <= 15 else 0
        metadata = {
            "contours": 0, "spots": 0, "contour_interval_m": interval,
            "simplified_m": tolerance, "source_year": self.metadata["source_year"],
            "points_requested": str(points) == "1", "points_min_zoom": 13,
            "points_hidden_at_zoom": str(points) == "1" and zoom_level < 13,
            "truncated": False, "spots_sampled": False,
            "max_contours": MAX_CONTOURS, "max_coordinates": MAX_COORDINATES,
            "max_spots": MAX_SPOTS,
        }
        result = {"type": "FeatureCollection", "features": [], "metadata": metadata}
        bounded = (max(west, self.bounds[0]), max(south, self.bounds[1]), min(east, self.bounds[2]), min(north, self.bounds[3]))
        if bounded[0] >= bounded[2] or bounded[1] >= bounded[3]:
            return result
        native_bounds = self.to_native.transform_bounds(*bounded, densify_pts=21)
        x1, y1, x2, y2 = native_bounds
        native_window, wgs_window = box(*native_bounds), box(west, south, east, north)
        spatial_args = (x2, x1, y2, y1)
        with self.connect() as db:
            if tolerance:
                rows = db.execute("""
                    SELECT c.id,c.height_m,c.major,l.wkb FROM contour_index r
                    JOIN contours c ON c.id=r.id
                    JOIN contour_lod l ON l.contour_id=c.id AND l.tolerance_m=?
                    WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=?
                      AND CAST(ROUND(c.height_m) AS INTEGER) % ? = 0
                    ORDER BY c.major DESC,c.id
                """, (tolerance, *spatial_args, interval))
            else:
                rows = db.execute("""
                    SELECT c.id,c.height_m,c.major,c.wkb FROM contour_index r
                    JOIN contours c ON c.id=r.id
                    WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=?
                      AND CAST(ROUND(c.height_m) AS INTEGER) % ? = 0
                    ORDER BY c.major DESC,c.id
                """, (*spatial_args, interval))
            coordinate_count = 0
            for row in rows:
                geometry = from_wkb(row["wkb"]).intersection(native_window)
                if geometry.is_empty:
                    continue
                geometry = transform(self.to_wgs.transform, geometry).intersection(wgs_window)
                if geometry.geom_type == "GeometryCollection":
                    parts = []
                    for part in geometry.geoms:
                        if part.geom_type == "LineString":
                            parts.append(part)
                        elif part.geom_type == "MultiLineString":
                            parts.extend(part.geoms)
                    geometry = MultiLineString(parts)
                if geometry.is_empty or geometry.geom_type not in ("LineString", "MultiLineString"):
                    continue
                count = int(get_num_coordinates(geometry))
                if metadata["contours"] >= MAX_CONTOURS or coordinate_count + count > MAX_COORDINATES:
                    metadata["truncated"] = True
                    continue
                coordinate_count += count
                result["features"].append({"type": "Feature", "id": f"contour-{row['id']}", "properties": {
                    "id": f"contour-{row['id']}", "kind": "contour", "height_m": row["height_m"], "major": bool(row["major"]),
                }, "geometry": mapping(geometry)})
                metadata["contours"] += 1
            if str(points) == "1" and zoom_level >= 13:
                # A bounded grid provides geographically distributed points even
                # when a caller requests a city-wide bbox at a very high zoom.
                cell = max(8, 160 / 2 ** max(0, zoom_level - 13), (x2 - x1) / 40, (y2 - y1) / 40)
                occupied = set()
                point_rows = db.execute("""
                    SELECT s.id,s.x,s.y,s.height_m FROM spot_index r JOIN spots s ON s.id=r.id
                    WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=?
                    ORDER BY s.id
                """, spatial_args)
                for row in point_rows:
                    lon, lat = self.to_wgs.transform(row["x"], row["y"])
                    if not west <= lon <= east or not south <= lat <= north:
                        continue
                    cell_id = (math.floor((row["x"] - x1) / cell), math.floor((row["y"] - y1) / cell))
                    if cell_id in occupied or metadata["spots"] >= MAX_SPOTS:
                        metadata["spots_sampled"] = True
                        continue
                    occupied.add(cell_id)
                    result["features"].append({"type": "Feature", "id": f"spot-{row['id']}", "properties": {
                        "id": f"spot-{row['id']}", "kind": "spot", "height_m": row["height_m"], "major": False,
                    }, "geometry": {"type": "Point", "coordinates": [lon, lat]}})
                    metadata["spots"] += 1
                metadata["spot_spacing_m"] = cell
        metadata["coordinates"] = coordinate_count + metadata["spots"]
        return result

    def bookmarks(self):
        with self.bookmark_connection() as db:
            return {"bookmarks": [dict(row) for row in db.execute("SELECT id,name,lon,lat FROM bookmarks ORDER BY rowid")]}

    def add_bookmark(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"name", "lon", "lat"}:
            raise APIError("Bookmark must contain name,lon,lat")
        name = payload["name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80 or any(ord(char) < 32 for char in name):
            raise APIError("name must contain 1–80 characters without control characters")
        lon, lat = coordinate(payload["lon"], payload["lat"])
        if not self.inside(lon, lat):
            raise APIError("Bookmark is outside the source extent")
        bookmark = {"id": uuid.uuid4().hex, "name": name.strip(), "lon": lon, "lat": lat}
        with self.bookmark_connection() as db:
            db.execute("INSERT INTO bookmarks VALUES(:id,:name,:lon,:lat)", bookmark)
        return bookmark

    def delete_bookmark(self, identifier):
        with self.bookmark_connection() as db:
            if db.execute("DELETE FROM bookmarks WHERE id=?", (identifier,)).rowcount == 0:
                raise APIError("Bookmark not found", 404)
        return {"deleted": identifier}


def local_origin(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost", "::1") and parsed.username is None and parsed.password is None
    except ValueError:
        return False


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, api: TerrainAPI, directory=None, **kwargs):
        self.api = api
        super().__init__(*args, directory=str(directory or ROOT / "dist"), **kwargs)

    def send_json(self, value, status=200):
        content = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        compressed = len(content) > 1024 and self.accepts_gzip()
        if compressed:
            content = gzip.compress(content, compresslevel=3, mtime=0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Vary", "Accept-Encoding, Origin")
        if compressed:
            self.send_header("Content-Encoding", "gzip")
        origin = self.headers.get("Origin")
        if origin and local_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(content)

    def accepts_gzip(self):
        for item in self.headers.get("Accept-Encoding", "").lower().split(","):
            name, *options = item.strip().split(";")
            if name == "gzip":
                try:
                    return all(float(option.strip()[2:]) > 0 for option in options if option.strip().startswith("q="))
                except ValueError:
                    return False
        return False

    def send_head(self):
        path = Path(self.translate_path(self.path))
        compressed = path.with_name(path.name + ".gz")
        if self.accepts_gzip() and path.suffix in (".js", ".css", ".json", ".glb") and path.is_file() and compressed.is_file():
            stream = compressed.open("rb")
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(compressed.stat().st_size))
            self.send_header("Vary", "Accept-Encoding")
            self.send_header("Cache-Control", "public, max-age=31536000, immutable" if path.parent.name == "assets" else "no-cache")
            self.end_headers()
            return stream
        self._vary_static = path.is_file() and compressed.is_file()
        return super().send_head()

    def end_headers(self):
        if getattr(self, "_vary_static", False):
            self.send_header("Vary", "Accept-Encoding")
            self._vary_static = False
        super().end_headers()

    def check_local(self):
        if not local_origin("http://" + self.headers.get("Host", "")):
            raise APIError("Only localhost requests are allowed", 403)
        origin = self.headers.get("Origin")
        if origin and not local_origin(origin):
            raise APIError("Only localhost origins are allowed", 403)

    def route(self, method):
        try:
            self.check_local()
            parsed = urlsplit(self.path)
            if not parsed.path.startswith("/api/"):
                if method == "GET":
                    return super().do_GET()
                raise APIError("Not found", 404)
            if len(parsed.query) > 4096:
                raise APIError("Query is too long")
            args = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=16)
            if any(len(values) != 1 for values in args.values()):
                raise APIError("Repeated query parameters are not allowed")
            args = {key: value[0] for key, value in args.items()}
            if method == "GET" and parsed.path == "/api/health":
                return self.send_json({"status": "ok", "source_year": self.api.metadata["source_year"], "database": "ready"})
            if method == "GET" and parsed.path == "/api/meta":
                return self.send_json(self.api.meta())
            if method == "GET" and parsed.path == "/api/places/meta":
                return self.send_json(self.api.places.meta())
            if method == "GET" and parsed.path == "/api/places":
                if set(args) - {"q", "limit", "min_households"}:
                    raise APIError("places accepts q, limit and min_households")
                options = {"min_households": args["min_households"]} if "min_households" in args else {}
                return self.send_json(self.api.places.search(args.get("q", ""), args.get("limit", "12"), **options))
            if method == "GET" and parsed.path == "/api/landmarks":
                if "bbox" not in args or set(args) - {"bbox", "zoom", "kinds", "min_households"}:
                    raise APIError("landmarks requires bbox and accepts zoom,kinds,min_households")
                return self.send_json(self.api.places.features(**args))
            if method == "GET" and parsed.path.startswith("/api/apartments/"):
                if args:
                    raise APIError("apartment detail accepts no query parameters")
                return self.send_json(self.api.apartment_details.detail(unquote(parsed.path.rsplit("/", 1)[-1])))
            if method == "GET" and parsed.path == "/api/renewal-zones":
                if "bbox" not in args or set(args) - {"bbox", "kinds"}:
                    raise APIError("renewal-zones requires bbox and accepts kinds")
                return self.send_json(self.api.apartment_details.zones(args["bbox"], args.get("kinds", "project,district")))
            if method == "GET" and parsed.path == "/api/roads/meta":
                return self.send_json(self.api.roads.meta())
            if method == "GET" and parsed.path == "/api/greenery":
                if set(args) != {"bbox"}:
                    raise APIError("greenery requires bbox")
                return self.send_json(self.api.greenery.features(args["bbox"]))
            if method == "GET" and parsed.path == "/api/mobility":
                if set(args) != {"bbox"}:
                    raise APIError("mobility requires bbox")
                return self.send_json(self.api.mobility.features(args["bbox"]))
            if method == "GET" and parsed.path == "/api/roads":
                if "bbox" not in args or set(args) - {"bbox", "zoom"}:
                    raise APIError("roads requires bbox and accepts zoom")
                return self.send_json(self.api.roads.features(**args))
            if method == "GET" and parsed.path == "/api/buildings/meta":
                return self.send_json(self.api.buildings.meta())
            if method == "GET" and parsed.path == "/api/buildings":
                if "bbox" not in args or set(args) - {"bbox", "zoom"}:
                    raise APIError("buildings requires bbox and accepts zoom")
                return self.send_json(self.api.buildings.features(**args))
            if method == "GET" and parsed.path.startswith("/api/buildings/"):
                result = self.api.buildings.detail(unquote(parsed.path.rsplit("/", 1)[-1]))
                if result is None:
                    raise APIError("Building not found", 404)
                return self.send_json(result)
            if method == "GET" and parsed.path == "/api/features":
                if "bbox" not in args or set(args) - {"bbox", "zoom", "interval", "points"}:
                    raise APIError("features requires bbox and accepts zoom,interval,points")
                return self.send_json(self.api.features(**args))
            if method == "GET" and parsed.path == "/api/elevation":
                if set(args) != {"lon", "lat"}:
                    raise APIError("elevation requires lon and lat")
                return self.send_json(self.api.elevation(**args))
            if method == "GET" and parsed.path == "/api/bookmarks":
                return self.send_json(self.api.bookmarks())
            if method == "POST" and parsed.path == "/api/bookmarks":
                if self.headers.get_content_type() != "application/json":
                    raise APIError("Use application/json", 415)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise APIError("Invalid Content-Length") from None
                if not 0 < length <= 4096:
                    raise APIError("JSON body must be 1–4096 bytes", 413)
                try:
                    payload = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeDecodeError):
                    raise APIError("Invalid JSON") from None
                return self.send_json(self.api.add_bookmark(payload), 201)
            if method == "DELETE" and parsed.path.startswith("/api/bookmarks/"):
                return self.send_json(self.api.delete_bookmark(parsed.path.rsplit("/", 1)[-1]))
            raise APIError("Not found", 404)
        except APIError as error:
            self.send_json({"error": str(error)}, error.status)
        except ValueError:
            self.send_json({"error": "Invalid request"}, 400)
        except sqlite3.Error:
            self.send_json({"error": "Database temporarily unavailable"}, 503)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_DELETE(self):
        self.route("DELETE")

    def do_OPTIONS(self):
        try:
            self.check_local()
        except APIError as error:
            return self.send_json({"error": str(error)}, error.status)
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()


def create_server(api: TerrainAPI, port: int = 8791, static_dir: Path | None = None):
    return ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, api=api, directory=static_dir))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "terrain.sqlite")
    parser.add_argument("--bookmarks-database", type=Path)
    parser.add_argument("--buildings-database", type=Path)
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--static-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    api = TerrainAPI(args.database, args.bookmarks_database, args.buildings_database)
    with create_server(api, args.port, args.static_dir) as server:
        print(f"Seoul elevation local: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
