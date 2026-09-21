# 대표 아파트 배치12 시각 검토

사진을 직접 검토한 9개 단지의 원본 폴리곤 58개를 coarse representative 모델로 통합했다. 개별 동 정밀 복원이나 공식 완료 통계가 아니며 모든 자산의 `completionCredit`는 `false`다.

기준 브랜치: `feat/apartment-representatives-11` (`c897f6b0f763a8585f42f1d67accc0e0f9e2591f`). 읽기 전용 fetch로 확인한 main: `6e8e126c6d608cb26b9d29111abd8a81a02b26b4`. HEAD와 main의 bespoke/reference 소유권 및 HEAD의 기존 representative 소유권에 중복 없음. 기존 자산과 보호 풋프린트는 변경하지 않았다.

Blender PID 73533의 127.0.0.1:9885 리스너를 확인하고 실제 BlenderMCP로 생성·검증했다. 단지마다 남동/북서 고가 시점 2개를 직접 확인했다. 첫 렌더에서 과도한 창틀 폭과 하부 겹침을 수정했으며, 최종 렌더 18개와 MCP 기록을 보존한다.

| 단지 | 코드 | 원본 폴리곤 | 층수 기반 높이 추정 | GLB bytes | Draw calls |
|---|---|---:|---:|---:|---:|
| e편한세상마포리버파크 | A10028006 | 9 | 0 | 658020 | 6 |
| 거여4단지 | A13811203 | 6 | 0 | 700336 | 5 |
| 흑석롯데캐슬에듀포레 | A10025867 | 7 | 0 | 609028 | 6 |
| 가양대림경동 | A15780703 | 6 | 6 | 963680 | 6 |
| 창신두산 | A11054101 | 3 | 0 | 860584 | 5 |
| 월계청백4단지 | A13985107 | 4 | 1 | 239308 | 6 |
| 마곡수명산파크3단지 | A15728003 | 8 | 1 | 858776 | 5 |
| 답십리두산위브 | A13003003 | 7 | 0 | 775336 | 6 |
| 가락1차현대아파트 | A13820004 | 8 | 8 | 992600 | 6 |

높이값이 있는 42개는 원본 높이를 유지했다. 나머지 16개는 원본 층수 × 3m 추정: 가양대림경동 6개(45m), 월계청백4단지 1개(33m), 마곡수명산파크3단지 1개(45m), 가락1차현대 8개(36–42m). 지붕·파라펫은 별도 소규모 대표 디테일로 원본 벽체 위에 추가되었다.

## 사진과 최종 렌더 비교

### e편한세상마포리버파크 (A10028006)

White window stacks and orange mostly blank endwalls; slender gray ventilation strips; flat parapets. Both elevated renders retain the mixed slab and branched source masses and different heights. Orange end panels and white window stacks correspond to the visible 102/103 photo; the model uses simpler, more uniform paired panes and omits balcony railings and gray ventilation strips. Orange assignment on unseen short faces is approximate.

