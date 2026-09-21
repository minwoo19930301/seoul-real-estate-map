# 대표 모델 batch07

사진을 참고한 거친 대표 외관 모델 8개 단지, 원본 폴리곤 81개를 추가한다. 단지별 대표 프로필 1개를 반복하며 `completionCredit=false`로 유지한다. 개별 동 정밀 복원이나 실측 정확도를 주장하지 않는다.

| 단지 | 원본 폴리곤 | 높이 근거 |
|---|---:|---|
| 용산e편한세상 | 13 | 원본 높이 유지 |
| 홍제무악청구1차 | 14 | 원본 높이 유지 |
| 송파삼성래미안 | 13 | 12층 × 3m 추정 1개, 나머지 원본 유지 |
| 역삼e-편한세상 | 12 | 원본 높이 유지 |
| 공릉3단지라이프 | 4 | 원본 높이 유지 |
| 가락우성1차 | 7 | 15층 × 3m 추정 7개, 나머지 원본 유지 |
| 신공덕1차삼성래미안아파트 | 11 | 원본 높이 유지 |
| 정릉대우 | 7 | 원본 높이 유지 |

원본 배치·방향·외곽선·높이를 유지했다. 선택 단지의 sourceIssues는 비어 있고 전체 retained source ID 집합을 검증했다. 공식 동수 일치는 개별 동 식별의 증거로 사용하지 않았다. 높이 누락 8개는 소스 층수에 3m를 곱했으며, 그 외 73개는 소스 높이를 유지했다. 옥상 서비스 박스와 파라펫은 별도의 대표 디테일이다.

12개 로컬 참고사진을 접촉시트로 직접 확인하고, 승인한 8개 단지의 양방향 고가 시점 렌더 16장을 수정 전후 확인했다. 가락·역삼의 최종 전체 해상도 렌더도 확인했다. 새 사진 검색을 수행했다는 주장은 없다. 첫 생성의 짧은 면 과도한 무창벽, 긴 면의 굵은 창살, 근거 없는 필로티형 기단을 수정했다. 사진 자체는 배포하지 않고 출처 URL과 SHA-256을 보존한다.

용산은 주황갈색 측벽과 어두운 지붕 테두리, 홍제는 따뜻한 회색 벽과 수평 줄눈, 송파삼성은 밝은 수직 기둥과 청록 창열, 역삼은 흰색 측벽과 회색 패널, 공릉은 크림색 벽과 짙은 청록 창열·단차 옥탑, 가락은 크림색과 황갈색 측벽, 신공덕은 밝은 측벽과 회색 수직 창열, 정릉은 옅은 분홍 측벽을 선택했다. 각 원본 사진과 렌더의 구체 비교는 published-representative.json의 해당 sourceId별 observation에 남겼다.

보이지 않는 입면, 정확한 창수·발코니 깊이·동별 사진 대응은 미확정이다. 평면 창호와 줄눈은 거친 근사이며 외부 에어컨, 난간 세부, 로고, 조경, 지형 및 출입구는 생략했다. 공릉의 계단 코어와 용산·역삼의 옥상 장식도 단순화했다.

## 보류

- 신트리4단지 (A15807316): No exact-name image result was available from the executed image query.
- 래미안허브리츠 (A13070301): No exact-name image result was available from the executed image query.
- 상암월드컵8단지 (A12127008): No exact-name image result was available from the executed image query.
- 독산주공14단지 (A15375809): Street photograph is heavily occluded by autumn trees; insufficient visible facade and full-height massing for representative profile.
- LH수서1단지(행복주택) (A10023314): No exact-name image result was available from the executed image query. Missing both source heights and floors.
- 반포래미안아이파크 (A10026051): Referenced banpo.jpg missing locally; cannot visually inspect supplied source.
- 서울숲아이파크리버포레 (A10020907): Phase identity unresolved in researched source; branding does not establish which Riverfore phase matches retained five towers.
- 신림주공2단지 (A15179403): Signed image URL failed during download; no alternate image URL was successfully obtained.
- 송파파크데일1단지 (A13881701): No exact-name image result was available from the executed image query.
- 강남엘에이치1단지 (A13519007): No exact-name image result was available from the executed image query.
- 개포7차우성 (A13594403): Major source massing mismatch: retained 5/14/26-floor mixture including 89m block is not validated by photographed older high-rise slabs; research mentions 17 buildings versus 15 retained.
- 신내동성3차아파트 (A13113004): No exact-name image result was available from the executed image query. Incomplete retained complex geometry.
- 더샵파크프레스티지 (A10023715): No exact-name image result was available from the executed image query.
- 송파파인타운9단지 (A13821007): No exact-name image result was available from the executed image query.
- 래미안송파파인탑 (A13817001): Rounded glazed tower profile in distant photo needs source-form validation; do not substitute standard slab profile.
- LH서초3단지 (A13778212): No exact-name image result was available from the executed image query.

## 검증과 보존

- Blender PID 73533, 전용 MCP 포트 9885에서 실제 생성 및 검증. 부모 포트 미사용.
- 81개 source polygon/height 보존 검사 통과. blend는 개별 source ID와 메시 유지.
- GLB는 단지당 재질 5개, 0.69–2.17MB. 숨은 창문 박스 프리즘 없이 평면 창호를 사용.
- MCP 실행 기록, 렌더 16장, 편집 blend, 독립 입력·레시피를 보존.
- `node scripts/validate_representative_models.mjs` 통과.
- `node --test tests/representative-models.test.mjs` 2개 통과.
- `python3 -m unittest discover -s tests -p 'test_representative_publisher.py'` 2개 통과.
- 최신 main `a89732cf8bf4ac8ec18501917250f162f6ea6cc9` 및 시작 HEAD의 bespoke/reference와 기존 representative 소유권을 확인했고 겹침 없음. main에는 representative manifest가 아직 없음.
- 엄격한 bespoke 완료 통계 및 기존 자산은 변경하지 않았다.

이 PR의 기준 브랜치는 `feat/apartment-representatives-06`이며 앞선 PR에 의존한다. 병합·배포는 수행하지 않는다.
