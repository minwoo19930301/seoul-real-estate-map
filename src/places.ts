export type Place = { name: string; subtitle: string; center: [number, number]; zoom: number };

// Curated navigation anchors, not a general address/geocoding database.
export const places: Place[] = [
  { name: '성수동', subtitle: '한강 옆 낮은 생활권', center: [127.049, 37.544], zoom: 14.4 },
  { name: '대치동', subtitle: '평지와 완만한 지형', center: [127.060, 37.495], zoom: 14.3 },
  { name: '상도동', subtitle: '언덕을 따라 이어지는 주택가', center: [126.948, 37.501], zoom: 15.1 },
  { name: '신림동', subtitle: '관악산 아래 생활권', center: [126.936, 37.481], zoom: 14.0 },
  { name: '해방촌', subtitle: '남산 남쪽 주택가', center: [126.987, 37.543], zoom: 15.0 },
  { name: '이태원', subtitle: '용산의 언덕과 골목', center: [126.994, 37.534], zoom: 14.5 },
  { name: '연희동', subtitle: '서대문 주거 지역', center: [126.930, 37.573], zoom: 14.2 },
  { name: '한남동', subtitle: '한강과 남산 사이', center: [127.006, 37.535], zoom: 14.3 },
  { name: '창신동', subtitle: '종로 동쪽 언덕', center: [127.012, 37.575], zoom: 14.5 },
  { name: '불광동', subtitle: '북한산 아래 생활권', center: [126.930, 37.615], zoom: 14.2 },
  { name: '목동', subtitle: '안양천 옆 주거 지역', center: [126.876, 37.535], zoom: 14.0 },
  { name: '잠실', subtitle: '한강 남쪽 평지', center: [127.092, 37.511], zoom: 14.0 },
  { name: '서울시청', subtitle: '도심', center: [126.978, 37.566], zoom: 14.2 },
];

export function searchPlaces(query: string): Place[] {
  const normalized = query.trim().replace(/\s+/g, '');
  if (!normalized) return [];
  const coordinates = query.trim().split(/[,\s]+/).map(Number);
  if (coordinates.length === 2 && coordinates.every(Number.isFinite)) {
    let [a, b] = coordinates;
    const [lon, lat] = a > 90 ? [a, b] : [b, a];
    if (lon >= 126.74 && lon <= 127.22 && lat >= 37.39 && lat <= 37.76) {
      return [{ name: '입력한 좌표', subtitle: `${lat.toFixed(5)}, ${lon.toFixed(5)}`, center: [lon, lat], zoom: 15 }];
    }
  }
  return places.filter(place => `${place.name}${place.subtitle}`.includes(normalized));
}
