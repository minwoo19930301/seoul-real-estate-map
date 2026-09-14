#!/usr/bin/env python3
"""Build an atomic, reproducible SQLite copy of Seoul's public contour SHP ZIP.

The source geometries and heights are preserved. Simplified copies only support
map rendering; they are never used to answer elevation queries.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import zipfile

from pyproj import CRS, Transformer
import shapefile
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SOURCE = ROOT / "data" / "seoul-contours.zip"
DEFAULT_SOURCE = LOCAL_SOURCE if LOCAL_SOURCE.exists() else ROOT.parent / "seoul-contours-feasibility" / "seoul-contours.zip"
DEFAULT_DATABASE = ROOT / "data" / "terrain.sqlite"
SOURCE_URL = "https://data.seoul.go.kr/dataList/OA-22241/F/1/datasetView.do"
SIMPLIFICATIONS = (2, 8, 25, 60)
SCHEMA_VERSION = 1


def source_reader(archive: zipfile.ZipFile, stem: str) -> shapefile.Reader:
    return shapefile.Reader(**{
        ext: io.BytesIO(archive.read(f"{stem}.{ext}"))
        for ext in ("shp", "shx", "dbf")
    }, encoding="cp949")


def build_database(source: Path, destination: Path, force: bool = False) -> dict:
    source, destination = Path(source), Path(destination)
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if destination.exists() and not force:
        with sqlite3.connect(f"{destination.resolve().as_uri()}?mode=ro", uri=True) as db:
            existing = {key: json.loads(value) for key, value in db.execute("SELECT key,value FROM metadata")}
            if existing.get("source_sha256") == digest and existing.get("schema_version") == SCHEMA_VERSION:
                return {**existing, "database_bytes": destination.stat().st_size, "reused": True}

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".terrain-", suffix=".sqlite", dir=destination.parent, delete=False) as temp:
        staging = Path(temp.name)
    try:
        with sqlite3.connect(staging) as db, zipfile.ZipFile(source) as archive:
            db.executescript("""
                PRAGMA journal_mode=DELETE;
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE contours (
                    id INTEGER PRIMARY KEY, height_m REAL NOT NULL,
                    major INTEGER NOT NULL, wkb BLOB NOT NULL
                );
                CREATE VIRTUAL TABLE contour_index USING rtree(id,minx,maxx,miny,maxy);
                CREATE TABLE contour_lod (
                    contour_id INTEGER NOT NULL, tolerance_m INTEGER NOT NULL,
                    wkb BLOB NOT NULL, PRIMARY KEY(contour_id,tolerance_m)
                ) WITHOUT ROWID;
                CREATE TABLE spots (
                    id INTEGER PRIMARY KEY, x REAL NOT NULL, y REAL NOT NULL,
                    height_m REAL NOT NULL, wkb BLOB NOT NULL
                );
                CREATE VIRTUAL TABLE spot_index USING rtree(id,minx,maxx,miny,maxy);
                CREATE INDEX contour_height ON contours(height_m);
            """)
            stems = {"contour": "등고선 5000/N3L_F001", "spot": "표고 5000/N3P_F002"}
            crs = CRS.from_wkt(archive.read(stems["contour"] + ".prj").decode())
            point_crs = CRS.from_wkt(archive.read(stems["spot"] + ".prj").decode())
            if crs.to_epsg() != 5174 or not crs.equals(point_crs):
                raise ValueError("Expected matching EPSG:5174 contour and spot sources")
            bounds = [math.inf, math.inf, -math.inf, -math.inf]
            counts, ranges = {}, {}
            for kind, stem in stems.items():
                heights = []
                with source_reader(archive, stem) as reader:
                    for identifier, row in enumerate(reader.iterShapeRecords(), 1):
                        geometry = shape(row.shape.__geo_interface__)
                        fields = row.record.as_dict()
                        height = float(fields["HEIGHT"])
                        if geometry.is_empty or not math.isfinite(height):
                            raise ValueError(f"Invalid source {kind} {identifier}")
                        x1, y1, x2, y2 = geometry.bounds
                        if not all(map(math.isfinite, (x1, y1, x2, y2))):
                            raise ValueError("Non-finite source coordinate")
                        bounds = [min(bounds[0], x1), min(bounds[1], y1), max(bounds[2], x2), max(bounds[3], y2)]
                        if kind == "contour":
                            if geometry.geom_type not in ("LineString", "MultiLineString") or height % 5:
                                raise ValueError("Unexpected source contour geometry or level")
                            db.execute("INSERT INTO contours VALUES(?,?,?,?)", (identifier, height, fields.get("DIVI") == "CTD001", geometry.wkb))
                            db.execute("INSERT INTO contour_index VALUES(?,?,?,?,?)", (identifier, x1, x2, y1, y2))
                            db.executemany("INSERT INTO contour_lod VALUES(?,?,?)", [
                                (identifier, tolerance, geometry.simplify(tolerance).wkb)
                                for tolerance in SIMPLIFICATIONS
                            ])
                        else:
                            if geometry.geom_type != "Point":
                                raise ValueError("Unexpected source spot geometry")
                            db.execute("INSERT INTO spots VALUES(?,?,?,?,?)", (identifier, geometry.x, geometry.y, height, geometry.wkb))
                            db.execute("INSERT INTO spot_index VALUES(?,?,?,?,?)", (identifier, x1, x2, y1, y2))
                        heights.append(height)
                counts[kind] = len(heights)
                ranges[kind] = [min(heights), max(heights)]
            to_wgs = Transformer.from_crs(crs, 4326, always_xy=True)
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "source_url": SOURCE_URL,
                "source_title": "서울시 경사도 — 서울시 등고선.zip",
                "source_year": 2023,
                "source_file_date": "2025-03-20",
                "source_file": source.name,
                "source_bytes": source.stat().st_size,
                "source_sha256": digest,
                "license": "공공누리 제1유형 (출처표시)",
                "attribution": "서울특별시·국토지리정보원 / 서울열린데이터광장 OA-22241",
                "source_crs": "EPSG:5174",
                "source_crs_epsg": 5174,
                "output_crs": "EPSG:4326",
                "vertical_datum": "unverified",
                "vertical_datum_note": "원본 PRJ와 필드 설명에 수직 기준이 명시되지 않아 확인되지 않았습니다.",
                "contours": counts["contour"],
                "spots": counts["spot"],
                "contour_interval_m": 5,
                "contour_height_range_m": ranges["contour"],
                "spot_height_range_m": ranges["spot"],
                "bounds_native": bounds,
                "bounds": list(to_wgs.transform_bounds(*bounds, densify_pts=21)),
                "bounds_note": "원본 자료 범위의 사각형이며 서울시 행정경계가 아닙니다.",
                "simplifications_m": list(SIMPLIFICATIONS),
                "elevation_method": "nearest_source_spot",
                "nearest_max_distance_m": 1000,
                "limitations": [
                    "5 m 등고 간격은 수평 해상도나 높이 정확도를 뜻하지 않습니다.",
                    "클릭 위치의 높이를 보간하지 않으며 가장 가까운 원본 표고점과 거리를 표시합니다.",
                    "제작 이후 지형 변화와 교량·건물·지하 공간의 높이를 보장하지 않습니다.",
                ],
            }
            db.executemany("INSERT INTO metadata VALUES(?,?)", [(key, json.dumps(value, ensure_ascii=False, allow_nan=False)) for key, value in metadata.items()])
            db.execute("ANALYZE")
        staging.replace(destination)
        return {**metadata, "database_bytes": destination.stat().st_size, "reused": False}
    finally:
        staging.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build_database(args.source, args.output, args.force), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
