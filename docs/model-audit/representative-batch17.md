# 대표 모델 배치 17

금호자이2차 6개, 정릉푸르지오 7개 원본 건물 폴리곤에 사진을 참고한 대표 외관을 추가합니다. 단지별 하나의 대표 프로필을 반복하며, 개별 동의 정밀 복원 또는 동 식별을 주장하지 않습니다.

- 원본 배치·방향·높이·층수 유지. 이번 승인 대상은 모두 원본 높이가 있어 3m/층 높이 추정은 사용하지 않았습니다. 옥상 장식은 근사값입니다.
- 금호: 회백색 벽, 갈색 측벽/코어, 녹색 유리, 어두운 옥상 프레임. 정릉: 미색 벽, 올리브색 하부 측벽, 반복 유리창과 옥상 설비실.
- 단지별 두 방향 렌더와 실제 사진을 직접 비교했습니다. 경사지·저층 포디움·동별 계단형 매스·난간·보이지 않는 벽은 단순화했습니다.
- 방화동부센트레빌, 개포우성3차는 원본 동 구성/매스 불일치 우려로 보류. 중계대림벽산은 검증 사진 부재, 아이파크상도동은 파노라마 내 대상 식별 부족으로 보류했습니다.
- Blender MCP 9885에서 생성·형상 검증. 13개 footprint와 높이 유지 확인. 각 GLB 6 draw calls, 0.60MB 미만. editable blend, 재현 입력·레시피, 실제 MCP 기록, 렌더 포함. 사진은 배포하지 않고 URL·SHA256만 기록합니다.
- 검증: representative validator 통과, Node fallback 테스트 2개 및 Python publisher 테스트 2개 통과.
- `completionCredit=false`: 정밀 bespoke 완성 통계에 포함하지 않습니다.

의존성: 이전 PR 브랜치 `feat/apartment-representatives-16`을 base로 합니다. main으로 직접 통합하지 않으며 이 PR은 병합·배포하지 않습니다.

## 원본 및 소유권

Base commit: `1928c5d646958c300f44fae72557a3f97c8e98ca`. Read-only fetched main: `6e8e126c6d608cb26b9d29111abd8a81a02b26b4`. HEAD와 main의 bespoke/reference 및 HEAD representative 자산에서 대상 footprint 중복 없음. 공식 동 수 일치는 개별 동 식별의 근거로 쓰지 않음.

### 금호자이2차

Directly inspected geumho.jpg and both final elevated renders. Photo shows gray-white faces, green-tinted paired glazing, brown blank/core panels and projecting dark rooftop frames. Renders use these choices on all six retained source polygons; reduced mullion width and moved dark roof frames onto long elevations after initial review. Photo has stepped tower cores, balcony rails and a sloped podium absent from the uniform source extrusions. No per-tower identity or exact rear facade is established.

원본 ID: `88a48f97-f28e-46a3-8b2a-3989296d5c68`, `57d45db1-7cbb-4ea5-ace7-f39471e20252`, `b2acb6ed-83ce-4a7c-b76d-13020b136f52`, `e5b58705-f0cf-4afb-bbe0-c5244f22a410`, `b7861cb9-7d1d-4a14-ac89-49ae6e983b1e`, `e0390284-2b26-4848-b532-a9931a9af262`

### 정릉푸르지오

Directly inspected jeongneung.jpg and both final elevated renders. Photo shows cream-white slabs, largely blank numbered end walls with olive lower panels, regular enclosed balcony glazing and olive service boxes. Renders reproduce that palette, lower end-wall panels and flat service-box roofs on all seven source polygons. Visible photo setbacks and pitched/parapet transitions are simplified; source slab heights are retained rather than inferred from perspective. Window rhythm is representative, not an exact count.

원본 ID: `dc477522-cef4-476a-ac31-303f80a24652`, `5312ff88-37e7-48b7-8ef9-be64ba6216d8`, `45673e5d-6871-4f9f-bdb8-9ff59d29abc9`, `c7b1d4e8-8818-4eda-be6d-eb657db34b67`, `6e88dc8f-190f-4a83-a23e-80a19b24a7ad`, `8a0ac172-6d2a-42bb-b468-2622d859625b`, `d00d8637-f8f2-4d4a-a8fb-6caab73e49ec`

## 보류

- A15722108: Source set includes two 5-floor slabs and a 12-floor named 105; photo 105 shows tall continuous balcony stacks. Full phase/massing match unresolved.
- A13524004: Source contains 21-floor building 116 among 15-floor buildings 1/3/5/6; target photo labels 3 and 2. Possible neighboring footprint contamination; complete site held.
- A13922903: No verified target exterior image in researched inputs.
- A15603203: Panorama does not identify which distant cluster is the target; target-specific facade/massing cannot be validated.
