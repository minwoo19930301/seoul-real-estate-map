"""Bounded illustrative traversals on original OSM lines and unscaled terrain.

MobilityAPI(roads_sqlite, public_data_terrain_directory).features('w,s,e,n')
also accepts the sibling terrain.json path. These are individual source ways,
not a routing graph, live traffic, measured travel speeds or surveyed heights.
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
import json
import math
from pathlib import Path
import sqlite3
from server.database import connect_readonly, available, database_bytes
import threading
import zlib

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point, box
from shapely.ops import substring

from server.roads import parse_bbox

DEM_ZOOM = 14
TILE_SIZE = 256
EARTH_RADIUS = 6378137.0
METRES_PER_DEGREE = EARTH_RADIUS * math.pi / 180
MAX_BBOX_METRES = 2200
MAX_ROUTES = 60
MAX_CANDIDATES = 320
MAX_PROFILES = 180
MAX_WAY_VERTICES = 4000
MAX_ROUTE_POINTS = 180
MAX_SAMPLE_POINTS = 18000
MAX_ROUTE_METRES = 750
SAMPLE_SPACING_METRES = 12
TILE_CACHE_SIZE = 32
MAX_REQUEST_TILES = 24
MAX_SEGMENT_MASK_PIXELS = 64
GRID_SIZE = 4
RESTRICTED_ACCESS = {'no', 'private', 'restricted', 'customers', 'delivery', 'agricultural',
                     'forestry', 'permit', 'destination', 'emergency'}
CAR_HIGHWAYS = {'motorway','motorway_link','trunk','trunk_link','primary','primary_link',
                'secondary','secondary_link','tertiary','tertiary_link','residential',
                'unclassified','living_street','service'}


def tag_value(tags, key):
    return str(tags.get(key, '')).strip().casefold()


def travel_mode(tags, category):
    """Conservative simulation eligibility; never invent an offset sidewalk."""
    if any(tag_value(tags,key) not in ('','no','false','0') for key in ('conveying','escalator')):
        return None,False,False,'mechanical_way'
    for key in ('bridge','tunnel','covered','indoor','ford','location'):
        value = tag_value(tags,key)
        if value and value not in ('no','false','0','surface','outdoor','outdoors'):
            return None, False, False, 'non_ground_way'
    for key in ('layer','level','min_height'):
        value = tag_value(tags,key)
        if value:
            try:
                if float(value) != 0:
                    return None,False,False,'non_ground_way'
            except ValueError:
                return None,False,False,'non_ground_way'
    if tag_value(tags,'area') == 'yes' or any(tag_value(tags,k) not in ('','no','false','0') for k in ('construction','proposed','disused','abandoned')):
        return None,False,False,'unusable_way'
    if tag_value(tags,'access') in RESTRICTED_ACCESS or tags.get('access:conditional'):
        return None,False,False,'restricted_access'
    if category in ('walkway','steps'):
        if tag_value(tags,'foot') in RESTRICTED_ACCESS or tags.get('foot:conditional'):
            return None,False,False,'restricted_access'
        if tag_value(tags,'highway') == 'cycleway' and tag_value(tags,'foot') not in ('yes','designated','permissive'):
            return None,False,False,'pedestrian_access_unknown'
        return 'pedestrian',False,False,None
    if category != 'roadway' or tag_value(tags,'highway') not in CAR_HIGHWAYS:
        return None,False,False,'not_a_car_road'
    if any(tag_value(tags,k) in RESTRICTED_ACCESS or tags.get(k+':conditional') for k in ('vehicle','motor_vehicle','motorcar')):
        return None,False,False,'restricted_access'
    if tags.get('oneway:conditional'):
        return None,False,False,'conditional_direction'
    direction = tag_value(tags,'oneway:motorcar') or tag_value(tags,'oneway:motor_vehicle') or tag_value(tags,'oneway')
    if direction in ('-1','reverse'):
        return 'car',True,True,None
    if direction in ('yes','true','1'):
        return 'car',True,False,None
    if direction in ('no','false','0'):
        return 'car',False,False,None
    if direction:
        return None,False,False,'unknown_direction'
    # motorway_link requires an explicit direction; unlike motorway, its
    # one-way default is not uniformly implied by the OSM definition.
    if tag_value(tags,'highway') == 'motorway_link':
        return None,False,False,'unknown_direction'
    implicit = tag_value(tags,'junction') == 'roundabout' or tag_value(tags,'highway') == 'motorway'
    return 'car',implicit,False,None


class TerrainSampler:
    """z14 Terrain-RGB bilinear sampling on global pixel CENTER coordinates.

    Each contributing pixel must have mask=255. No lower-zoom fallback, padded
    height, numeric zero fallback, exaggeration or clamping is introduced.
    """
    def __init__(self, terrain_root, cache_size=TILE_CACHE_SIZE):
        root = Path(terrain_root).resolve()
        if root.suffix == '.json':
            self.root,self.metadata_path = root.parent / root.stem,root
        elif (root / 'terrain.json').is_file():
            self.root,self.metadata_path = root / 'terrain',root / 'terrain.json'
        else:
            self.root,self.metadata_path = root,root.with_suffix('.json')
        self.metadata = {}
        self.reason = None
        try:
            self.metadata = json.loads(self.metadata_path.read_text())
            if self.metadata.get('encoding') != 'mapbox' or self.metadata.get('tileSize') != TILE_SIZE:
                raise ValueError('unsupported DEM encoding or tile size')
            if not self.metadata.get('minzoom',0) <= DEM_ZOOM <= self.metadata.get('maxzoom',0):
                raise ValueError('z14 DEM not declared')
            if not (self.root / str(DEM_ZOOM)).is_dir() or not (self.root / 'mask' / str(DEM_ZOOM)).is_dir():
                raise ValueError('DEM or coverage mask directory missing')
        except (OSError,ValueError,TypeError) as error:
            self.reason = str(error)
        self.available = self.reason is None
        self.cache_size = max(1,int(cache_size))
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def session(self):
        return {'tiles':{},'tile_reads':0,'cache_hits':0,'missing_tiles':0,'tile_limit_hit':False,
                'coverage_segments':0,'coverage_pixels':0,'coverage_limit_hit':False}

    def _tile(self,x,y,session):
        key = (x,y)
        if key in session['tiles']:
            return session['tiles'][key]
        if len(session['tiles']) >= MAX_REQUEST_TILES:
            session['tile_limit_hit'] = True
            return None
        with self._lock:
            if key in self._cache:
                tile = self._cache.pop(key)
                self._cache[key] = tile
                session['cache_hits'] += 1
            else:
                relative = Path(str(DEM_ZOOM)) / str(x) / f'{y}.png'
                tile = None
                try:
                    session['tile_reads'] += 1
                    with Image.open(self.root / relative) as image:
                        if image.mode != 'RGB' or image.size != (TILE_SIZE,TILE_SIZE):
                            raise ValueError('invalid DEM tile')
                        rgb = np.asarray(image,dtype=np.uint32)
                    with Image.open(self.root / 'mask' / relative) as image:
                        if image.mode != 'L' or image.size != (TILE_SIZE,TILE_SIZE):
                            raise ValueError('invalid coverage mask')
                        mask = np.asarray(image).copy()
                    heights = -10000.0 + (rgb[...,0]*65536+rgb[...,1]*256+rgb[...,2])*0.1
                    tile = (heights,mask)
                except (OSError,ValueError):
                    session['missing_tiles'] += 1
                self._cache[key] = tile
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
        session['tiles'][key] = tile
        return tile

    def _pixel_coordinate(self,lon,lat):
        if not self.available or not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon < 180 or not -85.05112878 < lat < 85.05112878:
            return None
        bounds = self.metadata.get('source_bounds')
        if bounds and not (bounds[0] <= lon <= bounds[2] and bounds[1] <= lat <= bounds[3]):
            return None
        size = TILE_SIZE * 2 ** DEM_ZOOM
        px = (lon+180)/360*size - 0.5
        py = (1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*size - 0.5
        return px,py

    def segment_supported(self,start,end,session=None):
        """Conservatively validate every bilinear support pixel along a segment.

        Longitude and latitude, and their Mercator pixel coordinates, are each
        monotone along an emitted straight segment. Its complete support is
        therefore contained in this inclusive pixel rectangle. Inspecting the
        entire rectangle can reject an unused corner near a hole, but cannot
        bridge a hole between the 12 m elevation samples. The bounded rectangle
        also avoids floating-point grid-crossing/corner cases of a pixel walk.
        """
        a,b = self._pixel_coordinate(*start),self._pixel_coordinate(*end)
        if a is None or b is None:
            return False
        if session is None:
            session = self.session()
        session['coverage_segments'] += 1
        x0,x1 = math.floor(min(a[0],b[0])),math.floor(max(a[0],b[0]))+1
        y0,y1 = math.floor(min(a[1],b[1])),math.floor(max(a[1],b[1]))+1
        pixel_count = (x1-x0+1)*(y1-y0+1)
        if pixel_count>MAX_SEGMENT_MASK_PIXELS:
            session['coverage_limit_hit'] = True
            return False
        session['coverage_pixels'] += pixel_count
        for tx in range(x0//TILE_SIZE,x1//TILE_SIZE+1):
            left,right = max(x0-tx*TILE_SIZE,0),min(x1-tx*TILE_SIZE,TILE_SIZE-1)
            for ty in range(y0//TILE_SIZE,y1//TILE_SIZE+1):
                top,bottom = max(y0-ty*TILE_SIZE,0),min(y1-ty*TILE_SIZE,TILE_SIZE-1)
                tile = self._tile(tx,ty,session)
                if tile is None or not np.all(tile[1][top:bottom+1,left:right+1] == 255):
                    return False
        return True

    def sample(self,lon,lat,session=None):
        pixel = self._pixel_coordinate(lon,lat)
        if pixel is None:
            return None
        if session is None:
            session = self.session()
        px,py = pixel
        ix,iy = math.floor(px),math.floor(py)
        fx,fy = px-ix,py-iy
        values = []
        for dy,dx in ((0,0),(0,1),(1,0),(1,1)):
            gx,gy = ix+dx,iy+dy
            tx,col = divmod(gx,TILE_SIZE)
            ty,row = divmod(gy,TILE_SIZE)
            tile = self._tile(tx,ty,session)
            if tile is None or tile[1][row,col] != 255:
                return None
            values.append(float(tile[0][row,col]))
        return ((1-fx)*(1-fy)*values[0]+fx*(1-fy)*values[1]
                +(1-fx)*fy*values[2]+fx*fy*values[3])


def densify(coordinates):
    result = [coordinates[0]]
    for start,end in zip(coordinates,coordinates[1:]):
        length = math.dist(start,end)
        if length < 1e-6:
            continue
        intervals = max(1,math.ceil(length/SAMPLE_SPACING_METRES))
        if len(result)+intervals > MAX_ROUTE_POINTS:
            return None
        for index in range(1,intervals+1):
            fraction = index/intervals
            result.append((start[0]+(end[0]-start[0])*fraction,start[1]+(end[1]-start[1])*fraction))
    return result


def line_parts(geometry):
    if geometry.geom_type == 'LineString':
        return [geometry] if not geometry.is_empty else []
    if hasattr(geometry,'geoms'):
        return [line for part in geometry.geoms for line in line_parts(part)]
    return []


class MobilityAPI:
    def __init__(self, roads, terrain_root):
        self.database = Path(roads).resolve()
        self.terrain = TerrainSampler(terrain_root)
        self.road_metadata = {}
        if available(self.database):
            with self.connect() as db:
                self.road_metadata = {row['key']:json.loads(row['value']) for row in db.execute('SELECT key,value FROM metadata')}

    def connect(self):
        db = connect_readonly(self.database)
        db.row_factory = sqlite3.Row
        return db

    def _candidates(self,bounds):
        west,south,east,north = bounds
        with self.connect() as db:
            return db.execute('''WITH candidates AS (
                SELECT b.rowid,b.category,(r.minx+r.maxx)/2 AS cx,(r.miny+r.maxy)/2 AS cy
                FROM road_index r JOIN roads b ON b.rowid=r.rowid
                WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=?
            ), cells AS (
                SELECT *,MIN(3,MAX(0,CAST((cx-?)/? AS INTEGER))) gx,
                    MIN(3,MAX(0,CAST((cy-?)/? AS INTEGER))) gy FROM candidates
            ), ranked AS (
                SELECT rowid,gx,gy,category,ROW_NUMBER() OVER(PARTITION BY gx,gy,category ORDER BY rowid) rank FROM cells
            ) SELECT b.* FROM ranked r JOIN roads b ON b.rowid=r.rowid
                ORDER BY r.rank,r.gx,r.gy,r.category,r.rowid LIMIT ?''',
                (east,west,north,south,west,(east-west)/GRID_SIZE,south,(north-south)/GRID_SIZE,MAX_CANDIDATES+1)).fetchall()

    def features(self,bbox):
        west,south,east,north = bounds = parse_bbox(bbox)
        cx,cy = (west+east)/2,(south+north)/2
        sx,sy = METRES_PER_DEGREE*math.cos(math.radians(cy)),METRES_PER_DEGREE
        width,height = (east-west)*sx,(north-south)*sy
        if width > MAX_BBOX_METRES or height > MAX_BBOX_METRES:
            raise ValueError(f'mobility bbox must be at most {MAX_BBOX_METRES} metres wide and high')
        metadata = {
            'available':available(self.database) and self.terrain.available,'truncated':False,
            'count':0,'counts':{'pedestrian':0,'car':0},'category_counts':{'roadway':0,'walkway':0,'steps':0},
            'max_routes':MAX_ROUTES,'max_bbox_metres':MAX_BBOX_METRES,'sample_spacing_m':SAMPLE_SPACING_METRES,
            'max_route_length_m':MAX_ROUTE_METRES,'max_route_points':MAX_ROUTE_POINTS,
            'max_candidates':MAX_CANDIDATES,'max_profiled_parts':MAX_PROFILES,'max_sample_points':MAX_SAMPLE_POINTS,
            'dem_zoom':DEM_ZOOM,'elevation_exaggeration':1,'elevation_unit':'metres',
            'elevation_estimated':True,
            'coverage_policy':'Every pixel in each segment\'s bilinear-support bounding rectangle must have mask 255; missing samples or unsupported intervals split lines. This conservatively excludes some intervals beside holes.',
            'source':'Original OpenStreetMap ways and locally interpolated Seoul contour/spot DEM.',
            'road_source_url':self.road_metadata.get('source_url','https://www.openstreetmap.org'),
            'road_source_timestamp':self.road_metadata.get('source_osm_timestamp'),
            'terrain_source_url':self.terrain.metadata.get('source',{}).get('url'),
            'terrain_source_method':self.terrain.metadata.get('method'),
            'vertical_datum':self.terrain.metadata.get('vertical_datum'),
            'selection_policy':'4x4 geographic/category round-robin; steep supported profiles first within each bucket.',
            'simulation_only':True,'routing_graph':False,
            'geometry_policy':'Original ground-level way segments, clipped/capped and densified; no invented sidewalk or lane offsets.',
        }
        result = {'routes':[],'metadata':metadata}
        if not metadata['available']:
            metadata['reason'] = 'roads_database_missing' if not available(self.database) else 'terrain_or_mask_unavailable'
            return result
        rows = self._candidates(bounds)
        metadata['truncated'] = len(rows)>MAX_CANDIDATES
        metadata['candidate_count'] = min(len(rows),MAX_CANDIDATES)
        window = box(-width/2,-height/2,width/2,height/2)
        session = self.terrain.session()
        skipped = Counter()
        routes = []
        sampled = profiled = missing = unsupported = 0
        exhausted = False
        for row in rows[:MAX_CANDIDATES]:
            raw = row['tags']
            tags = json.loads(zlib.decompress(raw) if isinstance(raw,bytes) else raw)
            kind,oneway,reverse,reason = travel_mode(tags,row['category'])
            if reason:
                skipped[reason] += 1
                continue
            if row['vertex_count']>MAX_WAY_VERTICES:
                skipped['way_vertex_limit'] += 1
                metadata['truncated'] = True
                continue
            original = json.loads(row['geometry'])['coordinates']
            coordinates = [(float(p[0]-cx)*sx,float(p[1]-cy)*sy) for p in original]
            if reverse:
                coordinates.reverse()
            line = LineString(coordinates)
            parts = line_parts(line.intersection(window))
            parts.sort(key=lambda p: min(line.project(Point(p.coords[0])),line.project(Point(p.coords[-1]))))
            for part_index,part in enumerate(parts):
                xy = list(part.coords)
                if line.project(Point(xy[0])) > line.project(Point(xy[-1])):
                    part = LineString(xy[::-1])
                if part.length>MAX_ROUTE_METRES:
                    center_distance = part.project(Point(0,0))
                    start = max(0,min(part.length-MAX_ROUTE_METRES,center_distance-MAX_ROUTE_METRES/2))
                    part = substring(part,start,start+MAX_ROUTE_METRES)
                minimum = 12 if kind=='pedestrian' else 30
                if part.length<minimum:
                    skipped['short_part'] += 1
                    continue
                points = densify(list(part.coords))
                if points is None:
                    skipped['route_vertex_limit'] += 1
                    metadata['truncated'] = True
                    continue
                if profiled>=MAX_PROFILES or sampled+len(points)>MAX_SAMPLE_POINTS:
                    exhausted = metadata['truncated'] = True
                    break
                profiled += 1
                sampled += len(points)
                segments = []
                segment = []
                for x,y in points:
                    # Validate and sample the exact coordinates sent to clients;
                    # rounding must not move a validated edge into a mask hole.
                    lon,lat = round(cx+x/sx,10),round(cy+y/sy,10)
                    elevation = self.terrain.sample(lon,lat,session)
                    if elevation is None:
                        missing += 1
                        if segment:
                            segments.append(segment)
                        segment = []
                    else:
                        if segment and not self.terrain.segment_supported(segment[-1][:2],(lon,lat),session):
                            unsupported += 1
                            segments.append(segment)
                            segment = []
                        segment.append((lon,lat,elevation,x,y))
                if segment:
                    segments.append(segment)
                for segment_index,segment in enumerate(segments):
                    if len(segment)<2:
                        continue
                    lengths = [math.hypot(b[3]-a[3],b[4]-a[4]) for a,b in zip(segment,segment[1:])]
                    length = sum(lengths)
                    if length<minimum:
                        continue
                    rises = [b[2]-a[2] for a,b in zip(segment,segment[1:])]
                    slope = max((math.degrees(math.atan2(abs(dz),dl)) for dz,dl in zip(rises,lengths) if dl>1e-6),default=0)
                    midpoint = segment[len(segment)//2]
                    cell = (min(3,max(0,int((midpoint[0]-west)/(east-west)*GRID_SIZE))),
                            min(3,max(0,int((midpoint[1]-south)/(north-south)*GRID_SIZE))),row['category'])
                    routes.append({'id':f"{row['id']}:{kind}:{part_index}:{segment_index}",
                        'source_way_id':row['id'],'kind':kind,'category':row['category'],
                        'coordinates':[[round(p[0],10),round(p[1],10),round(p[2],4)] for p in segment],
                        'oneway':oneway,'length_m':round(length,2),'max_slope_degrees':round(slope,3),
                        'elevation_gain_m':round(sum(max(0,rise) for rise in rises),3),
                        'elevation_loss_m':round(sum(max(0,-rise) for rise in rises),3),
                        '_cell':cell})
            if exhausted:
                break
        buckets = defaultdict(list)
        for route in routes:
            buckets[route['_cell']].append(route)
        for values in buckets.values():
            values.sort(key=lambda r:(-r['max_slope_degrees'],-r['length_m'],r['id']))
        keys = sorted(buckets)
        while keys and len(result['routes'])<MAX_ROUTES:
            following = []
            for key in keys:
                if len(result['routes'])>=MAX_ROUTES:
                    break
                route = buckets[key].pop(0)
                route.pop('_cell')
                result['routes'].append(route)
                if buckets[key]:
                    following.append(key)
            keys = following
        metadata['truncated'] |= len(routes)>len(result['routes']) or session['tile_limit_hit'] or session['coverage_limit_hit']
        metadata.update(count=len(result['routes']),profiled_parts=profiled,sample_points=sampled,
            missing_elevation_samples=missing,unsupported_elevation_segments=unsupported,
            coverage_segments=session['coverage_segments'],coverage_pixels=session['coverage_pixels'],
            coverage_limit_hit=session['coverage_limit_hit'],max_segment_mask_pixels=MAX_SEGMENT_MASK_PIXELS,
            skipped=dict(skipped),tile_reads=session['tile_reads'],
            tile_cache_hits=session['cache_hits'],tile_keys=len(session['tiles']),
            tile_limit_hit=session['tile_limit_hit'],missing_tiles=session['missing_tiles'],
            max_request_tiles=MAX_REQUEST_TILES,tile_cache_capacity=self.terrain.cache_size)
        for route in result['routes']:
            metadata['counts'][route['kind']] += 1
            metadata['category_counts'][route['category']] += 1
        if not result['routes']:
            metadata['reason'] = 'no_supported_ground_routes_in_bbox'
        return result
