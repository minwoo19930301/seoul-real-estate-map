# 서울 도로·보행로 원본과 표시 기준

이 지도는 OpenStreetMap(OSM)의 실제 way 좌표를 사용합니다. 차도 중심선과 별도로 등록된 보행 선형을 겹쳐 표시하며, 도로 폭이나 보도 위치를 임의 계산하지 않습니다. OSM에 없는 길을 생성하지도 않습니다. 전 서울 범위를 요청했더라도 OSM의 현장 수록 완전성까지 보장하는 것은 아닙니다.

## 분류

| 지도 분류 | 원본 조건 | 주의점 |
|---|---|---|
| 차도 | motorway, trunk, primary, secondary, tertiary 및 link, residential, unclassified, living_street, service, road, track | 중심선이며 실제 도로 경계·폭이 아님. 생활도로와 임도도 포함 |
| 별도 보도 | highway=footway + footway=sidewalk | 별도 way에 기록된 경우만 해당 |
| 횡단보도 | highway=footway + footway=crossing | 따로 기록된 횡단 선형 |
| 일반 보행로 | highway=footway, pedestrian, path | path는 산길·공용길일 수도 있음 |
| 자전거·보행 겸용 | highway=cycleway + foot=yes/designated/permissive | 보행 허용 태그가 있는 자전거길 |
| 계단 | highway=steps | 갈색 짧은 점선으로 구분 |

차도의 `sidewalk=both/left/right`나 `sidewalk:left/right`는 원본 속성으로 남기지만 보도선을 새로 만들지 않습니다. `area=yes`인 광장·보행 면 도형은 경계선을 보행 경로처럼 오해하지 않도록 이 선 레이어에서 제외합니다. 건설 예정·공사 중 highway나 보행 허용이 없는 cycleway도 제외합니다. 도형의 좌표·굴곡·순서를 보존합니다.

OSM의 `access`, `foot`, `surface`, `wheelchair`, `incline`, `bridge`, `tunnel`, `layer` 태그를 API에 함께 제공합니다. 접근 제한이 있는 일반 보행선은 낮은 채도 색으로 구분합니다. 지도에 보인다고 통행 가능·무장애·안전한 경로라는 뜻은 아닙니다. 교량·터널 태그는 원본 속성이며, 도로의 실제 교량 높이·지하 깊이를 입체 생성하지 않습니다.

## 취득·재생성

원본 요청문과 응답은 `data/sources/osm-roads-2026-09-08/`에 보존합니다. 같은 요청에 지하철역·대교·이름 있는 교차로·주거지역·행정구역 POI를 포함하여 장소 검색 모듈과 캐시를 공유합니다. 익명 공개 Overpass 조회를 사용하며 키·유료 프록시는 필요 없습니다. 대량 반복 조회나 사용 제한 우회는 하지 않습니다.

2026-09-08 수신에 성공했습니다. 첫 `overpass-api.de` 서버는 HTTP 504를 반환했고, 이후 `overpass.kumi.systems` 요청 한 번이 약 188초 후 정상 완료됐습니다. 응답은 155,978,047 bytes, 219,052개 OSM element이며 오류 `remark`가 없습니다. **원본 OSM 기준시각은 `2026-06-01T08:52:28Z`입니다.** 다운로드 날짜를 최신 지도 갱신일로 해석하면 안 됩니다. 실제 사용한 요청문·endpoint·응답 SHA-256은 [manifest](../data/sources/osm-roads-2026-09-08/manifest.json)에 기록했습니다.

원본 highway way 207,864개 중 서울 행정경계와 교차하는 지원 선형 119,917개를 수록했습니다. 서울 밖 83,331개, 지원 대상이 아닌 highway 3,577개, 면 도형 1,039개를 제외했습니다. 임의 생활권 샘플이 아니라 전 서울 bbox를 조회한 결과이지만, 전체 실재 도로·보도의 완전한 목록이라는 뜻은 아닙니다.

| 수록 항목 | 선형 수 |
|---|---:|
| 차도 | 79,812 |
| 보행로 합계 | 37,071 |
| 그중 별도 보도 | 8,343 |
| 그중 횡단보도 | 7,156 |
| 계단 | 3,034 |

원본 좌표는 725,816개이며 DB는 53,907,456 bytes입니다. 차도 중 보도 관련 태그를 가진 1,086개는 차도 한 선 그대로 남겼습니다. 보행로 합계에는 일반 footway 14,582개, pedestrian 588개, path 4,354개, 보행 허용 cycleway 2,048개도 포함됩니다. way 개수는 지리적으로 이어진 한 도로의 개수와 다릅니다.

