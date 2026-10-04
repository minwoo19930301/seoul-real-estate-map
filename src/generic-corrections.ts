import type { CityModelAsset } from './city-models.ts';

/** A partition corrects source ownership without changing the archived base catalog. */
export interface GenericCorrection {
  kind?: 'metadata-only' | 'repartition';
  sourceId: string; sourceSha256: string; sourceFootprintIds: string[]; assets: CityModelAsset[];
}
const same = (a: string[], b: string[]) => a.length === b.length && [...a].sort().every((id, i) => id === [...b].sort()[i]);
const identityFields = new Set(['name', 'nameKo', 'apartmentCode', 'householdCount', 'sourceIdentity']);
function stable(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => JSON.stringify(k) + ':' + stable(v)).join(',') + '}';
  return JSON.stringify(value) ?? 'undefined';
}
function unchangedRendering(original: CityModelAsset, part: CityModelAsset) {
  const preserved = (asset: CityModelAsset) => Object.fromEntries(Object.entries(asset).filter(([key]) => !identityFields.has(key)));
  return stable(preserved(original)) === stable(preserved(part));
}
export function applyGenericCorrections(assets: CityModelAsset[], matches: Record<string, string[]>, raw: unknown) {
  const document = raw as { version?: number; corrections?: GenericCorrection[] };
  if (document?.version !== 1 || !Array.isArray(document.corrections)) throw new Error('Invalid generic correction document');
  const byId = new Map(assets.map(a => [a.id, a]));
  const effectiveMatches = { ...matches };
  const touched = new Set<string>();
  const ancestry = new Map<string, string[]>();
  for (const correction of document.corrections) {
    const original = byId.get(correction.sourceId);
    const repartition = correction.kind === 'repartition';
    if (!original || original.quality || (repartition ? !touched.has(original.id) || !original.genericCorrection : touched.has(original.id)) || original.sha256 !== correction.sourceSha256
        || !Array.isArray(correction.sourceFootprintIds) || !same(effectiveMatches[original.id] ?? [], correction.sourceFootprintIds)
        || !Array.isArray(correction.assets)) throw new Error('Generic correction source mismatch');
    if (correction.kind === 'metadata-only') {
      const part = correction.assets[0];
      if (correction.assets.length !== 1 || correction.sourceFootprintIds.length !== 1 || !part
          || part.id !== original.id || !Array.isArray(part.footprintIds) || !same(part.footprintIds, correction.sourceFootprintIds)
          || typeof part.nameKo !== 'string' || !part.nameKo.trim() || !unchangedRendering(original, part)) {
        throw new Error('Metadata-only correction must preserve the exact singleton asset and rendering properties');
      }
      byId.set(original.id, part);
      touched.add(original.id);
      continue;
    }
    if (correction.kind !== undefined && !repartition || correction.assets.length < 2) throw new Error('Generic correction source mismatch');
    const partitionIds: string[] = [], footprints: string[] = [];
    for (const part of correction.assets) {
      if (!part || !/^[a-z0-9_-]+$/.test(part.id) || part.quality || part.supersedes?.length
          || !/^generic-corrections\/[a-z0-9_-]+\.glb$/.test(part.model) || !/^[a-f0-9]{64}$/.test(part.sha256)
          || !Array.isArray(part.footprintIds) || !part.footprintIds.length
          || part.coordinate?.lon !== original.coordinate.lon || part.coordinate?.lat !== original.coordinate.lat
          || part.yawDegFromEast !== original.yawDegFromEast
          || !Array.isArray(part.geoBounds) || part.geoBounds.length !== 4 || !part.geoBounds.every(Number.isFinite)
          || part.geoBounds[0] >= part.geoBounds[2] || part.geoBounds[1] >= part.geoBounds[3]
          || !Array.isArray(part.dimensions) || part.dimensions.length !== 3 || !part.dimensions.every(n => Number.isFinite(n) && n > 0)
          || repartition && part.id === original.id
          || (part.id !== original.id && byId.has(part.id)) || touched.has(part.id)) throw new Error('Invalid generic correction partition');
      partitionIds.push(part.id); footprints.push(...part.footprintIds);
    }
    if (new Set(partitionIds).size !== partitionIds.length
        || new Set(footprints).size !== footprints.length || !same(footprints, correction.sourceFootprintIds)) throw new Error('Generic correction must exactly partition original ownership');
    // Remove the compound only after every source footprint has a unique replacement.
    if (!partitionIds.includes(original.id)) { byId.delete(original.id); delete effectiveMatches[original.id]; }
    const ancestors = [...new Set([original.id, ...(ancestry.get(original.id) ?? [])])];
    touched.add(original.id);
    for (const part of correction.assets) { byId.set(part.id, part); effectiveMatches[part.id] = [...part.footprintIds!]; touched.add(part.id); ancestry.set(part.id, ancestors); }
  }
  // Annotate only the returned runtime copies, after validating every historical record.
  // Public correction objects remain byte-for-byte untouched, including metadata-only records.
  const current = [...byId.values()].map(asset => asset.genericCorrection && ancestry.get(asset.id)?.some(id => id !== asset.genericCorrection!.sourceId)
    ? { ...asset, genericCorrection: { ...asset.genericCorrection, ancestorSourceIds: [...ancestry.get(asset.id)!] } }
    : asset);
  return { assets: current, matches: effectiveMatches };
}
