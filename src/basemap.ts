import type { LayerSpecification, VectorSourceSpecification } from 'maplibre-gl';

// Separate vector layers let road/building controls actually remove those features.
// No building geometry or heights from this online background are displayed.
export const basemapSource: VectorSourceSpecification = {
  type: 'vector', url: 'https://tiles.openfreemap.org/planet',
  attribution: '<a href="https://openfreemap.org/">OpenFreeMap</a> · © <a href="https://openmaptiles.org/">OpenMapTiles</a> · © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
};
const name = ['coalesce', ['get', 'name:ko'], ['get', 'name'], ['get', 'name:latin']] as any;
const roads = ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'service']]] as any;
export const basemapLayers: LayerSpecification[] = [
  // OpenMapTiles carries ordinary parks/gardens in landcover, mostly as grass.
  // A park boundary alone is not evidence that all of its surface is wooded.
  { id: 'base-grass', type: 'fill', source: 'osm', 'source-layer': 'landcover', filter: ['==', ['get', 'class'], 'grass'], paint: { 'fill-color': '#8ccf73', 'fill-opacity': 0.92 } },
  { id: 'base-parks', type: 'fill', source: 'osm', 'source-layer': 'landcover', filter: ['all', ['==', ['get', 'class'], 'grass'], ['in', ['get', 'subclass'], ['literal', ['park', 'garden', 'recreation_ground', 'village_green']]]], paint: { 'fill-color': '#66b95b', 'fill-opacity': 0.88 } },
  { id: 'base-woods', type: 'fill', source: 'osm', 'source-layer': 'landcover', filter: ['==', ['get', 'class'], 'wood'], paint: { 'fill-color': '#3f924c', 'fill-opacity': 0.9 } },
  { id: 'base-cemetery', type: 'fill', source: 'osm', 'source-layer': 'landuse', filter: ['==', ['get', 'class'], 'cemetery'], paint: { 'fill-color': '#a3c888', 'fill-opacity': 0.65 } },
  { id: 'base-water', type: 'fill', source: 'osm', 'source-layer': 'water', paint: { 'fill-color': '#5da9e8' } },
  { id: 'base-roads-case', type: 'line', source: 'osm', 'source-layer': 'transportation', filter: roads,
    layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#e1e5e8', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 14, 3, 18, 13], 'line-opacity': 1 } },
  { id: 'base-roads', type: 'line', source: 'osm', 'source-layer': 'transportation', filter: roads,
    layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#e1e5e8', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.5, 14, 2, 18, 10], 'line-opacity': 1 } },
  { id: 'base-road-names', type: 'symbol', source: 'osm', 'source-layer': 'transportation_name', minzoom: 14, filter: roads,
    layout: { 'symbol-placement': 'line', 'symbol-spacing': 400, 'text-field': name, 'text-font': ['Noto Sans Regular'], 'text-size': 10 },
    paint: { 'text-color': '#717c80', 'text-halo-color': '#ffffff', 'text-halo-width': 1.6 } },
  { id: 'base-water-names', type: 'symbol', source: 'osm', 'source-layer': 'water_name',
    layout: { 'text-field': name, 'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-padding': 25 },
    paint: { 'text-color': '#477790', 'text-halo-color': '#e6f0f3', 'text-halo-width': 1.5 } },
];
export const basemapIds = basemapLayers.map(layer => layer.id);
export const basemapRoadIds = ['base-roads-case', 'base-roads', 'base-road-names'];
export const basemapGreeneryIds = ['base-grass', 'base-parks', 'base-woods', 'base-cemetery'];
