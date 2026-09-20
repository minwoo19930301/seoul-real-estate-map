import type { CityModelAsset } from './city-models.ts';

export interface ReferencePlace {
  id: string; name: string; subtitle: string;
  center: [number, number]; zoom: number; source_url: string;
  household_count?: number;
  supersedesPlaceIds?: string[];
}
export interface ReferenceManifest {
  version: 1; assets: CityModelAsset[]; places: ReferencePlace[];
  preservedLandmarkFootprints?: Record<string, string[]>;
}

export function referenceManifest(value: unknown, preserved: CityModelAsset[]): ReferenceManifest {
  const data = value as ReferenceManifest;
  if (data?.version !== 1 || !Array.isArray(data.assets) || data.assets.length > 5000
    || !Array.isArray(data.places)) throw Error('잘못된 개별 건물 모델 목록입니다.');
  const ids = new Set(preserved.map(asset => asset.id));
  if (data.preservedLandmarkFootprints !== undefined) {
    if (!data.preservedLandmarkFootprints || typeof data.preservedLandmarkFootprints !== 'object'
      || Array.isArray(data.preservedLandmarkFootprints)
      || Object.entries(data.preservedLandmarkFootprints).some(([id, footprints]) => !ids.has(id)
        || !Array.isArray(footprints) || footprints.some(fid => typeof fid !== 'string' || !fid))) {
      throw Error('잘못된 기존 랜드마크 건물 목록입니다.');
    }
  }
  for (const asset of data.assets) {
    if (!asset || typeof asset.id !== 'string' || !/^[a-z0-9_-]+$/.test(asset.id) || ids.has(asset.id)
      || !/^[a-z0-9_-]+(?:\/[a-z0-9_-]+)*\.glb$/.test(asset.model)
      || !/^[a-f0-9]{64}$/.test(asset.sha256) || asset.quality !== 'reference'
      || typeof asset.nameKo !== 'string' || !asset.nameKo
      || !Array.isArray(asset.dimensions) || asset.dimensions.length !== 3 || !asset.dimensions.every(n => Number.isFinite(n) && n > 0)
      || !asset.coordinate || !Number.isFinite(asset.coordinate.lon) || !Number.isFinite(asset.coordinate.lat)
      || Math.abs(asset.coordinate.lon) > 180 || Math.abs(asset.coordinate.lat) > 90 || !Number.isFinite(asset.yawDegFromEast)
      || asset.groundOffsetM !== undefined && (!Number.isFinite(asset.groundOffsetM) || Math.abs(asset.groundOffsetM) > 100)
      || !Array.isArray(asset.footprintIds) || asset.footprintIds.some(id => typeof id !== 'string' || !id)
      || !Array.isArray(asset.supersedes) || asset.supersedes.some(id => typeof id !== 'string' || !id || id === asset.id)) {
      throw Error('개별 건물 모델의 위치 또는 출처가 올바르지 않습니다.');
    }
    ids.add(asset.id);
  }
  const generations = new Map(data.assets.map(asset => [asset.id, asset]));
  const incoming = new Map(data.assets.map(asset => [asset.id, 0]));
  for (const asset of data.assets) {
    for (const id of asset.supersedes!) {
      if (incoming.has(id)) incoming.set(id, incoming.get(id)! + 1);
    }
  }
  const pending = data.assets.filter(asset => incoming.get(asset.id) === 0).map(asset => asset.id);
  for (let index = 0; index < pending.length; index++) {
    for (const id of generations.get(pending[index])!.supersedes!) {
      if (!incoming.has(id)) continue;
      const remaining = incoming.get(id)! - 1;
      incoming.set(id, remaining);
      if (remaining === 0) pending.push(id);
    }
  }
  if (pending.length !== data.assets.length) throw Error('개별 모델 사이의 대체 관계가 잘못됐습니다.');
  for (const place of data.places) {
    if (!place || typeof place.id !== 'string' || typeof place.name !== 'string' || typeof place.subtitle !== 'string'
      || !Array.isArray(place.center) || place.center.length !== 2 || !place.center.every(Number.isFinite)
      || Math.abs(place.center[0]) > 180 || Math.abs(place.center[1]) > 90 || !Number.isFinite(place.zoom)
      || place.zoom < 0 || place.zoom > 22 || typeof place.source_url !== 'string') throw Error('잘못된 개별 건물 검색 위치입니다.');
    if (place.supersedesPlaceIds !== undefined && (!Array.isArray(place.supersedesPlaceIds)
      || place.supersedesPlaceIds.some(id => typeof id !== 'string' || !id))) throw Error('잘못된 이전 장소 목록입니다.');
  }
  return data;
}
