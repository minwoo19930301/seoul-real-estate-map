"""Bounded-cost residential facades on an unchanged source polygon.

All facade style, window layouts and balcony locations are illustrative. The
caller supplies the height envelope and floor estimate; this module never infers
heights or dwelling classification. See docs/RESIDENTIAL_MODEL_DESIGN.md.
"""
import math
from shapely.geometry.polygon import orient

KINDS = frozenset(('villa', 'apartment', 'mixed-use', 'officetel'))
MAX_DETAIL_EDGES = 12
MAX_WINDOW_BAYS = 4
MAX_WINDOW_ROWS = 24
MAX_DISPLAY_OFFSET_M = .04

_PALETTES = {
    'villa': ((.67, .57, .47), (.58, .39, .29), (.73, .69, .61)),
    'apartment': ((.77, .77, .71), (.72, .76, .73), (.79, .75, .66)),
    'mixed-use': ((.70, .72, .70), (.65, .69, .70), (.74, .71, .65)),
    'officetel': ((.58, .65, .68), (.65, .66, .64), (.54, .60, .64)),
}
_GLASS = (.23, .36, .40)
_ROOF = (.38, .43, .41)
_FRAME = (.74, .76, .72)
_BRICK = (.46, .29, .22)
_CORE = (.55, .60, .58)


class _Face:
    """A source edge with its own detail quota, preventing one face starvation."""
    def __init__(self, mesh, a, b, interior, quota):
        self.mesh = mesh
        self.a = a
        self.length = math.dist(a, b)
        self.ux = (b[0]-a[0])/self.length
        self.uz = (b[1]-a[1])/self.length
        self.interior = interior
        self.left = quota

    def point(self, distance, y, offset=.006):
        return (self.a[0]+self.ux*distance+self.uz*offset,
                y, self.a[1]+self.uz*distance-self.ux*offset)

    def panel(self, mat, a, b, low, high, color, offset=.006):
        if self.left <= 0 or b <= a or high <= low:
            return False
        self.mesh.quad(mat, self.point(a, low, offset), self.point(a, high, offset),
                       self.point(b, high, offset), self.point(b, low, offset), color)
        self.left -= 1
        return True

    def balcony(self, a, b, low, high):
        # A shallow railing/slab relief, not an invented habitable room volume.
        if self.interior or self.left < 4:
            return
        depth = MAX_DISPLAY_OFFSET_M
        lip = min(.06, (high-low)*.12)
        self.panel(0, a, b, low, low+lip, _FRAME, depth)
        self.panel(0, a, b, high-lip, high, _FRAME, depth)
        self.mesh.quad(2, self.point(a, low+lip, 0), self.point(b, low+lip, 0),
                       self.point(b, low+lip, depth), self.point(a, low+lip, depth), _FRAME)
        self.mesh.quad(1, self.point(a, low+lip, depth), self.point(a, high-lip, depth),
                       self.point(b, high-lip, depth), self.point(b, low+lip, depth), (.39, .47, .45))
        self.left -= 2


def _sample_rows(floors, count):
    if count <= 1:
        return [0]
    return sorted({round(i*(floors-1)/(count-1)) for i in range(count)})


