# 대표 모델 batch08

용두신동아·강일리버파크4·7·10단지·도곡삼성래미안·사당자이·중림삼성사이버빌리지·등촌부영의 사진 참고 대표 외관 8개 단지, 원본 건물 폴리곤 76개를 추가한다. 단지별 대표 프로필 1개를 반복하며 `completionCredit=false`, `reviewstatus=coarse-visually-reviewed`로 기록한다. 개별 동 정밀 복원이나 실측 정확도를 주장하지 않는다.

| 단지 | 원본 폴리곤 | 높이 근거 |
|---|---:|---|
| 용두신동아 | 5 | 15층 × 3m, 17층 × 3m 추정 5개 |
| 강일리버파크4단지 | 10 | 원본 높이 유지 |
| 도곡삼성래미안 | 10 | 원본 높이 유지 |
| 강일리버파크7단지 | 11 | 14층 × 3m 추정 1개 |
| 사당자이 | 9 | 원본 높이 유지 |
| 중림삼성사이버빌리지 | 12 | 원본 높이 유지 |
| 등촌부영 | 7 | 원본 높이 유지 |
| 강일리버파크10단지 | 12 | 원본 높이 유지 |

원본 배치·방향·외곽선·높이를 유지했다. 선택 단지의 sourceIssues는 비어 있고 retained source ID 전체를 검증했다. 공식 동수 일치는 개별 동 식별 증거가 아니다. 용두 5개와 강일7의 1개 등 높이 누락 6개는 소스 층수×3m 추정이며, 나머지 70개는 원본 높이다. 강일10의 원본 50m/14층 조합도 임의 변경하지 않았다. 파라펫·옥탑은 추가된 대표 디테일이다.

제공된 로컬 참고사진 8장을 직접 확인하고, 각 단지 양방향 고가 시점 렌더 16장을 생성 전후가 아닌 첫 생성 및 수정 후 각각 검토했다. 새 사진 검색은 수행하지 않았다. 과도한 면 전체 강조색을 제거하고 용두·사당의 창 높이를 줄였다. 사진 파일은 배포하지 않고 출처 URL·직접 이미지 URL·SHA-256을 보존한다.

용두는 회색 수평 측벽 띠와 청록 창호, 강일4는 크림 벽과 옅은 분홍 창열, 도곡은 흰 벽·상부 초록 패널·직사각 옥상 프레임, 강일7은 황록 측벽 띠·발코니 띠·옥상 캡, 사당은 짧은 수평 창호·회색 측면 띠·얕은 박공지붕 코어, 중림은 청록 유리·황갈색 창열·단차 옥탑, 등촌은 연속 수평 창열·베이지 측벽, 강일10은 황갈색 창열·갈색 하부·옥상 캡을 선택했다. 원본 사진과 렌더의 구체 비교는 published-representative.json의 sourceId별 observation에 기록했다.

보이지 않는 입면, 정확한 창수·발코니 깊이·동별 사진 대응은 미확정이다. 특히 도곡·중림의 긴 면 내 넓은 무창벽 위치는 개별 식별하지 못해 단순화했다. 사당 사진의 710 표기 역시 개별 source ID에 대응시키지 않았다. 로고·에어컨·출입구·조경·경사지형·정확한 옥상 장식은 생략 또는 근사했다.

## 보류

- 시흥삼익 (A15383702): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 쌍문현대1차 (A13286109): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 명일지에스 (A13483002): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 신정동일하이빌 (A15807315): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 문화촌현대 (A12009305): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 창동주공2단지 (A13204508): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 상아2차아파트 (A13886009): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 청량리신현대 (A13087201): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 보라매롯데낙천대 (A15601104): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- e편한세상화랑대아파트 (A10025855): Missing both source height and floor count.
- 고척서울가든 (A15282810): Missing both source height and floor count.
- 꿈의숲푸르지오 (A13613009): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 왕십리 자이 아파트 (A10026900): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 송파파인타운8단지 (A13821006): Incomplete retained geometry or source issues.
- 하계1차청구아파트 (A13987205): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.
- 중계주공8단지 (A13922111): Supplied research has no retained identity-validated reference image; no new image search performed in this modeling batch.

## 검증과 보존

- 기존 Blender PID 73533, MCP 9885 포트를 먼저 확인하고 실제 MCP에서 생성·검증했다.
- 76개 source polygon/height 보존 검사 통과. blend는 source ID별 개별 메시 유지.
- GLB는 단지당 5–6 draw calls, 0.08–2.12MB. 창호는 평면이며 숨은 창문 박스 프리즘 없음.
- 실제 MCP 실행 기록, 렌더 16장, 편집 blend, 독립 입력·레시피 보존.
- `node scripts/validate_representative_models.mjs` 통과. 누적 검증 43자산/535폴리곤은 이번 배치 신규 수량과 구분한다.
- `node --test tests/representative-models.test.mjs` 2개 통과.
- `python3 -m unittest discover -s tests -p 'test_representative_publisher.py'` 2개 통과.
- 최신 main `6e8e126c6d608cb26b9d29111abd8a81a02b26b4` 및 시작 HEAD의 bespoke/reference/기존 representative 소유권 검사에서 겹침 없음.
- strict bespoke 완료 통계·기존 자산은 변경하지 않았다.

기준 브랜치 `feat/apartment-representatives-07`의 앞선 PR에 의존한다. 병합·배포는 수행하지 않는다.
