# 대표 모델 batch15: 창동동아그린·삼성동 아이파크·도봉래미안

사진을 참고한 단지별 대표 프로필 1개를 원본 건물에 반복 적용한 coarse 모델이다. `completionCredit=false`, `coarse-visually-reviewed`; 정밀 개별 동 복원이나 실측 정확도를 주장하지 않는다.

|단지|코드|원본 윤곽|원본 높이|원본 층수|
|---|---|---:|---|---|
|창동동아그린|A13204506|3|53m|17|
|아이파크삼성동|A13509009|3|178/200/198m|38/45/45|
|도봉래미안|A13293505|7|46–51m|16–18|

총 3단지, 13개 원본 윤곽을 빠짐없이 보존했다. 위치·방향·본체 높이를 유지하며 옥상 장식은 위에 별도로 추가한다. 이번 배치의 높이 추정은 0건이다. 층수만 있는 입력에는 3m/층 추정 규칙을 사용하지만 이번 선택에는 해당하지 않는다. 아이파크 높이/층수 비율의 불일치는 보정하거나 실측값으로 주장하지 않고 원본 그대로 남겼다. 공식 동 수와 윤곽 수 일치는 개별 동 식별의 근거가 아니다.

## 사진 대조 및 한계

### A13204506

Both elevated renders inspected against the retained photo: three connected-wing source polygons at 53m retain their bends and orientation. Peach blank ends, broad dark glazing and light balcony bands approximate the photograph. Initial dense bays widened to 5.2m and blank end treatment expanded. Roof heads are smaller and simpler than photographed stepped heads; railings, exact pink vertical strips, low foreground buildings and unseen walls are not reconstructed. Source 17-floor values retained; photo is not a per-tower floor survey.

### A13509009

Both elevated renders inspected: three stepped source tower footprints at 178, 200 and 198m retain their placement and height differences. Cyan glazing and fine light divisions follow the photo. Initial separated window holes replaced with near-continuous glazing and missing open crown frames added. Final overview includes full crown. Photo has stronger silver vertical stripes, projecting balcony ledges and asymmetric crown placement; these remain coarse. Source 38/45/45 floors retained despite height-to-floor inconsistency; no height invented or tower-wing identity validated.

### A13293505

Both elevated renders inspected: seven source rectangles at 46-51m retain placement and height. Gray blank endwalls and separated dark rectangular windows follow the 101 and neighboring facade photograph. Bay spacing widened to 5.8m after first render. Source rectangles omit shallow facade articulation; rooftop stair heads are simplified stepped boxes, and brick scoring, ribbed borders, rails and numbered logo are omitted. Appearance outside the photographed buildings is a repeated representative profile, not verified tower identity.

## 근거와 재현

- 실제 Blender MCP 9885, PID 73533 확인 후 생성·검증했다. 다른 포트는 사용하지 않았다.
- `modeling/representative/representative-batch15/`에 편집 가능한 개별 메시/원본 ID가 담긴 blend, 자체 완결 입력 및 빌더·검증·내보내기 레시피를 보존한다.
- `docs/model-audit/mcp/representative-batch15-mcp-*-evidence.json`에 실제 MCP 응답을 보존한다.
- `docs/model-audit/renders/representative/representative-batch15/`에 단지별 높은 시점의 정방향·반대방향 2개 렌더를 보존한다.
- 출처 이미지 URL과 SHA-256 및 검토 입력 해시는 published-representative 감사 기록에 포함한다. 원본 사진은 ignored 로컬 자료로 유지한다.
- 셸 원본 윤곽 및 높이 검사 통과. 모든 창은 면으로 표현하며 숨겨진 창 박스 프리즘은 만들지 않는다. GLB는 재질별 결합, 단지당 5 draw calls, 최대 약 1.84MB.
- `node scripts/validate_representative_models.mjs` 통과; `node --test tests/representative-models.test.mjs` 2건 통과; `python3 -m unittest discover -s tests -p 'test_representative_publisher.py'` 2건 통과.

## 제외와 통합 경계

24곳 중 21곳 보류: 상계동양메이저는 사진에서 수목이 외관을 가리고 옥상이 나오지 않아 보류했다. 나머지 20곳은 제공된 연구에 검증된 외관 이미지가 없다. 이번 작업에서 새 이미지 검색을 수행했다고 주장하지 않는다. 보류 입력은 교체하지 않는다.

시작 브랜치 `feat/apartment-representatives-14`, 시작 커밋 `5cbaa6df11fefac7dbc48aa6dbf3914ceda1d249`. 읽기 전용 fetch로 확인한 최신 main `6e8e126c6d608cb26b9d29111abd8a81a02b26b4`의 bespoke/reference 소유 윤곽 및 현재 대표 모델과 교집합 0건. 기존 자산·정밀 완성 통계는 수정하지 않는다. 이전 PR #28 브랜치에 의존하는 후속 PR이며 병합·배포는 수행하지 않는다.