```sh
curl -L -o data/sources/osm-roads-2026-09-08/overpass.json --fail \
  --connect-timeout 20 --max-time 240 \
  --data-urlencode data@data/sources/osm-roads-2026-09-08/query.overpassql \
  https://overpass.kumi.systems/api/interpreter
.venv/bin/python scripts/build_roads.py \
  --source data/sources/osm-roads-2026-09-08/overpass.json
```

빌더는 오류 remark가 있는 부분 응답, 빠진 geometry, 유효하지 않은 좌표를 거부합니다. 임시 SQLite에 저장한 뒤 성공한 경우에만 `data/roads.sqlite`를 원자적으로 교체합니다. POI 출력 때문에 같은 OSM way가 중복되면 실제 좌표를 가진 항목을 보존합니다. 서울 행정경계와 교차하는 선만 수록하며 경계를 넘는 원본 way는 전체를 유지합니다.

## API와 성능

`GET /api/roads/meta`는 원본 기준시각, SHA-256, 분류별 수, 원본 좌표 수, 제외 이유, 공간 범위와 라이선스를 제공합니다. `GET /api/roads?bbox=west,south,east,north&zoom=15`는 GeoJSON FeatureCollection과 표시 제한 metadata를 제공합니다.

- zoom 11부터 주요 도로, 13부터 생활·접근 도로, 14부터 보행로·계단을 조회합니다. 보행선은 15 이상에서 더 뚜렷해집니다.
- 최대 5,000개 선·100,000개 원본 좌표입니다. 후보를 RTree로 찾고 실제 선형 교차를 다시 확인합니다.
- 8×8 화면 격자와 분류를 순환하며 선택하므로 수집 순서상 첫 지역이 한도를 독점하지 않습니다. 한도 도달 시 `truncated=true`이며 확대 안내를 표시합니다.
- API 도형은 자르거나 단순화하지 않습니다. 선 폭과 점선 간격은 지도의 표시 스타일이며 측정 폭이 아닙니다.
- 토글을 전부 끄면 이전 요청을 취소하고 화면 자료를 비웁니다. 이전 화면의 늦은 응답은 현재 화면을 덮어쓰지 않습니다.

검증: `.venv/bin/python -m unittest tests.test_roads -v`의 7개 테스트가 통과했습니다. 별도 보도 조건, 원본 좌표 보존, 동일 way 중복, 확대 단계, bbox 오탐 제거, 개수·좌표 한도, 서울 밖 제외·경계 횡단 원본 보존, 오류 시 기존 DB 보존, 잘못된 입력·없는 DB를 확인합니다. TypeScript 검사와 Vite production build도 통과했습니다.

실제 DB에서 상도 `126.935,37.490,126.965,37.510`/z15.3 조회는 1,126선(차도 874·보행 201·계단 51), 시청 `126.966,37.556,126.987,37.574`/z15는 1,436선을 반환했으며 모두 잘리지 않았습니다. 이 Mac에서 JSON 직렬화를 포함한 조회는 각각 약 21/24ms였습니다. 전 서울/z14는 5,000선 제한과 `truncated=true`를 반환했습니다. 성능 수치는 특정 실행의 관찰값이며 [원본 조회 결과](../data/sources/osm-roads-2026-09-08/viewport-checks.json)에 저장했습니다.

실제 DB의 119,917개 geometry를 원본 OSM way ID로 다시 찾아 모든 좌표 725,816개와 순서를 직접 비교한 결과 **불일치 0건**, SQLite integrity check는 `ok`였습니다. [전체 좌표 비교 결과](../data/sources/osm-roads-2026-09-08/geometry-audit.json)를 보존했습니다. 이는 수록한 선형이 원본과 일치한다는 증거이며 OSM 밖의 미등록 도로 존재 여부를 검증한 것은 아닙니다.

## 출처·라이선스

© OpenStreetMap contributors. 데이터는 [Open Database License](https://www.openstreetmap.org/copyright)에 따라 사용합니다. 지도 자체·개별 렌더러의 조건과 데이터 라이선스는 별개입니다. 이 로컬 파생 DB를 외부 배포할 때는 OSM 표시와 해당 데이터베이스 공유 조건을 유지해야 합니다.

분류 기준은 OSM의 [footway 키 문서](https://wiki.openstreetmap.org/wiki/Key:footway), 요청 형식은 [Overpass QL 공식 프로젝트 문서](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)를 참고했습니다. 이 자료는 이용자 기여 지도이며 현장 측량 원본이나 최신 통행 안내로 표시하지 않습니다.
