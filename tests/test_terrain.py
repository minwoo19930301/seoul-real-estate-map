"""Geometry/encoding tests and checks against the actual generated Seoul tiles.
Run with: .venv-terrain/bin/python -m unittest discover -s tests -p test_terrain.py -v
"""
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image
from pyproj import CRS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_terrain', ROOT / 'scripts' / 'build_terrain.py')
terrain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terrain)


class TerrainMathTests(unittest.TestCase):
    def test_height_rgb_roundtrip_includes_negative_original_spot_heights(self):
        heights = np.array([[-0.54, 0, 5, 17.63, 29.13], [65.06, 158.24, 740.2, 770, 1234.56]])
        rgb = terrain.encode_mapbox_rgb(heights)
        self.assertEqual(rgb.dtype, np.uint8)
        self.assertEqual(rgb.shape, (2, 5, 3))
        np.testing.assert_allclose(terrain.decode_mapbox_rgb(rgb), heights, atol=0.050001, rtol=0)
        with self.assertRaises(ValueError):
            terrain.encode_mapbox_rgb([np.nan])
        with self.assertRaises(ValueError):
            terrain.encode_mapbox_rgb([-10001])

    def test_line_sampling_respects_meter_spacing_endpoints_and_small_closed_summits(self):
        points = terrain.sample_polyline([[0, 0], [50, 0], [50, 40]], 30)
        np.testing.assert_allclose(points[[0, -1]], [[0, 0], [50, 40]])
        self.assertTrue(np.all(np.linalg.norm(np.diff(points, axis=0), axis=1) <= 30.000001))
        short_loop = terrain.sample_polyline([[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]], 30)
        self.assertGreaterEqual(len(np.unique(short_loop, axis=0)), 3)
        np.testing.assert_array_equal(terrain.sample_polyline([[1, 2], [1, 2]], 30), [[1, 2]])

    def test_duplicate_spots_override_contours_without_duplicated_tin_vertices(self):
        xy, z, meta = terrain.deduplicate(
            [[1, 2], [1, 2], [1, 2], [3, 4]], [5, 6, 8, 30], [0, 1, 1, 0],
        )
        np.testing.assert_array_equal(xy, [[1, 2], [3, 4]])
        np.testing.assert_array_equal(z, [7, 30])
        self.assertEqual(meta['duplicates_removed'], 2)
        self.assertEqual(meta['groups_with_height_disagreement_over_0_5m'], 1)

    def test_adjacent_rasters_use_one_global_pixel_grid_and_continue_the_same_slope(self):
        zoom, x, y = 13, 6984, 3173
        left_x, left_y = terrain.tile_mercator_grid(zoom, x, y)
        right_x, right_y = terrain.tile_mercator_grid(zoom, x + 1, y)
        pixel = terrain.WORLD_SIZE / (terrain.TILE_SIZE * 2 ** zoom)
        np.testing.assert_allclose(right_x[:, 0] - left_x[:, -1], pixel, atol=2e-9, rtol=0)
        np.testing.assert_allclose(right_y[:, 0], left_y[:, -1], atol=0, rtol=0)
        _, south_y = terrain.tile_mercator_grid(zoom, x, y + 1)
        np.testing.assert_allclose(left_y[-1] - south_y[0], pixel, atol=2e-9, rtol=0)
        # A real interpolator spanning a tile edge, not merely a coordinate test.
        west, east = left_x.min() - 100, right_x.max() + 100
        south, north = left_y.min() - 100, left_y.max() + 100
        xy = np.array([[west, south], [west, north], [east, north], [east, south]])
        height = lambda px, py: 50 + (px - west) * .01 + (py - south) * .02
        surface = terrain.TerrainSurface(xy, height(xy[:, 0], xy[:, 1]), CRS.from_epsg(3857), 100000, 100000)
        left, _ = surface.tile(zoom, x, y)
        right, _ = surface.tile(zoom, x + 1, y)
        np.testing.assert_allclose(left, height(left_x, left_y), atol=1e-9, rtol=0)
        np.testing.assert_allclose(right, height(right_x, right_y), atol=1e-9, rtol=0)
        decoded_left = terrain.decode_mapbox_rgb(terrain.encode_mapbox_rgb(left))
        decoded_right = terrain.decode_mapbox_rgb(terrain.encode_mapbox_rgb(right))
        np.testing.assert_allclose(decoded_right[:, 0] - decoded_left[:, -1], pixel * .01, atol=.100001, rtol=0)

    def test_hull_padding_is_continuous_and_never_masquerades_as_supported_height(self):
        surface = terrain.TerrainSurface([[0, 0], [10, 0], [10, 10], [0, 10]], [10, 20, 40, 30], CRS.from_epsg(3857), 100, 100)
        heights, mask = surface.evaluate(np.array([2, 5, 2, 2]), np.array([-1, -1, -0.000001, 0.000001]))
        np.testing.assert_allclose(heights[:2], [12, 15], atol=1e-9)
        self.assertLess(abs(heights[2] - heights[3]), .00001)
        np.testing.assert_array_equal(mask, [0, 0, 0, 255])
        sparse = terrain.TerrainSurface([[0, 0], [10000, 0], [10000, 10000], [0, 10000]], [10, 20, 40, 30], CRS.from_epsg(3857), 300, 1500)
        h, m = sparse.evaluate(np.array([5000]), np.array([5000]))
        self.assertTrue(np.isfinite(h).all())
        self.assertEqual(m[0], 0, 'large unsupported triangles are not marked valid')
        overlay = terrain.coverage_overlay(mask)
        np.testing.assert_array_equal(overlay[:, :3], [[113, 128, 140]] * 4)
        np.testing.assert_array_equal(overlay[:, 3], [180, 180, 180, 0])


class GeneratedSeoulTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ROOT / 'public' / 'data'
        cls.directory = cls.data / 'terrain'
        cls.meta = json.loads((cls.data / 'terrain.json').read_text())

    def test_metadata_marks_derived_heights_and_preserves_official_provenance(self):
        meta = self.meta
        self.assertTrue(meta['estimated'])
        self.assertEqual(meta['encoding'], 'mapbox')
        self.assertEqual(meta['tileSize'], 256)
        self.assertEqual(meta['source']['source_crs'], 'EPSG:5174')
        self.assertEqual(meta['source']['spot_height_count'], 45870)
        self.assertEqual(meta['source']['contour_original_vertex_count'], 4413952)
        self.assertEqual(meta['source']['zip_sha256'], '4fbe3c7e061b5974e7403ec116855304ed8ae321eebcc0d12c31ca8fb7be30bf')
        self.assertGreater(meta['source_point_count'], meta['source']['spot_height_count'])
        self.assertLess(meta['source_point_count'], meta['source']['contour_original_vertex_count'])
        self.assertIsNone(meta['validity']['noDataValue'])
        self.assertGreaterEqual(meta['validity']['padding_ground_m'], 6000)
        self.assertIn('현장 검증하지 않았', ' '.join(meta['limitations']))
        hull = json.loads((self.directory / 'source-hull.geojson').read_text())
        self.assertEqual(hull['geometry']['type'], 'Polygon')
        self.assertTrue(hull['properties']['estimated'])
        self.assertEqual(hull['geometry']['coordinates'][0][0], hull['geometry']['coordinates'][0][-1])

    def test_every_declared_tile_mask_and_overlay_exist_and_encode_valid_heights(self):
        terrain_total = 0
        for zoom in range(self.meta['minzoom'], self.meta['maxzoom'] + 1):
            layout = self.meta['raster_validity_counts'][str(zoom)]
            supported = 0
            count = 0
            for x in range(layout['x_range'][0], layout['x_range'][1] + 1):
                for y in range(layout['y_range'][0], layout['y_range'][1] + 1):
                    relative = Path(str(zoom)) / str(x) / f'{y}.png'
                    with Image.open(self.directory / relative) as image:
                        self.assertEqual(image.mode, 'RGB')
                        self.assertEqual(image.size, (256, 256))
                        heights = terrain.decode_mapbox_rgb(np.asarray(image))
                    self.assertGreaterEqual(heights.min(), self.meta['source_height_range_m'][0] - .051)
                    self.assertLessEqual(heights.max(), self.meta['source_height_range_m'][1] + .051)
                    with Image.open(self.directory / 'mask' / relative) as image:
                        self.assertEqual(image.mode, 'L')
                        mask = np.asarray(image)
                        self.assertTrue(np.isin(mask, [0, 255]).all())
                        supported += int(np.count_nonzero(mask))
                    with Image.open(self.directory / 'coverage' / relative) as image:
                        self.assertEqual(image.mode, 'RGBA')
                        np.testing.assert_array_equal(np.asarray(image), terrain.coverage_overlay(mask))
                    count += 1
            self.assertEqual(count, self.meta['tile_counts'][str(zoom)])
            self.assertEqual(supported, layout['supported_pixels'])
            terrain_total += count
        self.assertGreater(terrain_total, 200)

    def test_actual_seam_samples_match_the_source_interpolator_without_tile_edge_offsets(self):
        with np.load(self.directory / 'constraints.npz') as constraints:
            surface = terrain.TerrainSurface(constraints['points'], constraints['heights'], CRS.from_epsg(int(constraints['epsg'])))
        zoom = self.meta['maxzoom']
        layout = self.meta['raster_validity_counts'][str(zoom)]
        middle_x = sum(layout['x_range']) // 2
        middle_y = sum(layout['y_range']) // 2
        xs, ys, emitted = [], [], []
        masks = []
        # Multiple real Seoul horizontal and vertical borders, including padding.
        for tile_x, tile_y in [(middle_x, middle_y), (middle_x + 1, middle_y),
                                (middle_x, middle_y + 1), (layout['x_range'][0], layout['y_range'][0])]:
            px, py = terrain.tile_mercator_grid(zoom, tile_x, tile_y)
            rgb = np.asarray(Image.open(self.directory / str(zoom) / str(tile_x) / f'{tile_y}.png'))
            valid = np.asarray(Image.open(self.directory / 'mask' / str(zoom) / str(tile_x) / f'{tile_y}.png'))
            decoded = terrain.decode_mapbox_rgb(rgb)
            for row, col in [(0, 0), (0, 128), (0, 255), (64, 0), (64, 255), (128, 0), (128, 255), (255, 0), (255, 128), (255, 255)]:
                xs.append(px[row, col]); ys.append(py[row, col]); emitted.append(decoded[row, col]); masks.append(valid[row, col])
        expected, expected_mask = surface.evaluate(np.array(xs), np.array(ys))
        np.testing.assert_allclose(emitted, expected, atol=.050001, rtol=0)
        np.testing.assert_array_equal(masks, expected_mask)
        self.assertIn(0, masks, 'padding samples must be explicitly unsupported')
        self.assertIn(255, masks, 'test must also exercise actual supported Seoul terrain')


if __name__ == '__main__':
    unittest.main()
