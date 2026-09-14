"""Synthetic real PNG terrain fixtures and original-way SQLite regressions."""
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from scripts.build_roads import build_database
from server.mobility import MobilityAPI,TerrainSampler,travel_mode


class MobilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.terrain=self.root/'terrain'
        self.database=self.root/'roads.sqlite'
        self.source=self.root/'ways.json'
        self.x,self.y=13970,6345
        self.world=256*2**14
        self.metadata={'encoding':'mapbox','tileSize':256,'minzoom':13,'maxzoom':14,
            'source_bounds':[126,37,128,38],'estimated':True,'exaggeration':8,
            'method':'synthetic analytic ramp for tests only','source':{'url':'fixture://terrain'}}
        self.terrain.with_suffix('.json').write_text(json.dumps(self.metadata))
        for offset in range(3):
            self.write_tile(offset)

    def write_tile(self,offset,masked_columns=()):
        yy,xx=np.mgrid[0:256,0:256]
        heights=-5+(xx+offset*256)*.4+yy*.2
        encoded=np.rint((heights+10000)*10).astype(np.uint32)
        rgb=np.stack(((encoded>>16)&255,(encoded>>8)&255,encoded&255),axis=-1).astype(np.uint8)
        mask=np.full((256,256),255,dtype=np.uint8)
        for column in masked_columns:mask[:,column]=0
        relative=Path('14')/str(self.x+offset)/f'{self.y}.png'
        (self.terrain/relative).parent.mkdir(parents=True,exist_ok=True)
        (self.terrain/'mask'/relative).parent.mkdir(parents=True,exist_ok=True)
        Image.fromarray(rgb).save(self.terrain/relative)
        Image.fromarray(mask).save(self.terrain/'mask'/relative)

    def coordinate(self,u,v):
        gx,gy=self.x*256+u+.5,self.y*256+v+.5
        return [gx/self.world*360-180,math.degrees(math.atan(math.sinh(math.pi*(1-2*gy/self.world))))]

    def bbox(self,u1=0,v1=0,u2=200,v2=200):
        west,south=self.coordinate(u1,v2)
        east,north=self.coordinate(u2,v1)
        return ','.join(map(str,(west,south,east,north)))

    def way(self,identifier,tags,uv=None):
        return {'type':'way','id':identifier,'tags':tags,
                'geometry':[dict(zip(('lon','lat'),self.coordinate(u,v))) for u,v in (uv or [(20,100),(80,100)])]}

    def build(self,ways):
        self.source.write_text(json.dumps({'elements':ways,'osm3s':{'timestamp_osm_base':'fixture-only'}}))
        build_database(self.source,self.database)
        return MobilityAPI(self.database,self.terrain)

    def test_raw_bilinear_height_preserves_negative_values_and_cross_tile_ramp(self):
        sampler=TerrainSampler(self.terrain)
        self.assertTrue(sampler.available)
        for u,v in [(1.25,2.5),(128.75,110.25),(255.25,110.5),(256.75,110.5)]:
            with self.subTest(u=u):
                self.assertAlmostEqual(sampler.sample(*self.coordinate(u,v)),-5+.4*u+.2*v,places=6)
        self.assertLess(sampler.sample(*self.coordinate(1.25,2.5)),0)
        # Metadata's 8x visual preference cannot multiply the server's raw DEM.
        self.assertAlmostEqual(sampler.sample(*self.coordinate(100,100)),55,places=6)

    def test_reverse_oneway_car_and_raw_uphill_pedestrian_profile(self):
        api=self.build([self.way(1,{'highway':'residential','oneway':'-1'}),
                        self.way(2,{'highway':'footway'},[(20,110),(80,110)]),
                        self.way(3,{'highway':'steps'},[(35,95),(35,125)])])
        routes={r['source_way_id']:r for r in api.features(self.bbox())['routes']}
        car=routes['osm:way:1'];person=routes['osm:way:2']
        self.assertTrue(car['oneway'])
        np.testing.assert_allclose(car['coordinates'][0][:2],self.coordinate(80,100),atol=1e-9,rtol=0)
        np.testing.assert_allclose(car['coordinates'][-1][:2],self.coordinate(20,100),atol=1e-9,rtol=0)
        self.assertAlmostEqual(car['coordinates'][0][2],47,places=3)
        self.assertAlmostEqual(car['coordinates'][-1][2],23,places=3)
        self.assertAlmostEqual(car['elevation_loss_m'],24,places=3)
        self.assertFalse(person['oneway'])
        self.assertAlmostEqual(person['elevation_gain_m'],24,places=3)
        self.assertTrue(all(b[2]>=a[2] for a,b in zip(person['coordinates'],person['coordinates'][1:])))
        self.assertGreater(person['max_slope_degrees'],2)
        self.assertLess(person['max_slope_degrees'],4)
        self.assertEqual(routes['osm:way:3']['category'],'steps')
        clipped=api.features(self.bbox(30,80,70,130))['routes']
        car=next(r for r in clipped if r['kind']=='car')
        self.assertGreater(car['coordinates'][0][0],car['coordinates'][-1][0])

    def test_coverage_gap_splits_lines_and_missing_dem_does_not_make_zero_height(self):
        self.write_tile(0,range(48,55))
        api=self.build([self.way(1,{'highway':'footway'})])
        result=api.features(self.bbox())
        self.assertEqual(len(result['routes']),2)
        self.assertGreater(result['metadata']['missing_elevation_samples'],0)
        for route in result['routes']:
            self.assertTrue(all(p[2]!=0 for p in route['coordinates']))
            for lon,lat,height in route['coordinates']:
                self.assertIsNotNone(api.terrain.sample(lon,lat))
        middle=api.terrain.sample(*self.coordinate(50,100))
        self.assertIsNone(middle)
        (self.terrain/'14'/str(self.x)/f'{self.y}.png').unlink()
        fresh=MobilityAPI(self.database,self.terrain)
        result=fresh.features(self.bbox())
        self.assertEqual(result['routes'],[])
        self.assertGreater(result['metadata']['missing_tiles'],0)

    def test_private_elevated_and_mode_restricted_ways_are_excluded(self):
        tags=[{'highway':'residential','access':'private'},
              {'highway':'residential','motorcar':'no'},
              {'highway':'residential','bridge':'yes'},
              {'highway':'residential','tunnel':'yes'},
              {'highway':'residential','layer':'1'},
              {'highway':'residential','layer':'-1'},
              {'highway':'residential','oneway':'reversible'},
              {'highway':'footway','foot':'no'},
              {'highway':'footway','access:conditional':'no @ (night)'},
              {'highway':'steps','level':'1'},
              {'highway':'footway'}]
        api=self.build([self.way(i+1,t) for i,t in enumerate(tags)])
        result=api.features(self.bbox())
        self.assertEqual([r['source_way_id'] for r in result['routes']],['osm:way:11'])
        self.assertTrue(travel_mode({'highway':'residential','junction':'roundabout'},'roadway')[1])
        self.assertFalse(travel_mode({'highway':'residential','junction':'roundabout','oneway':'no'},'roadway')[1])
        self.assertIsNone(travel_mode({'highway':'motorway_link'},'roadway')[0])

    def test_between_sample_mask_hole_cannot_be_bridged(self):
        # All three 12 m samples are supported, but the first interval passes
        # through a different bilinear cell whose lower-left pixel is NoData.
        api=self.build([self.way(1,{'highway':'footway'},[(20.9,100.9),(23.12,103.12)])])
        before=api.features(self.bbox())
        self.assertEqual(len(before['routes']),1)
        coordinates=before['routes'][0]['coordinates']
        self.assertEqual(len(coordinates),3)
        mask_path=self.terrain/'mask'/'14'/str(self.x)/f'{self.y}.png'
        with Image.open(mask_path) as image:mask=np.asarray(image).copy()
        mask[102,21]=0
        Image.fromarray(mask).save(mask_path)
        api=MobilityAPI(self.database,self.terrain)
        self.assertTrue(all(api.terrain.sample(*p[:2]) is not None for p in coordinates))
        a,b=coordinates[:2]
        self.assertIsNone(api.terrain.sample((a[0]+b[0])/2,(a[1]+b[1])/2))
        self.assertFalse(api.terrain.segment_supported(a[:2],b[:2]))
        self.assertFalse(api.terrain.segment_supported(b[:2],a[:2]))
        after=api.features(self.bbox())
        self.assertEqual(after['metadata']['missing_elevation_samples'],0)
        self.assertGreater(after['metadata']['unsupported_elevation_segments'],0)
        # Splitting leaves fragments shorter than the 12 m minimum; there must
        # be no synthetic supported path connecting the valid sample points.
        self.assertEqual(after['routes'],[])

    def test_mechanical_walkways_are_excluded(self):
        for key in ('conveying','escalator'):
            for value in ('yes','forward','backward','reversible','unknown'):
                for highway,category in (('steps','steps'),('footway','walkway'),('residential','roadway')):
                    with self.subTest(key=key,value=value,highway=highway):
                        mode=travel_mode({'highway':highway,key:value},category)
                        self.assertIsNone(mode[0])
                        self.assertEqual(mode[3],'mechanical_way')
            for value in ('no','false','0'):
                self.assertEqual(travel_mode({'highway':'steps',key:value},'steps')[0],'pedestrian')
        api=self.build([self.way(1,{'highway':'steps','conveying':'forward'}),
                        self.way(2,{'highway':'steps','escalator':'yes'}),
                        self.way(3,{'highway':'steps','conveying':'no'})])
        result=api.features(self.bbox())
        self.assertEqual([r['source_way_id'] for r in result['routes']],['osm:way:3'])
        self.assertEqual(result['metadata']['skipped']['mechanical_way'],2)

    def test_segment_support_checks_cross_tile_pixels_and_bounds_work(self):
        a,b=self.coordinate(254.9,100.9),self.coordinate(256.01,102.01)
        sampler=TerrainSampler(self.terrain)
        self.assertTrue(sampler.segment_supported(a,b))
        mask_path=self.terrain/'mask'/'14'/str(self.x)/f'{self.y}.png'
        with Image.open(mask_path) as image:mask=np.asarray(image).copy()
        mask[102,255]=0
        Image.fromarray(mask).save(mask_path)
        sampler=TerrainSampler(self.terrain)
        self.assertIsNotNone(sampler.sample(*a))
        self.assertIsNotNone(sampler.sample(*b))
        self.assertFalse(sampler.segment_supported(a,b))
        session=sampler.session()
        self.assertFalse(sampler.segment_supported(self.coordinate(20,100),self.coordinate(100,100),session))
        self.assertTrue(session['coverage_limit_hit'])
        self.assertEqual(session['coverage_pixels'],0)
        self.assertEqual(session['tile_reads'],0)

    def test_selection_is_distributed_deterministic_steep_and_resource_bounded(self):
        ways=[]
        identifier=0
        for gx in range(4):
            for gy in range(4):
                for local in range(6):
                    identifier+=1
                    highway=('residential','footway','steps')[local%3]
                    u,v=10+gx*45,10+gy*45+local*2
                    ways.append(self.way(identifier,{'highway':highway},[(u,v),(u+20,v)]))
        api=self.build(ways)
        first=api.features(self.bbox());second=api.features(self.bbox())
        self.assertEqual(first['routes'],second['routes'])
        self.assertEqual(len(first['routes']),60)
        self.assertTrue(first['metadata']['truncated'])
        self.assertEqual(set(r['category'] for r in first['routes']),{'roadway','walkway','steps'})
        points=[r['coordinates'][len(r['coordinates'])//2] for r in first['routes']]
        self.assertGreater(max(p[0] for p in points)-min(p[0] for p in points),.01)
        self.assertGreater(max(p[1] for p in points)-min(p[1] for p in points),.007)
        self.assertLessEqual(first['metadata']['sample_points'],18000)
        self.assertLessEqual(first['metadata']['tile_keys'],24)
        self.assertLessEqual(first['metadata']['coverage_pixels'],first['metadata']['sample_points']*64)
        self.assertFalse(first['metadata']['coverage_limit_hit'])
        self.assertEqual(second['metadata']['tile_reads'],0)
        self.assertTrue(all(len(r['coordinates'])<=180 and r['length_m']<=750.01 for r in first['routes']))
        with patch('server.mobility.MAX_SAMPLE_POINTS',2):
            result=api.features(self.bbox())
            self.assertEqual(result['routes'],[])
            self.assertTrue(result['metadata']['truncated'])
        api=self.build([self.way(1,{'highway':'footway'},[(30,20),(30,45)]),
                        self.way(2,{'highway':'footway'},[(20,30),(45,30)])])
        with patch('server.mobility.MAX_ROUTES',1):
            result=api.features(self.bbox())
            self.assertEqual(result['routes'][0]['source_way_id'],'osm:way:2')

    def test_lru_and_per_request_tile_budget_and_input_validation(self):
        sampler=TerrainSampler(self.terrain,cache_size=1)
        for u in (20,280,20):
            session=sampler.session();self.assertIsNotNone(sampler.sample(*self.coordinate(u,100),session))
            self.assertEqual(session['tile_reads'],1)
            self.assertLessEqual(len(sampler._cache),1)
        sampler=TerrainSampler(self.terrain)
        with patch('server.mobility.MAX_REQUEST_TILES',1):
            session=sampler.session()
            self.assertIsNone(sampler.sample(*self.coordinate(255.25,100),session))
            self.assertTrue(session['tile_limit_hit'])
            self.assertEqual(session['tile_reads'],1)
        api=MobilityAPI(self.database,self.terrain)
        self.assertFalse(api.features(self.bbox())['metadata']['available'])
        self.assertFalse(self.database.exists())
        for bbox in ('nan,37,127,38','127,37,126,38','1,2,3','126,37,127,38',None):
            with self.subTest(bbox=bbox),self.assertRaises(ValueError):api.features(bbox)
        self.assertTrue(TerrainSampler(self.terrain.with_suffix('.json')).available)


if __name__=='__main__':
    unittest.main()
