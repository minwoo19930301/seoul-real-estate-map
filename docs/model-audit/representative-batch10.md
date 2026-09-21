# 대표 모델 배치10

사진을 직접 검토한 5개 단지, 보존 원본 폴리곤 37개를 대상으로 한 coarse representative 모델이다. 동별 정밀 복원 완료로 집계하지 않는다 (`completionCredit=false`).

| 단지 | 원본 폴리곤 | GLB 바이트(정규화 전) | draw calls |
|---|---:|---:|---:|
| 세운푸르지오헤리시티 (A10023352) | 1 | 296208 | 6 |
| 신길센트럴아이파크 (A10025562) | 6 | 503992 | 6 |
| 대방1차e편한세상 (A15602007) | 7 | 856932 | 6 |
| 힐스테이트서울숲리버 (A10026470) | 15 | 1172848 | 6 |
| 여의도한양 (A15088918) | 8 | 536456 | 6 |

## 근거와 검토

Blender PID 73533 / localhost:9885에서 실제 MCP execute를 수행했다. 각 단지 두 고가 시점 렌더를 직접 검토했고, 원본 footprint 좌표·방향·높이를 Blender mesh와 비교 검증했다. 최신 main 및 현재 base의 bespoke/reference/representative 소유권과 충돌하지 않는다.

- 이전 PR base: `feat/apartment-representatives-08` (`4970a4a9f216715f317b9899eccf606be85a03eb`)
- 확인한 origin/main: `6e8e126c6d608cb26b9d29111abd8a81a02b26b4`
- 37개 모두 원본 height_m 사용. 이번 승인 모델에 3m/floor 대체 추정은 0개다. 원본 높이 자체는 실측 보증이 아니다. 층 수/창 배치 및 옥상 시설은 대표적 근사이며 옥상 박스는 원본 몸체 높이 위에 추가된다.
- 사진은 배포하지 않으며 source URL/SHA-256을 audit와 manifest에 기록한다.
- 원본 폴리곤 개수가 공식 동 수와 같다는 사실로 동별 식별을 주장하지 않는다. 보이지 않는 입면, 지형 단차, 정확한 동별 창/발코니/출입구 위치는 미확인이다.
- 신길·대방·서울숲 등의 반복 facade는 단지 내 대표 프로필이며, 다른 단지는 별도 팔레트·창·지붕 설정을 사용한다. 여의도한양은 복도/창 스택 두 프로필을 사용한다.

### 세운푸르지오헤리시티

Photo shows a tall angular urban block with white horizontal bands, dark glazing and a charcoal end strip, flat parapet and lower podium. Retained polygon and 90m source height drive massing; podium setback and exact band placement are not surveyed. Both elevated renders retain the angular footprint and show horizontal white bands and dark end panels; facade is more uniform than the photo and omits the detailed podium/crown articulation.

### 신길센트럴아이파크

Photo shows beige towers, white window surrounds, brown vertical recesses, large blue balcony glazing and broad beige end walls. Entrance sign confirms address 426. Representative window stacks and flat parapets approximate these cues; individual towers and entrance canopy are not reconstructed. Both renders show six retained separate source blocks, beige blank ends and white/brown window stacks. Wider revised bays reduce excessive density; the photo has more varied balcony widths/recess depths than this repeated profile.

### 대방1차e편한세상

Photo shows light gray walls and white balcony edges/railings around broad blue-green glazing. Trees obscure the base and roof is cropped. Shallow balcony ledges approximate visible relief; roof plant and unseen end walls remain assumptions. Both renders show seven source slabs with gray walls, broad repeated glazing and shallow white balcony ledges. The photo has individual railings/AC units absent from the model; roof boxes are schematic because the reference is cropped.

### 힐스테이트서울숲리버

Photo shows cream walls, conspicuous green vertical panels, small square windows alternating with wider balcony glazing and simple flat rooflines. Green stacks are represented but exact bay assignment and unseen walls are approximate. Both renders show the full 15 retained irregular blocks with cream/green vertical stacks. Photo green is concentrated in broad panels while the representative profile repeats narrower stacks; exact facade orientation and terrain steps are unresolved.

### 여의도한양

Aerial photo shows white slabs, green FLAT roofs, small rooftop boxes, rear horizontal corridor bands, front dark glazed balcony stacks and pale yellow strips. Recipe represents both long-wall rhythms; no pitched roofs inferred. Connected source polygon layout retained; exact circulation/balcony assignment is approximate. Both renders retain all eight polygons with green flat roof surfaces and corridor versus window-stack profiles. The photo confirms these two rhythms but not their assignment to every source edge; the long source slabs and exposed end walls are retained, not individually surveyed.

## 보류

- 청량리한신1차 (A13086703): No locally validated exterior photo available
- 창동신창 (A13204302): No locally validated exterior photo available
- 성수롯데캐슬 (A13312302): Incomplete retained geometry: 5 of 7 expected source IDs; complex holes/omissions held
- 방학삼성래미안1단지 (A13285406): No locally validated exterior photo available
- 강동리엔파크11단지 (A10024420): No locally validated exterior photo available
- 답십리동답한신 (A13003405): No locally validated exterior photo available
- 창동동아 (A13290003): Source includes named block 7 and unnamed 17-floor 66m block; photo shows blocks 6/3/1 and 15-floor slabs. Tower membership/massing unresolved; count match is insufficient
- 중계주공6단지 (A13922909): No locally validated exterior photo available
- 상계미도 (A13971501): No locally validated exterior photo available
- 영등포경남아너스빌 (A15003701): No locally validated exterior photo available
- 삼성래미안공덕4차 (A12170601): No locally validated exterior photo available
- 길동GS강동자이 (A13488104): No locally validated exterior photo available
- 아크로리버뷰 신반포 (A10026227): No locally validated exterior photo available
- e편한세상 고덕 어반브릿지 (A10022756): No locally validated exterior photo available
- 신정동아이파크 (A15807210): No locally validated exterior photo available
- 경희궁자이3단지 (A10027105): Photo does not isolate phase 3; phase identity unresolved
- 용산더프라임 (A14070302): No locally validated exterior photo available
- 서울숲2차푸르지오 (A13378102): No locally validated exterior photo available
- 마곡힐스테이트 (A10027687): Rendered source layout includes detached unnamed 16-floor polygon; named 107 absent. Photo identifies 105/108 only. Membership of detached source cannot be validated; hold entire complex.

## 검증

- `node scripts/validate_representative_models.mjs`: 통과 (전체 catalog 48 assets / 572 source footprints; 이번 배치 실적과 구분).
- `node --test tests/representative-models.test.mjs`: 2/2 통과, draw 성공 후 ownership 및 실패 fallback 포함.
- `python3 -m unittest discover -s tests -p test_representative_publisher.py`: 2/2 통과.
- MCP scene validation: 승인 5개 단지 / 37개 원본 footprint 및 높이 보존.
- 단지별 GLB 15MB 미만, 편집용 blend 95MB 미만.
- 병합 및 배포하지 않음. 이전 PR branch에 의존하는 새 PR.
