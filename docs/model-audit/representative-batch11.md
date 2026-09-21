# 대표 모델 배치 11

사진을 직접 확인한 6개 단지의 원본 풋프린트 41개를 대표 프로필로 모델링했다. 개별 동 번호 대응이나 정밀 복원 완료를 주장하지 않는다. `completionCredit: false`, `reviewstatus: coarse-visually-reviewed`.

| 단지 | 원본 폴리곤 | 높이 근거 | GLB 바이트 | 드로콜 |
|---|---:|---|---:|---:|
| 옥수극동그린아파트 (A13384403) | 5 | 기존 소스 높이 유지 | 925724 | 6 |
| 여의도자이 (A15076302) | 4 | 기존 소스 높이 유지 | 2172976 | 6 |
| 청화아파트 (A14086001) | 9 | 층수 × 3m 추정 | 145996 | 6 |
| 잠실우성4차 (A13822902) | 7 | 층수 × 3m 추정 | 757920 | 6 |
| 강일리버파크6단지 (A13410004) | 10 | 기존 소스 높이 유지 | 1098528 | 6 |
| 서초호반써밋 (A13778211) | 6 | 기존 소스 높이 유지 | 1248068 | 6 |

청화 9개(30/36m), 잠실우성4차 7개(45m)는 높이가 없어 층수로 추정했다. 나머지 25개는 기존 소스 높이이며 새로 측량한 값이 아니다. 모든 단지는 한 가지 단지별 대표 프로필을 반복한다. 원본 위치·방향·높이와 모든 선택 폴리곤을 보존했다. 동 수 일치는 동별 식별 증거로 사용하지 않았다.

## 사진 및 양방향 렌더 비교

### 옥수극동그린아파트

Local photo shows the 105 label on a broad off-white blank endwall, one green horizontal band, dense gray-blue enclosed balcony glazing, and taller rooftop enclosures. Both elevated model views retain the irregular bent slabs and use restrained green endwall bands with a broad window grid. Initial excessive green facade fill was removed. Generic compact rooftop boxes are lower/simpler than the photographed service cores; signs, commercial frontage and terrain are omitted. The photograph does not map every source polygon to a numbered tower.

[남동측 렌더](renders/representative/representative-batch11/A13384403-overview.png) · [북서측 렌더](renders/representative/representative-batch11/A13384403-reverse.png)

### 여의도자이

Photo shows cream high-rise wings with dense small windows, brown lower cladding and projecting rooftop frames. Both model views retain the four lobed source footprints at source height, brown lower floors and pale facade frames. Rooftop edge frames were added after initial render review. The repeating grid is regularized; the photographed multi-level crowns, entrance bridge and podium are not reconstructed.

[남동측 렌더](renders/representative/representative-batch11/A15076302-overview.png) · [북서측 렌더](renders/representative/representative-batch11/A15076302-reverse.png)

### 청화아파트

Photo shows a pale slab with nearly continuous horizontal gray glazing, fine vertical mullions and a largely blank side wall. Both model views reproduce the horizontal band emphasis and low rooftop boxes over all nine retained source polygons. Fine band mullions were added after first review. Heights are explicitly 3m per source floor (30 or 36m), not measured; ground slopes and brick boundary wall are omitted.

[남동측 렌더](renders/representative/representative-batch11/A14086001-overview.png) · [북서측 렌더](renders/representative/representative-batch11/A14086001-reverse.png)

### 잠실우성4차

Photo shows labeled 108/105/103 slabs, large blank endwalls, repeated blue-gray enclosed balconies and subdued peach vertical strips. Both model views use broad blank ends and repeating pale/peach window stacks with flat service roofs on the seven retained footprints. Balconies are flattened to surface glazing rather than deep protruding boxes; window count and numbered tower matching remain unverified. Height is estimated as 15 source floors times 3m = 45m for each source polygon.

