# Representative batch 14

사당휴먼시아 8개, 구산동 경남아너스빌 9개, 홍제삼성래미안 6개, 신정이펜하우스2단지 20개 원본 폴리곤에 사진을 참고한 거친 대표 모델을 추가합니다. 단지별 1개 외관을 반복하며 개별 동 식별이나 정밀 복원을 주장하지 않습니다. completionCredit=false.

원본 배치·방향·높이를 보존했습니다. 홍제삼성래미안의 1개 높이는 원본 12층 × 3m = 36m 추정입니다. 창 배열, 보이지 않는 면, 옥상 구조 위치, 난간·발코니 깊이·지형은 근사 또는 생략했습니다. 사진 부족/매스 불일치/단지 구분 문제로 20곳을 보류했습니다.

실제 Blender MCP 9885 생성·검증, 고각 렌더 8장 사진 비교 및 창 간격 수정. GLB당 5–6 draw calls, 0.7MB 미만. Node 모델 검증, 대표/fallback Node 테스트 2개, Python publisher 테스트 2개 통과.

이 PR은 이전 PR #27 및 feat/apartment-representatives-13에 의존합니다. 병합·배포하지 않습니다. 상세 비교: docs/model-audit/representative-batch14.md.

Base branch: feat/apartment-representatives-13

Base HEAD: fccdfc09c1b8fe12f5c04cdb7d5c1f89f56448a7

Read-only fetched main ownership checked: 6e8e126c6d608cb26b9d29111abd8a81a02b26b4; no selected protected/replaced overlap.

## 사당휴먼시아 — A15609003

8 retained source polygons. Both elevated views retain eight straight source slabs at 34-42m. Cream blank ends, blue gray glazing and stepped tan heads follow the 101/102 photograph. Initial narrow window bays were widened to 5m; ledges, rails, stepped upper facade and exact roof-head placement remain simplified.

## 경남아너스빌(구산동) — A12282203

9 retained source polygons. Both views retain nine source slabs and their 22-54m height range. Cream walls, orange infill and green gray roof caps follow visible 104/105. Window bays widened to 4.8m after review. Rectangular source shells omit shallow balcony recesses and endwall graphics; no numbered tower assignment is claimed.

## 홍제삼성래미안 — A12009202

6 retained source polygons. Both views retain six source polygons including bent outlines. White walls, teal stacks and broad dark balcony panes follow the 103 photograph. Bays widened to 5m. Five 40m source heights retained; one 12-floor source estimated at 36m. Rear stair-window distribution, rails and exact endwall allocation remain approximate.

## 신정이펜하우스2단지 — A15809002

20 retained source polygons. Both views retain all twenty low source blocks including open U-shaped footprints and 11-22m height variation. Cream walls, sparse dark windows and blank ends follow photographed 207. Bays widened to 4.5m. Only one cluster is photographed, so repeated appearance across other blocks, flat parapets replacing roof rails, concealed lower levels and terrain remain approximate.

## Holds

- 천호우성: No retained visually validated photograph.
- 용산롯데캐슬센터포레아파트: Only promotional aerial rendering retained; built finishes not photo-validated.
- 마포펜트라우스: Cropped entrance photo cannot resolve major connected podium and complete tower massing.
- 대림3동현대아파트: No retained visually validated photograph.
- 화곡중앙하이츠: No retained visually validated photograph.
- 동진신안: No retained visually validated photograph.
- 신정이펜하우스1단지(총세대 기준): No retained visually validated photograph.
- 임광관악파크: Photo shows deeply recessed open corridor and tall separated stair cores; rectangular retained source cannot reproduce major end massing.
- 수색대림한숲타운제2: No retained visually validated photograph.
- 당산진로: No retained visually validated photograph.
- 신성둔촌미소지움1차: No retained visually validated photograph.
- 개포4차우성: No retained visually validated photograph.
- 월계청백3단지: No retained visually validated photograph.
- 중계센트럴파크아파트: No retained visually validated photograph.
- 등촌동성: No retained visually validated photograph.
- 송파파인타운5단지: No retained visually validated photograph.
- 염창강변한솔솔파크: Foreground 102 is branded Kumho Oullim while Hansol blocks behind have different pitched roof heads; phase assignment unresolved.
- 휘경동일스위트리버: No retained visually validated photograph.
- 면목 라온 프라이빗 아파트: No retained visually validated photograph.
- 광장힐스테이트: No retained visually validated photograph.

Editable blend retains individual source IDs. Joined exports contain planar window faces, not hidden window box prisms. Reference photos remain ignored; source URLs and SHA-256 hashes are distributed with the audit. No strict bespoke completion statistics changed.
