import copy
import sys
import unittest
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, mapping
from shapely.affinity import affine_transform
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publish_shared_instances import local_polygon, placement, frame

class MultiPartPlacement(unittest.TestCase):
    def test_all_parts_and_holes_preserved_and_bounds_center_used(self):
        a=Polygon([(127,37),(127.0001,37),(127.0001,37.0001),(127,37.0001)])
        b=Polygon([(127.001,37),(127.0013,37),(127.0013,37.0002),(127.001,37.0002)], holes=[[(127.0011,37.00005),(127.0012,37.00005),(127.0012,37.0001),(127.0011,37.0001)]])
        target={'geometry':mapping(MultiPolygon([a,b])), 'register':{'height':50}}
        before=copy.deepcopy(target)
        source={'geometry':mapping(a)}
        asset={'coordinate':{'lon':127,'lat':37},'dimensions':[1,25,1]}
        anchor,m=placement(source,target,asset)
        np.testing.assert_allclose(anchor,[127.00065,37.0001],atol=1e-12)
        projected=local_polygon(target,anchor)
        self.assertEqual(len(projected.geoms),2)
        self.assertEqual(len(projected.geoms[1].interiors),1)
        pieces=[local_polygon({'geometry':mapping(p)},anchor) for p in [a,b]]
        self.assertAlmostEqual(projected.area,sum(p.area for p in pieces),8)
        expected=sum(p.area*p.centroid.x for p in pieces)/projected.area
        self.assertAlmostEqual(projected.centroid.x,expected,8)
        moved=affine_transform(local_polygon(source,[127,37]),[m[0],-m[8],-m[2],m[10],m[12],-m[14]])
        np.testing.assert_allclose(frame(moved)[1:],frame(projected)[1:],atol=1e-7)
        self.assertEqual(m[5],2)
        self.assertEqual(target,before)

    def test_invalid_or_empty_geometry_rejected(self):
        for geometry in [mapping(Polygon()),{'type':'LineString','coordinates':[[0,0],[1,1]]}]:
            with self.assertRaises(ValueError):local_polygon({'geometry':geometry},[0,0])

if __name__=='__main__':unittest.main()
