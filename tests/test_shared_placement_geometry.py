import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from shapely.geometry import box, Polygon, MultiPolygon, mapping
from shapely.affinity import scale
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from check_shared_instance_placements import check, projected_geometry

class CompleteGeometryChecks(unittest.TestCase):
    def run_check(self, representative, neighbor):
        metre=1/111319.49079327358
        def row(fid, number, geometry):
            return {'sourceId':fid,'number':number,'geometry':mapping(scale(geometry,metre,metre,origin=(0,0)))}
        assets=[{'id':'rep','coordinate':{'lon':0,'lat':0},'footprintIds':['rep'],'sourceRecord':{'siteId':'representative'}},
                {'id':'copy','coordinate':{'lon':0,'lat':0},'footprintIds':['target'],'sourceRecord':{'siteId':'copies'},'modelInstance':{'sourceAssetId':'rep','matrix':[1,0,0,0,0,1,0,0,0,0,1,0,100,0,0,1]}}]
        docs={'public/models/bespoke-manifest.json':{'assets':assets},'docs/model-audit/published-bespoke.json':{'sites':{'copies':{'sharedRepresentative':'rep','placementInputs':[{'path':'identity'}]}}},'identity':{'towers':[row('rep',1,representative),row('target',2,box(200,0,201,1)),row('neighbor',3,neighbor)]}}
        with patch('check_shared_instance_placements.read',side_effect=docs.__getitem__):return check()[0]['bodyPlanNeighborOverlaps']

    def test_second_representative_part_and_second_neighbor_part_are_checked(self):
        rep=MultiPolygon([box(0,0,1,1),box(10,0,12,2)])
        neighbor=MultiPolygon([box(300,0,301,1),box(110,0,112,2)])
        hits=self.run_check(rep,neighbor)
        self.assertEqual(len(hits),1)
        self.assertAlmostEqual(hits[0]['overlapM2'],4,places=6)

    def test_representative_hole_is_not_filled(self):
        rep=Polygon(box(0,0,10,10).exterior.coords,[box(2,2,8,8).exterior.coords])
        self.assertEqual(self.run_check(rep,box(103,3,107,7)),[])

    def test_neighbor_hole_is_not_filled(self):
        neighbor=Polygon(box(99,-1,110,10).exterior.coords,[box(100,0,109,9).exterior.coords])
        self.assertEqual(self.run_check(box(2,2,8,8),neighbor),[])

    def test_projection_retains_each_component_and_hole(self):
        shape=MultiPolygon([Polygon(box(0,0,10,10).exterior.coords,[box(2,2,8,8).exterior.coords]),box(20,0,22,2)])
        result=projected_geometry(mapping(shape),(0,0),2,3)
        self.assertEqual(len(result.geoms),2)
        self.assertEqual(len(result.geoms[0].interiors),1)
        self.assertAlmostEqual(result.area,shape.area*6)

if __name__=='__main__':unittest.main()