def residential_geometry(mesh, poly, height, floors, kind, seed):
    """Append geometry and return True; unsupported/invalid input is a no-op.

    ``poly`` is one valid metre Polygon (holes retained), ``height`` a positive
    maximum y, and ``floors`` a caller-supplied storey estimate. Uses only existing
    Mesh.solid/quad and material indices 0, 1, 2; no builder import or file writes.
    A rectangle is bounded by 240 triangles at 4 floors and 930 at 20 floors.
    """
    if kind not in KINDS:
        return False
    try:
        height = float(height)
        floor_number = float(floors or 1)
        seed = int(seed)
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(height) or height <= 0 or not math.isfinite(floor_number):
        return False
    if poly.geom_type != 'Polygon' or poly.is_empty or not poly.is_valid or poly.area <= 1e-7:
        return False
    floors = max(1, min(200, int(floor_number)))
    poly = orient(poly, sign=1)
    wall = _PALETTES[kind][seed % len(_PALETTES[kind])]
    mesh.solid(poly, 0, height, wall, _ROOF)

    # No buffered/rectangular replacement of the source perimeter or courtyard.
    edges = []
    for ring_index, ring in enumerate([poly.exterior, *poly.interiors]):
        points = list(ring.coords)
        for a, b in zip(points, points[1:]):
            length = math.dist(a, b)
            if length >= 1.1:
                edges.append((length, a, b, ring_index > 0))
    edges.sort(key=lambda edge: -edge[0])
    edges = edges[:MAX_DETAIL_EDGES]
    if not edges:
        return True
    detail_budget = min(460, 11+26*floors)
    floor_height = height/floors
    row_count = min(floors, MAX_WINDOW_ROWS)
    for edge_index, (length, a, b, interior) in enumerate(edges):
        quota = detail_budget//len(edges)+(edge_index < detail_budget % len(edges))
        face = _Face(mesh, a, b, interior, quota)
        edge_inset = min(.35, length*.075)
        usable = length-2*edge_inset
        # Thin plinth and roof-edge courses do not increase the height envelope.
        base_top = min(height*.12, floor_height*.28)
        face.panel(0, 0, length, 0, base_top, _BRICK if kind == 'villa' else _CORE)
        face.panel(0, 0, length, height-min(.24, height*.04), height, _FRAME)

        podium_levels = min(2, max(1, floors//7)) if kind == 'mixed-use' else 0
        podium_top = min(height*.45, floor_height*podium_levels)
        if podium_levels:
            face.panel(0, 0, length, 0, podium_top, (.45, .47, .44), .007)
            face.panel(0, 0, length, podium_top-min(.16, podium_top*.08), podium_top, _FRAME, .01)
        if kind == 'apartment' and not interior:
            # An applied vertical stair/service-core strip; no extra tower mass.
            core_width = min(length*.09, 1.2)
            middle = length*(.32 if seed % 2 else .68)
            face.panel(0, middle-core_width/2, middle+core_width/2,
                       base_top, height-min(.24, height*.04), _CORE, .004)

        # Reserve window capacity first. Large/complex outlines sample fewer rows
        # or bays evenly instead of exhausting the quota on the first few faces.
        rows = min(row_count, max(1, face.left//2))
        band_count = min(rows, 6) if kind in ('mixed-use', 'officetel') else 0
        window_allowance = max(1, face.left-band_count)
        rows = min(rows, window_allowance)
        max_bays = 3 if kind == 'villa' else MAX_WINDOW_BAYS
        bays = max(1, min(max_bays, int(usable/(2.5 if kind == 'officetel' else 3.0)),
                          window_allowance//max(1, rows)))
        sampled = _sample_rows(floors, rows)
        pitch = usable/bays
        windows = []
        for floor in sampled:
            store = podium_levels and floor < podium_levels
            low = floor_height*(floor+(.10 if store else .25))
            high = min(height-min(.24, height*.04), floor_height*(floor+(.91 if kind == 'officetel' or store else .78)))
            if high <= low:
                continue
            for bay in range(bays):
                margin = .08 if store else .30 if kind == 'officetel' else .19
                left = edge_inset+(bay+margin)*pitch
                right = edge_inset+(bay+1-margin)*pitch
                # Glass stays just outside the wall/podium to avoid z-fighting.
                glass = (.30, .43, .47) if (seed+floor+bay) % 9 == 0 else _GLASS
                if face.panel(1, left, right, low, high, glass, .012 if store else .008):
                    windows.append((floor, bay, left, right, low, high))
        if band_count:
            for floor in _sample_rows(floors, band_count):
                y = floor_height*(floor+.96)
                face.panel(0, 0, length, y, min(height, y+min(.09, floor_height*.025)), _FRAME, .014)
        if kind == 'villa':
            # Low-rise bays receive window dividers and a few shallow balconies.
            for floor, bay, left, right, low, high in windows:
                if floor > 0 and bay == (seed+edge_index) % bays and edge_index < 2:
                    face.balcony(left-.03, right+.03, low, low+(high-low)*.35)
            for floor, bay, left, right, low, high in windows:
                middle = (left+right)/2
                face.panel(0, middle-min(.025, pitch*.02), middle+min(.025, pitch*.02),
                           low, high, _FRAME, .01)
        elif kind == 'apartment':
            # Window sills emphasize stacked dwellings within the remaining cap.
            for _, _, left, right, low, _ in windows:
                face.panel(0, left, right, low, low+min(.08, floor_height*.025), _FRAME, .014)
    return True
