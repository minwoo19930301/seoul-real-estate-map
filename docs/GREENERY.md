# 녹지와 장식 나무

녹색 면은 OpenFreeMap의 OpenMapTiles 벡터 폴리곤을 사용한다. `landcover.class=wood`는 짙은 녹색, `class=grass`는 밝은 녹색이며, 잔디 중 `subclass=park/garden/recreation_ground/village_green`를 조금 더 강조한다. 묘지는 `landuse.class=cemetery`의 별도 연한 색으로 구별한다. 도로·건물·수면의 원본 도형과 표시 설정은 그대로 유지한다. `place`의 동네 이름 레이어는 제거했다.

공원·잔디를 `landuse.class=park`에서 찾던 이전 스타일은 실제 OpenMapTiles 분류를 충분히 반영하지 못했다. 일반적인 공원은 `landcover`에 포함되고, 별도의 `park` 레이어는 자연보호구역 등도 포함한다. 보호구역 경계를 모두 숲으로 칠하지 않는다. 분류 근거: [OpenMapTiles 공식 landcover/landuse 스키마](https://openmaptiles.org/schema/#landcover). 배경 타일을 받지 못하는 오프라인 환경에서는 해당 녹색 면도 제공되지 않는다.

`src/greenery.ts`의 `buildDecorativeTrees(input)`은 Three 모델용 위치만 생성하는 순수 함수다. `CityModels.setTrees(placements)`에 넘길 수 있는 `coordinate`, `height_m`, `crown_radius_m`을 반환한다. 각 결과에는 안정적인 격자 ID와 `decorative: true`가 포함된다. **개별 나무의 실제 좌표·수종·높이를 조사한 자료가 아니며, 숲 표현을 돕는 장식이다.** 연결하는 UI는 `GREENERY_DECORATION_NOTICE`를 표시해야 한다.

- `class=wood`, `natural=wood`, `landuse=forest` 폴리곤만 후보로 쓴다. 공원 경계나 잔디 면만으로 나무를 생성하지 않는다.
- 폴리곤 구멍과 바깥 경계에 수관이 걸치지 않게 제외한다. 건물 도형에는 수관 반경에 2m, 차도·보행로 중심선에는 종류별 5–25m 버퍼를 추가한다. 조회 경계에도 32m 여유를 두어 바로 바깥의 도로 중심선이 빠지는 경우에 대비한다. 이 버퍼는 도로 폭 측량값이 아니다. 실제 도로·건물의 완전성을 보증하는 기능이 아니라 입력된 제외 도형과 겹치는 모형을 걸러내는 기능이다.
- 호출자는 같은 현재 화면의 도로·건물 제외 도형이 준비된 경우에만 `exclusionsReady: true`를 전달한다. 숨기기 때문에 빈 자료, 다른 화면의 오래된 자료, 누락·표시 한도로 잘린 자료를 준비 완료로 취급하면 안 된다. `available=false`, `truncated`, `hidden_at_zoom`, `walkways_hidden_at_zoom` 또는 잘못된 도형을 발견하면 생성하지 않는다.
- 전역 32m 격자의 고정 해시를 사용한다. 입력 순서나 겹친 타일 도형 때문에 같은 자리에 나무가 중복되지 않는다. 최대 240개이며, 화면 중심 기준 최대 1.6km 범위만 후보로 확인한다. 입력 자료가 같으면 위치와 크기도 같다.
- 장식 높이는 5–9m이며 기록값이 아니다. Three 연결부는 지형에서 얻은 지면 위치만 지형 강조 배율에 맞추고, 모형 높이를 다시 곱하지 않는다. 지도 이동 후 자료 준비가 끝났을 때 갱신하며 매 프레임 전체 도형을 샘플링하지 않는다.

검증: `node --test tests/greenery.test.mjs`로 폴리곤 구멍·외곽선·도로·건물 회피, 중복 방지, 결정성, 자료 불완전 시 생성 중지, 개수 제한을 확인한다. 지도 연결과 시각 검수는 이 순수 함수 검사와 별개다.

## 제외 도형 조회와 성능

`server/greenery.py`의 `GreeneryAPI(buildings_database, roads_database).features(bbox)`는 기존 읽기 전용 API를 zoom 16으로 호출한다. 가로·세로 각각 최대 2km로 제한하며, 건물은 ID·도형만, 도로는 ID·도형·highway/category/subtype만 보낸다. 각 FC의 원본 metadata와 도형은 보존한다. `tests/test_greenery.py`가 도형 구멍/metadata 보존, 크기 제한, 미준비 DB를 새로 만들지 않는 동작을 검증한다.

2026-09-09 로컬 SQLite 표본에서 기존 전체 속성 응답을 이 형태로 줄이면 상도 2.81MB→1.07MB, 남산 1.59MB→0.63MB, 서울숲 1.65MB→0.63MB로 약 60–62% 감소했다. gzip 적용 시 각각 약 244/139/136KB지만, 이는 `gzip.compress` 측정값이며 HTTP 압축 확인과는 별개다. 기존 공간 조회를 재사용하므로 조회 CPU 약 34–61ms 자체는 유지된다. 같은 영역의 요청 캐시가 별도로 필요하다.

생성 함수의 참고 부하 측정은 **실제 제외 도형과 합성 숲 타원 경계**를 사용했다. 3천 정점 경계에서 240개 생성 중앙값은 상도 38.8ms, 남산 6.4ms, 서울숲 13.3ms였으며, 3만 정점 경계에서는 각각 150.2/35.4/81.2ms였다. 실제 배경 숲 타일이나 브라우저 프레임 속도를 측정한 결과가 아니다. 큰 경계와 반복 호출의 CPU 비용을 보여주므로, 결과 재사용과 지도 이동이 끝난 뒤의 갱신이 중요하다.
