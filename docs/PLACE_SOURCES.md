# 서울 장소 검색과 지도 표식

2026-09-09 공식 공동주택 자료를 추가하고 2026-09-10 K-apt 단지코드 일치 위치로 보완해 현재 검색은 43,809개다. [400세대 이상 아파트 연결과 검사](APARTMENTS_400.md)에 공식 원본 2,887개, 대상 1,363개, 위치 연결 1,344개와 나머지 기록을 설명한다. 아래 41,902개와 검색 표는 공식 자료 추가 전 OSM/Overture 기준 검사 결과다. 현재 수량은 `/api/places/meta`를 확인한다.

로컬 `data/places.sqlite`에서 검색한다. 사용자가 검색하거나 지도를 움직일 때 외부 지오코딩 API를 호출하지 않는다. 검색 이름과 위치는 보관한 OSM/Overture 원본에서 읽는다. 위치를 임의로 입력하거나 상호명으로 주소를 추측하지 않는다.

## 데이터와 범위

1. 기존 `data/buildings.sqlite`의 이름 있는 **부모 건물**만 검색에 넣는다. `building_part`는 중복 검색 대상에서 제외한다. 원본 35,747개 중 대표점이 서울 경계 밖에 있는 2개를 제외한 35,745개다. 원본 건물 ID를 `building_id`로 보존해 건물 상세 API와 연결한다. 원본 도형의 Shapely `representative_point()`는 도형 안에 있는 위치이며, 출입구·주소점·측량된 POI 좌표가 아니다. `location_method=inside_source_footprint`로 밝힌다. 원본 릴리스는 `2026-08-19.0`이다. [Overture 건물 설명](https://docs.overturemaps.org/guides/buildings/), [출처 표기](https://docs.overturemaps.org/attribution/).
2. 기존 `data/building-source/districts.geojson`의 서울 25개 자치구 이름·경계를 사용한다. 구 이름과 원본 별칭을 검색하며, 경계 내부 대표점으로 이동한다. 실제 행정기관의 소재지를 뜻하지 않는다. 이 파일의 OSM 기반 경계는 **공식 행정기관 공표 경계라는 주장이 아니다**. [Overture 행정구역 설명](https://docs.overturemaps.org/guides/divisions/).
3. 도로 수집과 **하나의 Overpass 쿼리를 공유**해 철도·지하철역, 다리, 이름 있는 교차로, 이름 있는 주거 영역, 동네·행정구역 원본을 받는다. 요청 범위는 `(37.413,126.734,37.716,127.270)`이며, 결과의 좌표/대표점이 보관한 서울 경계 안에 있을 때만 넣는다. 정확한 쿼리는 `data/sources/osm-roads-2026-09-08/query.overpassql`, 응답 캐시는 같은 폴더 `overpass.json`이다. 원본 태그 누락·현실과의 시점 차이가 있으므로 서울의 모든 역·교차로·단지를 수록했다는 의미가 아니다. [Overpass 공개 조회 설명](https://wiki.openstreetmap.org/wiki/Overpass_API).

2026-09-08 수집 결과는 **41,902개**다: 건물 35,745, 주거 영역 3,371, 역 311, 다리 552, 교차로 775, 지역 1,148개(서울 25개 구 포함). 이 수량은 중요 시설만의 공식 개수가 아니라 선택한 원본 태그에 해당하는 검색/표식 수다. SQLite는 26,288,128 bytes다.

첫 `https://overpass-api.de/api/interpreter` 요청은 HTTP 504로 실패했고, 동일 쿼리의 `https://overpass.kumi.systems/api/interpreter` 요청은 정상 완료했다. 원본은 155,978,047 bytes, 219,052개 elements, SHA-256 `25f8506f75becdb6b99b1497d24f8b17123a88fdeb7b60210fd191e4b0821978`이다. **응답의 OSM 기준 시각은 `2026-06-01T08:52:28Z`이며, 9월 8일 최신 현황이라는 뜻이 아니다.** 수집 경로는 원본 옆 `manifest.json`에 남긴다. 서울 밖 대표점 5,050개 제외, 서울 안 선택 객체 6,787개에서 같은 표식 묶음과 별도 25개 구 중복 제거 후 OSM 표식 6,132개를 보존했다.

최종 수량, 원본 응답의 OSM 시각, 파일 SHA-256, 누적 제외/중복 수량은 `/api/places/meta`에 보관한다. 빌더를 OSM 파일 없이 실행한 경우 `osm_available=false`이며 건물과 25개 구만 검색된다.

## 분류와 좌표 해석

| kind | 원본 조건 | 위치/표시 |
|---|---|---|
| `station` | `railway=station/halt` 및 이름 | 역 이름과 원본 별칭. `강남역`처럼 역 접미사를 붙인 검색도 허용하지만 원본 표시 이름은 바꾸지 않는다. 출입구·승강장은 모으지 않는다. |
| `bridge` | `man_made=bridge`, `bridge:name`, 또는 bridge 태그와 다리 이름 | 단순히 교량 위를 지나는 ‘○○대로’를 다리 이름으로 사용하지 않는다. |
| `junction` | 이름 있는 junction 노드, 또는 사거리/삼거리/오거리/육거리/교차로 이름 노드 | 원본 노드 좌표. 모든 신호등을 교차로 이름으로 만들지 않는다. 사거리 이름이 붙은 버스 정류장·public_transport 승강장/정차점은 제외한다. |
| `residential` | 이름 있는 `landuse=residential` 영역 | 원본 `residential=apartments`일 때만 아파트 주거 영역이라고 설명한다. 그 외에는 이름 있는 주거 영역이다. 단지 법적 경계나 주상복합 분류를 보장하지 않는다. |
| `neighborhood` | 원본 place/administrative 이름, 기존 25개 구 | 지역 위치를 찾는 용도. 법정동 전체 목록이나 관공서 좌표가 아니다. |
| `building` | 기존 도형에 실제 이름이 있는 부모 건물 | ‘101동’ 등 개별 건물은 전체 아파트 단지로 합치지 않는다. 원본 아파트 분류는 검색 순위에만 반영하며 이름으로 용도를 추정하지 않는다. |

OSM node는 `location_method=osm_node`로 원본 좌표를 보존한다. `out center`의 way/relation은 원본 bounding box의 중점(`osm_bounds_center`)이며 도형 내부에 있다는 보장은 없다. 도로 선을 재사용한 다리는 원본 선 길이의 중간 위치(`osm_line_midpoint`)다. 어느 경우도 출입구 좌표로 표시하지 않는다.

동일 종류·동일 정규화 이름의 역 500m 이내, 다리 2km 이내, 교차로 75m 이내, 지역 이름 250m 이내 중복은 표식 하나로 묶는다. 첫 원본 위치를 그대로 유지하고 관련 원본 ID들은 SQLite `source_ids`에 모두 남긴다. 역 노드·전용 다리 도형을 우선한다. 이것은 UI 표식 중복 정리이며 새로운 정식 시설 식별자를 만드는 작업은 아니다. 이름 있는 주거 영역과 개별 건물은 이 규칙으로 합치지 않는다.

## API 연결

`server.places.PlacesAPI(path)`는 다음 메서드를 제공한다. HTTP 경로는 `server/app.py`에서 연결한다.

- `.search(query, limit=12)` → `{results:[{id,name,subtitle,kind,center:[lon,lat],zoom,priority,source_url,location_method,building_id,district_name}],metadata}`. 빈 검색은 빈 결과다. 이름·원본 별칭·구와 이름을 합친 검색을 지원하며, 완전 일치를 우선하고, 나머지는 장소 종류의 표시 우선순위 → 접두/부분 일치 순이다. 따라서 `헬리오시티` 검색에서 단지인 `송파헬리오시티`가 개별 건물 `헬리오시티 경로당`보다 앞선다. 입력은 100자, limit은 1–50이다.
- `.features(bbox, zoom=15, kinds='station,bridge,junction,residential')` → GeoJSON Point FeatureCollection. 최대 300개이며 잘리면 `metadata.truncated=true`. `building`은 명시적으로 요청하고 줌 16 이상일 때만 나온다. 기본 표식과 건물 검색을 분리한다.
- `.meta()` → 출처, 수량, 범위, 한도. DB가 없으면 `available=false`를 반환한다.

잘못된 bbox/zoom/kinds/limit은 `ValueError`다. 프론트엔드가 임의 이름을 SQL로 보내지 않도록 별도 조건을 요구하지 않으며, 서버는 바인딩된 SQL 파라미터와 정규화된 검색문만 사용한다. SQLite RTree로 현재 화면 위치를 제한하고 실제 좌표로 한 번 더 검사한다.

## 재생성 및 검사

```sh
.venv/bin/python scripts/build_places.py --overpass data/sources/osm-roads-2026-09-08/overpass.json --overpass-endpoint https://overpass.kumi.systems/api/interpreter
.venv/bin/python -m unittest tests.test_places -v
```

빌더는 입력 캐시만 읽으며 네트워크를 사용하지 않는다. 새 임시 SQLite를 만들고 무결성 검사 후 파일을 원자적으로 교체한다. Overpass 응답에 오류/부분 응답 가능성을 뜻하는 `remark`가 있으면 거부하고 기존 DB를 보존한다. 합성 fixture 테스트는 검색 별칭, 원본 ID, 중복 정리, 서울 밖 제외, 건물/단지 구분, 입력 검증, 부분 응답으로 인한 기존 DB 손실 방지를 확인한다. 합성 fixture를 실제 지도 자료로 쓰지 않는다.

## 실제 검색 검산

다음 11개 질의의 첫 결과가 모두 원본 `landuse=residential` 영역인지, 원본 `center`와 좌표가 정확히 일치하는지 검사했다. 각 질의에 임의의 공백을 넣어도 같은 ID가 나온다. `타워팰리스 B동` 같은 정확한 개별 건물 검색은 여전히 해당 건물이 우선이다. 표의 링크는 검산한 실제 OSM 객체다.

| 검색 | 실제 원본 이름과 객체 | lon, lat |
|---|---|---|
| 헬리오시티 | [송파헬리오시티](https://www.openstreetmap.org/way/474304292) | 127.1074238, 37.4974045 |
| 파크리오 | [잠실 파크리오](https://www.openstreetmap.org/way/471733248) | 127.109961, 37.5209363 |
| 잠실엘스 | [잠실 엘스](https://www.openstreetmap.org/relation/6114967) | 127.0814378, 37.5141602 |
| 리센츠 | [잠실 리센츠](https://www.openstreetmap.org/relation/6114968) | 127.088489, 37.5143342 |
| 반포자이 | [반포자이아파트](https://www.openstreetmap.org/way/165196918) | 127.0136188, 37.5063094 |
| 래미안원베일리 | [래미안원베일리아파트](https://www.openstreetmap.org/way/412953594) | 126.9981259, 37.5067988 |
| 타워팰리스 | [삼성타워팰리스1차](https://www.openstreetmap.org/way/443030426) | 127.054345, 37.4882154 |
| 트리마제 | [서울숲트리마제](https://www.openstreetmap.org/way/601252646) | 127.0451209, 37.5389143 |
| 갤러리아포레 | [갤러리아포레](https://www.openstreetmap.org/way/671194792) | 127.0424006, 37.5457939 |
| 아크로서울포레스트 | [아크로서울포레스트](https://www.openstreetmap.org/way/671194791) | 127.0438371, 37.5444332 |
| 한남더힐 | [한남더힐아파트](https://www.openstreetmap.org/way/228802387) | 127.0093887, 37.5369684 |

추가로 `강남역` → `강남` 역, `잠실역` → `잠실` 역, `한강대교`·`성수대교` → 해당 다리, `성수동` → `성수동1가/2가`, `성동구` → 해당 구가 검색됨을 확인했다. `도산대로사거리`는 이 캐시에 결과가 없었다. 없는 이름을 새로 만들어 추가하지 않았다.

검증: `tests.test_places` **9개 통과**. SQLite ID 전수 고유성, RTree 행수와 실제행수 일치, `integrity_check=ok`, 전 서울 줌 15 조회 300개 상한과 `truncated=true`도 확인했다.

## 이용 조건

OSM 자료에는 [ODbL과 OpenStreetMap 출처 표기 조건](https://www.openstreetmap.org/copyright)이 적용된다. 기존 Overture 자료의 원본 출처 표기는 `data/building-source/ATTRIBUTION.md`와 건물 메타데이터를 함께 유지한다. 이번 검색 인덱스는 무료 공개 원본과 로컬 캐시를 사용한다. API 키·BrightData·로그인·유료 지오코딩 호출은 사용하지 않는다. 공개 Overpass 서버는 무한 재시도하거나 검색마다 다시 호출하지 않는다.