[사진 출처](https://hogangnono.com/apt/9YR91) · [남동 렌더](renders/representative/representative-batch12/A10028006-overview.png) · [북서 렌더](renders/representative/representative-batch12/A10028006-reverse.png)

### 거여4단지 (A13811203)

Broad blue-green glazed balcony stacks, white blank endwalls and dark red pitched roofs with raised stair heads. Both elevated views show six retained bent slabs, pale blank ends, broad teal windows and red sloped roof edges corresponding to the photographed 402/403 blocks. Window bays were widened after first review. Roof intersections and low central heads are simplified and do not reproduce the tall individual gabled stair heads or AC units.

[사진 출처](https://zippoom.com/부동산/서울-송파구-거여동-거여4단지/zugpk1) · [남동 렌더](renders/representative/representative-batch12/A13811203-overview.png) · [북서 렌더](renders/representative/representative-batch12/A13811203-reverse.png)

### 흑석롯데캐슬에듀포레 (A10025867)

Pale stone-like blank endwall, charcoal vertical strip, narrow stair windows and a dark lower wall; roof only partly visible. Both views show pale bodies with charcoal end stripes and narrow end windows, consistent with the photographed 101 blank wall and dark vertical panel. The source height variation remains. Repeated main-window faces and low roof boxes are approximate; the entrance logo, deep canopy and red lower decorative fins are absent.

[사진 출처](https://kbland.kr/se/c/33560) · [남동 렌더](renders/representative/representative-batch12/A10025867-overview.png) · [북서 렌더](renders/representative/representative-batch12/A10025867-reverse.png)

### 가양대림경동 (A15780703)

Cream blank slab end with salmon geometric patch; broad glazed window stacks on long sides, pale salmon roof head. Both views retain six parallel slabs, cream walls, salmon vertical accents and broad dark paired glazing. The photo shows a cream blank 104 end with salmon patch, represented on short ends; the two elevated views expose mostly long facades. Source heights are absent for all six: 15 floors are explicitly modeled as 45m. Actual alternating balcony projections and roof heads are simplified.

[사진 출처](https://hogangnono.com/apt/16p98) · [남동 렌더](renders/representative/representative-batch12/A15780703-overview.png) · [북서 렌더](renders/representative/representative-batch12/A15780703-reverse.png)

### 창신두산 (A11054101)

Beige blank slab ends, wide dark teal balcony glazing separated by horizontal rails, raised rectangular stair heads. Both views retain the three source polygons including long bent slabs, beige walls, teal balcony-window bands and blank short ends. Broad glazing was corrected from the initially overwide mullions. The photo supports beige blank ends and balcony bands, but does not certify every unnamed source polygon or the blank segmented rear wall; exact tower labels, AC units and rooftop stair positions remain unverified.

[사진 출처](https://hogangnono.com/apt/Ycc) · [남동 렌더](renders/representative/representative-batch12/A11054101-overview.png) · [북서 렌더](renders/representative/representative-batch12/A11054101-reverse.png)

### 월계청백4단지 (A13985107)

Yellow-beige walls, salmon corridor bands on left block and salmon window spandrels on right block; blank endwall 402. Both views show yellow-beige slabs with salmon corridor bands and alternate window-stack faces, reflecting the two facade types visible on 402/403. The lower fourth source body is retained at 11 floors estimated as 33m; other source heights remain 40m even though 15 floors are recorded. Exact assignment of corridor vs apartment elevations is approximate.

[사진 출처](https://m.r114.com/?ComplexCd=A01091390500033&ComplexNm=&CortarNo=&_a=detail&_c=memul&_m=complex&mmCode=A01011) · [남동 렌더](renders/representative/representative-batch12/A13985107-overview.png) · [북서 렌더](renders/representative/representative-batch12/A13985107-reverse.png)

### 마곡수명산파크3단지 (A15728003)

White walls, brown brick lower floors, broad blue-gray balcony glazing; largely blank 304 endwall. Both views retain irregular and rectangular source outlines, white walls, blue-gray glazing, blank short ends and brown lower walls matching the courtyard photo and 304 endwall. Lower brick coloration is represented without masonry joints; repeated windows and parapets simplify the photo. One 15-floor source without height is estimated at 45m; other source heights remain unchanged.

[사진 출처](https://hogangnono.com/apt/183c0) · [남동 렌더](renders/representative/representative-batch12/A15728003-overview.png) · [북서 렌더](renders/representative/representative-batch12/A15728003-reverse.png)

### 답십리두산위브 (A13003003)

Off-white blank 102 endwall, slate-blue vertical spandrels beside broad windows and dark roof edging/stair head. Both views retain the seven rectangular source slabs, off-white blank short ends, slate-blue vertical stacks and dark rooftop boxes. This follows the photo of the 102 endwall and neighboring glazed facade. Source rectangles omit the photographed stair protrusions; facade and small rooftop heads approximate those details without changing source outlines. Window counts and individual tower labels are not certified.

[사진 출처](https://kbland.kr/se/c/14127) · [남동 렌더](renders/representative/representative-batch12/A13003003-overview.png) · [북서 렌더](renders/representative/representative-batch12/A13003003-reverse.png)

### 가락1차현대아파트 (A13820004)

Pale cream blank 15 endwall, muted brown vertical accents, blue-gray balcony glazing and flat low parapet. Both views retain eight long stepped slabs, pale cream bodies, muted brown vertical stacks, blue-gray paired windows and blank ends corresponding to the photographed 15 endwall and entrance background. All eight lack source heights and use source floors times 3m (36-42m). The entrance brick wall is not used as tower cladding; railings, trees and exact rear elevations are omitted.

[사진 출처](https://www.geconomy.co.kr/news/article.html?no=299896) · [남동 렌더](renders/representative/representative-batch12/A13820004-overview.png) · [북서 렌더](renders/representative/representative-batch12/A13820004-reverse.png)

## 근사 한계와 보류

단지별 팔레트·창 패턴·측벽·지붕 선택을 적용하되 단지당 1개 대표 프로파일(월계청백은 복도/창 스택 2개)을 반복했다. 짧은 면을 측벽으로 분류하는 기준, 창 개수, 보이지 않는 후면과 옥탑 위치는 측량 결과가 아니다. 원본 수량과 공식 동수가 같다는 이유로 개별 동 동일성을 확정하지 않았다. 실제 사진은 ignored data 폴더에 두고 출처 URL과 SHA-256만 배포한다.

아래 15개는 통합 보류(`integrationHold=true`). 사진 없는 14개는 기존 연구 기록의 실패를 인용한 것이며 이번 작업에서 새 검색을 수행했다고 주장하지 않는다.

- 서초포레스타5단지 (A13716002): Retained research has no validated local photograph: Direct image download returned HTTP 404; one independent result was available but its image URL was not retrievable.
- 강남데시앙파크 (A13519005): Retained research has no validated local photograph: Image query returned no exact-name source usable for identity and download.
- 문정건영 (A13820005): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 목동현대A (A15870102): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 신트리3단지 (A15807311): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 신내새한아파트 (A13187406): Retained research has no validated local photograph: Available image result identified Shinnae phase 9, not 신내새한아파트; excluded to avoid wrong phase.
- 래미안밤섬리베뉴 2 (A12170702): Retained research has no validated local photograph: Image query did not return a source clearly identifying phase 2.
- 정릉푸른마을동아 (A13684605): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 안암래미안 (A13607101): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 천호동아하이빌 (A13486504): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 천왕이펜하우스2단지 (A15213003): Retained research has no validated local photograph: Image query did not return an exact phase-2 source suitable for download.
- 신도림디큐브시티 (A15277302): Retained research has no validated local photograph: No downloaded local image available for required MIME and visual inspection.
- 천왕이펜하우스5단지 (A15213001): Retained research has no validated local photograph: Image query did not return an exact phase-5 source suitable for download.
- 길음뉴타운 데시앙 (A13676605): Retained research has no validated local photograph: Image query returned no exact complex image suitable for download and identity confirmation.
- 마포강변힐스테이트 (A12112002): Hold source identity: two distinct retained footprints are both labeled 105, one has no tower name; entrance-focused photo cannot resolve full site/tower assignment. Counts alone are insufficient.

## 검증

- Blender 장면 검증: 58개 원본 외곽 XY 오차 < 0.001m, 벽체 높이 오차 < 0.01m; 소스 ID별 개별 메시 보존.
- 재질별 GLB 내보내기 5–6 draw calls/site, 각 GLB < 1MB. 창은 표면 quad이며 숨겨진 창 박스 프리즘을 만들지 않았다.
- `node scripts/validate_representative_models.mjs`: passed (누적 63 자산 / 671 원본 폴리곤; 이번 배치는 9 / 58).
- `node --experimental-strip-types --test tests/representative-models.test.mjs`: 2 passed; 로드 실패/실제 draw 시점의 generic fallback 검증.
- `python3 -m unittest discover -s tests -p test_representative_publisher.py`: 2 passed.
- 모든 검토 입력에 SHA-256을 기록; self-contained recipe inputs, editable blend 및 source URLs를 보존.
- PR은 이전 배치11 브랜치에 의존한다. Merge/deploy 수행 없음.