[남동측 렌더](renders/representative/representative-batch11/A13822902-overview.png) · [북서측 렌더](renders/representative/representative-batch11/A13822902-reverse.png)

### 강일리버파크6단지

The local composite photo visibly labels 603 and shows pale walls, yellow vertical accents, blue-gray glazing and dark projecting rooftop frames. Both elevated model views retain the varying source heights and stepped footprints, using yellow stacks and dark roof-edge frames. The roof frames were strengthened after first review. Short stepped wall segments and balcony setbacks are regularized, and only the photographed complex-level treatment is repeated; individual numbered tower identity is unproven.

[남동측 렌더](renders/representative/representative-batch11/A13410004-overview.png) · [북서측 렌더](renders/representative/representative-batch11/A13410004-reverse.png)

### 서초호반써밋

Photo shows white facade panels with charcoal vertical stacks, teal-blue windows, shallow recessed balconies and small orange roof-corner markings. Both elevated model views retain the six source footprints and heights, with charcoal window stacks and compact dark service roofs. The orange markings and fine balcony railings are omitted; repetitive window spacing and unseen walls are representative. A single site profile is repeated without claiming per-tower identity.

[남동측 렌더](renders/representative/representative-batch11/A13778211-overview.png) · [북서측 렌더](renders/representative/representative-batch11/A13778211-reverse.png)

## 근거와 한계

사진은 저장소에 배포하지 않는다. 원본 페이지 URL, 이미지 URL과 SHA-256은 `modeling/representative/representative-batch11/source-evidence.json`에 보존했다. 편집 가능한 Blend는 개별 메시와 source ID를 유지한다. 레시피 입력과 수학 생성기는 같은 디렉터리에 자급적으로 저장했다. 창문은 면으로 구성하고 GLB만 재질별 결합했다. 지형, 실제 동별 창 개수, 가려진 벽, 난간·간판·상가/포디움·조경은 단순화 또는 생략했다.

## 보류

로컬 검증 사진이 없는 18개 단지는 integrationHold=true로 제외했다. 이번 작업에서 이 단지들의 검색 또는 시각 검증을 수행했다고 주장하지 않는다. 상세 이유는 source-evidence.json의 holds에 기록했다.

- 마곡엠밸리10단지 아파트 (A10027452)
- 무악현대임대아파트 (A11008001)
- 창신쌍용1단지 (A11054301)
- 연희대우 (A12011002)
- 마포자이2차 (A12172401)
- 신촌태영데시앙 (A12188205)
- 방학우성2차 (A13282510)
- 옥수현대 (A13376702)
- 강변건영 (A13392307)
- 명일신동아 (A13407204)
- 명일동우성 (A13482505)
- 한솔마을 (A13594701)
- 송파파인타운6단지 (A13876108)
- 풍납 현대리버빌1차 (A13887405)
- 월계6-2초안 (A13905208)
- 원효산호 (A14085002)
- 여의도대교 (A15001016)
- 등촌주공10단지 (A15703306)

## 검증 및 의존성

기준 브랜치: `feat/apartment-representatives-10` / 커밋 `e97c032ccca20b8b060850f9da587e115bb78c4c`. 이전 PR #24에 의존한다. 최신 origin/main `6e8e126c6d608cb26b9d29111abd8a81a02b26b4`의 bespoke/reference 및 현재 브랜치의 기존 representative 소유권과 교차 검사했고 겹침은 0개다.

- 실제 Blender MCP: PID 73533, 격리 포트 9885. build/validation transcript는 docs/model-audit/mcp에 보존.
- Blender 장면 검사: 6개 단지, 41개 원본 풋프린트 및 높이 보존 통과.
- `node scripts/validate_representative_models.mjs`: 통과.
- `node --test tests/representative-models.test.mjs`: 2/2 통과, 로드 실패 시 generic 복원 포함.
- `python3 -m unittest discover -s tests -p test_representative_publisher.py -v`: 2/2 통과.
- 병합 및 배포는 수행하지 않았다.
