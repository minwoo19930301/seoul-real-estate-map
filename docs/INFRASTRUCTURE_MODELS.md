# 서울 인프라 모델

기존 1,160개 자산과 건물 매칭을 그대로 보존하고 390개 모델을 추가했습니다. 총 1,550개입니다.

| 추가 범위 | 수량 | 근거 |
| --- | ---: | --- |
| 초·중·고 건물 | 224 | 이름이 붙은 원본 건물 윤곽과 ID |
| 구청·주민센터 등 행정기관 | 140 | 원본 건물 ID와 구 경계 확인 |
| 한강 교량 | 26 | OSM 상판 윤곽 또는 폭 추정을 명시한 중심선 |
| 대로 노면 | 6,894개 구간 · 도로명 437개 | OSM 중심선 |
| 철도 위치 | 311개 기록 | 원본 역 좌표 |
| 역 주변 버스 정류장 | 51개 노드 | 실제 OSM 정류장 좌표 |

학교·공공청사는 25개 구에 걸쳐 추가했습니다. 전체 시설 전수조사는 아니며, 캠퍼스 전체가 아니라 이름과 원본 ID를 확인할 수 있는 건물만 포함합니다. 교구청은 행정 구청이 아니므로 제외합니다. 기존 모델과 같은 건물 ID를 다시 소유하지 않습니다.

## 실제 자료와 추정의 경계

건물의 위치와 외곽선은 보유한 원본 자료를 따릅니다. 높이는 자료에 있으면 그 값을 쓰고, 없으면 층수 × 3.05m, 층수마저 없으면 3층을 가정합니다. 창문·창틀·층 사이 띠·벽돌 기단·난간·현관 캐노피를 추가했지만, 색상과 창 배치·현관 위치는 사진 측량으로 확인한 값이 아닙니다. 개별 건물의 원본 높이 유무와 추정 방식은 [PUBLIC_FACILITY_PROVENANCE.json](PUBLIC_FACILITY_PROVENANCE.json)에 기록합니다.

대교는 실제 평면 윤곽에 맞춰 상판·난간·교각을 생성합니다. 반포/잠수교는 상하 층을 구분하고, 한강·서강·동작대교의 아치, 성수·성산대교 등의 트러스, 올림픽·월드컵대교의 주탑과 케이블 형태를 반영합니다. 일반 상판 높이는 바닥 기준 18m, 반포는 24m, 잠수는 5m로 **추정**했으며 교각 위치도 일정 간격의 재현입니다. 모델은 앵커 지점의 지형 높이에 놓이므로 전 구간의 수면·접속로 고도와 정확히 맞는 토목 설계 모델은 아닙니다.

올림픽대교 주탑 88m, 월드컵대교 주탑 100m라는 공개 수치를 참고했지만 원 자료의 수직 기준면과 현장 치수 전체는 확보하지 못했습니다. 주탑 비율·위치·케이블·횃불 장식은 단순화한 재현입니다. 참고: [서울시 올림픽대교](https://culture.seoul.go.kr/night/sub/viewSpot/view.do?viewId=69), [서울시 월드컵대교](https://kids.seoul.go.kr/article/articleView.do?p_articleSn=801474), [서울시 교량 소개](https://news.seoul.go.kr/safe/archives/53221).

강동·방화대교는 닫힌 상판 윤곽 대신 원본 도로 중심선을 미터 좌표계에서 폭만큼 확장했습니다. [bridge-outlines.geojson](../public/bridge-outlines.geojson)의 `geometrySource`·`widthBasis`와 [BRIDGE_MODEL_PROVENANCE.json](BRIDGE_MODEL_PROVENANCE.json)이 이를 구분합니다. 다른 교량은 원본 폐합 윤곽을 사용합니다.

대로는 검은색에 가까운 노면으로 표시합니다. 원본 폭 태그 49개, 차선 수로 계산한 폭 2,878개, 도로 등급으로 추정한 폭 3,967개입니다. 노폭은 5–45m로 제한하고 교량·터널 구간은 제외합니다. 차선 표시는 시각적 참고이며 연석 위치를 실측한 폴리곤은 아닙니다. [AVENUE_COVERAGE.json](AVENUE_COVERAGE.json)

교통 표시는 별도 [TRANSIT_COVERAGE.md](TRANSIT_COVERAGE.md)에 범위와 한계를 기록했습니다. 정류장 좌표를 역 중심점으로 대신 만들지 않습니다.

## 생성과 재현

공공시설 및 교량 GLB 생성기는 기존 파일 덮어쓰기를 거부합니다. 아래 GLB 생성 명령은 추가분이 없는 기존 1,160개 기준 체크아웃 또는 별도 출력 사본에서 실행합니다. 후보 선정, 도로·교통 생성 및 검증은 반복 실행할 수 있습니다. 원본 SQLite·경계·Overpass·OSM 다운로드 캐시는 Git에 포함하지 않습니다.

```sh
.venv/bin/python scripts/select_public_facilities.py --boundaries data/building-source/districts.geojson
.venv/bin/python scripts/build_district_landmarks.py --append-candidates docs/public-facility-candidates.json --expected-count 364 --provenance docs/PUBLIC_FACILITY_PROVENANCE.json
.venv/bin/python scripts/fetch_bridge_outlines.py
.venv/bin/python scripts/build_bridge_models.py
.venv/bin/python scripts/build_avenues.py
.venv/bin/python scripts/build_transit.py
node scripts/verify_district_landmarks.mjs
node --test tests/*.test.mjs
npm run build
```

런타임은 동시에 4개 파일만 내려받고 가까운 모델 32개, GPU 캐시 48개로 제한합니다. 기울어진 지도에서도 화면 중심에 가까운 모델을 우선합니다. 정지 화면에서 별도의 상시 애니메이션 루프를 만들지 않습니다. 건물·교량 모형, 학교·공공기관, 대교, 차도, 역, 버스 정류장을 켜고 끌 수 있습니다.

검증 결과는 [LANDMARK_ASSET_VALIDATION.json](LANDMARK_ASSET_VALIDATION.json), [infrastructure-browser-check.json](infrastructure-browser-check.json), [landmark-validation-summary.json](landmark-validation-summary.json)에 기록합니다. 기존 모델의 기록·바이너리 해시·건물 매칭 보존은 `tests/fixtures/preserved-1160-landmarks.json`과 대조합니다. 지도 자료는 © OpenStreetMap contributors 등 각 원본의 이용조건을 따릅니다.

## 실제 화면 확인

- [올림픽대교 주탑·케이블](images/olympic-bridge.png)
- [개포중학교와 주변 단지](images/gaepo-school.png)
- [4.19민주묘지 역·실제 버스 정류장 좌표](images/station-and-bus.png)

Chrome 자동화에서 기존 주요 모델 4개와 신규 모델 6개를 확인했고, 교량·공공기관·도로·역·정류장 토글과 가까운 모델 로딩 제한을 검사했습니다. Node 검사 1,595개와 전체 GLB 1,550개 파싱·해시·치수 검증, 운영 빌드를 통과했습니다. 운영 화면의 데이터 HTTP 응답도 별도로 확인했습니다.
