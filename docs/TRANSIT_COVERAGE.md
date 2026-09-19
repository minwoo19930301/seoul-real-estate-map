# Transit coverage

`public/transit.json` contains 311 rail-location records and 51 named bus-stop nodes. `scripts/build_transit.py` reads `data/places.sqlite` for rail points and the retained `data/sources/osm-roads-2026-09-08/overpass.json` snapshot for bus nodes. These files are opened read-only; no live database import is required.

Rail records preserve source points, URLs and location methods. Bus stops preserve the exact longitude, latitude and name of actual OSM `highway=bus_stop` nodes within approximately 222 metres of one of those rail points. This is a straight-line selection rule, not walking distance. The set is partial: it is neither every Seoul stop nor a ranking by ridership. Rail records may represent multiple source locations at one physical interchange; station entrances and platforms are not modeled.

Blue points mark rail locations; amber points mark bus stops. Labels appear with zoom and avoid overlapping. Rail and bus visibility can be controlled separately. Transit source coordinates were checked against the retained raw snapshot: see [TRANSIT_VALIDATION.json](TRANSIT_VALIDATION.json).

Regenerate from the repository root with `.venv/bin/python scripts/build_transit.py`. The source snapshot itself stays local and is excluded from Git. Attribution is © OpenStreetMap contributors, ODbL. Source context: [PLACE_SOURCES.md](PLACE_SOURCES.md).
