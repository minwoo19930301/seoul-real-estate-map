# 아파트 데이터 연결 및 건물 표시 기준

작성: 2026-09-08. 이 문서는 향후 아파트 정보를 수집하고 지도 건물과 연결하기 위한 설계 기준이다. **아파트별 건축물대장·공식 단지 정보의 상세 수집과 연결 검증은 아직 실행하지 않았다.** 일반 건물 외곽선 레이어를 확보했다고 해서 아파트 단지와 각 동의 공식 정보까지 연결된 것은 아니다.

## 단지, 동, 건물 부분의 관계

한 단지는 여러 개별 동을 가진다(1:N). 지도상의 `building_part`는 높이나 형태가 다른 건물의 일부이며, 아파트의 별도 동이나 세대를 뜻하지 않는다. Overture의 `building_part.building_id`는 부모 건물 ID이지 아파트 단지 코드가 아니다. [Overture 건물 가이드](https://docs.overturemaps.org/guides/buildings/)

```text
아파트 단지 complex
  └─ 연결 기록 complex_building_link (동명과 연결 근거)
       └─ 개별 건물 building
            └─ 건물 부분 building_part (0개 이상)
```

단지 경계·관리 단위·건축물대장상의 묶음이 항상 같다고 가정하지 않는다. 다필지 단지, 부속 건물, 명칭 변경, 재건축, 불확실한 대응 관계를 보존하도록 연결 기록을 분리한다. 확정 전에는 후보 연결이며 지도 도형에 공식 단지 코드를 강제로 붙이지 않는다.

## 최소 저장 구조

아래 영문 이름은 이 프로젝트의 제안 필드이며, 외부 API가 모두 같은 이름으로 제공한다는 뜻은 아니다. ID는 선행 0과 긴 자릿수를 보존하는 문자열로 저장한다.

| 테이블 | 최소 필드 | 의미 |
| --- | --- | --- |
| `complex` | `complex_id`, `name`, `reb_complex_id?`, `kapt_code?` | 내부 단지 키와 출처별 단지 식별자. 서로 다른 기관의 코드를 같은 값으로 취급하지 않는다. |
| `building` | `building_id`, `overture_id?`, `bd_mgt_sn?`, `bldrgst_pk?`, `gis_integrated_id?`, `source_building_id?`, `registry_namespace?`, `registry_version?` | 내부 건물 키와 외부 연결 키. 미확인 공식 키는 NULL이다. |
| `building_part` | `part_id`, `source_part_id`, `building_id`, `geometry` | 동일 건물의 부분 도형. 별도 아파트 동으로 집계하지 않는다. |
| `complex_building_link` | `complex_id`, `building_id`, `dong_name_raw`, `dong_name_source`, `match_method`, `match_status`, `checked_at?` | 단지–동 연결의 근거. 이름만 일치한 경우 확정으로 취급하지 않는다. |
| 건물/부분 공통 속성 | `geometry`, `geometry_source`, `geometry_release`, `source_record_id`, `source_updated_at?`, `footprint_area_m2`, `area_method`, `height_raw_m?`, `height_semantics`, `height_source?`, `height_method`, `num_floors?`, `render_base_m?`, `render_top_m?` | 원본 값·계산 결과·표시 값을 구분한다. 자료의 기준일과 취득일도 따로 보존한다. |

주소 연결에는 현재 필지 식별자(PNU), 법정동/지번, 도로명주소와 원문 동명을 보조 필드로 둘 수 있다. 다필지 대응은 여러 행으로 저장한다. 이름이나 단일 좌표만을 영구 건물 키로 사용하지 않는다.

## 공식 연결 키의 범위

- **한국부동산원 단지고유번호**: 기본정보에는 14자리 단지 식별자와 필지고유번호, 출처별 단지명이 있다. 동정보는 이 단지 식별자와 공시가격·건축물대장·도로명주소의 동명, 지상층수를 제공한다. 공개 동정보 표에는 독립 동고유번호나 건축물대장 PK가 없으므로 `단지고유번호 + 동명`만으로 완전한 1:1 연결을 보장할 수 없다. 시점 차이와 미기재에 따른 공란도 공식 안내에 명시돼 있다. [기본정보](https://www.data.go.kr/data/15106861/fileData.do), [동정보](https://www.data.go.kr/data/15106866/fileData.do)
- **K-APT 단지코드**: 공동주택관리정보시스템 가입 단지의 관리 정보를 연결할 때 별도 네임스페이스로 저장한다. 전체 공동주택 또는 개별 건물의 포괄적 식별자로 가정하지 않는다. [국토교통부 공동주택 기본 정보제공 서비스](https://www.data.go.kr/data/15096285/standard.do)
- **건물관리번호**: 도로명주소 체계의 개별 건물 키다. 반면 도로명주소관리번호는 아파트 여러 동이 공유할 수 있으므로 개별 동의 키로 사용하지 않는다. 건물일련번호·건물군일련번호를 쓸 때는 시군구코드와 함께 식별한다. [도로명주소 도움센터 공식 답변](https://eng.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=140043&noticeMgtSn=140043&noticeType=QNA)
- **건축물대장 PK**: 건축HUB 전환에 따른 기존 PK 변경이 공식 안내돼 있다. PK뿐 아니라 제공시스템·스키마/배포 버전과 원본 기록을 보존하고 공식 전환 규칙을 적용한다. [건축HUB 건축물대장정보 서비스](https://www.data.go.kr/data/15134735/openapi.do)
- **Overture ID**: 외곽선과 후속 속성을 연결하는 외부 키다. 한국의 공식 건물관리번호나 아파트 단지코드와 동일하지 않다. 건물 ID와 부분 도형 ID를 구분하며, 수집 release와 feature version을 함께 남긴다. [Overture 건물 스키마](https://docs.overturemaps.org/schema/reference/buildings/building/)

공식 GIS건물통합정보를 추가할 때는 `AL_D010`의 GIS건물통합식별번호(A1), 건축물ID(A19), 참조체계연계키(A21)를 각각 원문으로 보존한다. 이를 도로명주소 건물관리번호나 건축물대장 PK와 같은 값이라고 가정하지 않는다. 최신 컬럼 정의서 확인과 서울 SHP 원본 확보 상태는 [공식 건물 자료 연결 준비](OFFICIAL_BUILDINGS.md)에 별도로 기록돼 있다. 정의서를 확인한 것과 실제 서울 건물 행의 대응을 검증한 것은 구분한다.

연결 순서는 공식 식별자 일치 → 주소·동명·도형의 교차 검토 → 불확실한 후보의 수동 확인으로 한다. 일치율을 높이기 위해 미확정 대응을 조용히 확정시키지 않는다. 단지의 총 동수는 검산 자료이며, 누락된 동의 도형을 임의로 생성하는 근거가 아니다.

## 높이의 의미와 표시

`height_method`는 최소 `reported`, `levels_estimated`, `missing`으로 구분한다. 원본의 숫자 기록이 있다는 사실은 현장 실측 검증이나 독립 정확도 인증을 뜻하지 않는다.

- 원본 높이가 없으면 NULL로 보존한다. 현재 지도는 외곽선만 표시하는 방식을 기본으로 한다.
- 추후 층수로 높이를 추정한다면 사용한 층고·기타 가정과 `estimated_height_m`를 별도 저장한다. 원본 `height_raw_m`를 추정값으로 덮어쓰지 않는다. 실제 층고, 필로티, 지붕 및 기계층 차이 때문에 층수만으로 정확한 높이를 복원할 수 없다.
- 지면 위 건물 높이와 해발고도는 다른 값이다. 건물 높이를 원본 표고점 높이나 클릭 위치의 해발고도로 표시하지 않는다.
- **부분 건물의 높이 기준을 먼저 정규화한다.** 현재 Overture 스키마는 `height`를 최저점–최고점 거리, `min_height`를 지면–바닥 거리로 설명한다. MapLibre의 extrusion height는 지면 기준 윗면 위치다. 전자의 의미가 확인된 데이터라면 `render_top_m = min_height + height`, `render_base_m = min_height`가 된다. 원천 태그가 이미 지면–윗면 값인 경우에는 같은 합산을 하면 안 된다. 수집한 release와 원천 속성의 실제 의미를 확인해 `height_semantics`로 보존한다. [Overture 높이 필드 정의](https://docs.overturemaps.org/schema/reference/buildings/building/), [MapLibre extrusion 속성](https://maplibre.org/maplibre-style-spec/layers/#fill-extrusion)

화면에는 예를 들어 `건물 높이: 원본 기록 / 미검증`, `층수로 추정한 높이`, `높이 미등록`을 구별한다. 지형 강조 배율을 건물 원본 높이나 저장 값에 곱하지 않는다.

## 외곽선 면적과 다른 면적

`footprint_area_m2`는 **지도 도형의 수평 면적**이다. Overture 외곽선은 항공·위성영상에서 추출한 지붕 윤곽일 수도 있으므로, 법정 건축면적과 같은 값이라고 단정하지 않는다. 계산 시 전체 원본 도형과 미터 기반 좌표계/면적 계산 방식을 기록한다. 화면 bbox로 잘린 도형의 면적을 건물 전체 면적으로 저장하거나, 경위도 좌표의 면적을 바로 m²로 표시하지 않는다. [Overture 도형 정의](https://docs.overturemaps.org/schema/reference/buildings/building/)

| 면적 | 지도에서 구별할 의미 |
| --- | --- |
| 외곽선 면적 | 지도상의 footprint/roofprint 도형에서 계산한 수평 면적 |
| 대지면적 | 건물이 놓인 대지에 관한 별도 원본 속성 |
| 건축면적 | 법정 산정 기준을 따르는 건축물대장 속성; 지도 외곽선 면적으로 대체하지 않음 |
| 연면적 | 여러 층의 면적에 관한 별도 원본 속성; 외곽선 면적과 다름 |
| 전용면적 | 개별 세대/호의 면적 속성; 건물 전체 도형에서 산출하지 않음 |

이 문서는 법정 면적을 재산정하는 규칙을 제공하지 않는다. 공식 면적을 추가할 때는 원본 필드명·단위·대상 범위(단지/동/호)를 함께 표시한다. 건축HUB는 표제부, 층별개요, 전유공용면적 등 서로 다른 자료를 제공한다. [건축HUB 서비스 범위](https://www.data.go.kr/data/15134735/openapi.do)

## MapLibre 지형 위 배치와 중복 방지

설치된 MapLibre GL JS **6.8.0** 소스에서 확인한 동작이다. `get_elevation`이 DEM 고도에 지형 강조를 곱하고, extrusion 셰이더는 폴리곤 대표점의 그 값을 건물 윗면·바닥 값에 더한다. 건물 자체 높이는 자동으로 확대하지 않는다. `base=0`에서는 경사면 틈을 줄이기 위해 바닥을 추가로 10m 내린다. 이는 실제 지하층 정보가 아니다.

```text
표시 윗면 = 대표점 DEM × 지형 강조 + render_top_m
표시 바닥 = 대표점 DEM × 지형 강조 + (render_base_m > 0 ? render_base_m : -10m)
```

근거: [지형 공식 명세](https://maplibre.org/maplibre-style-spec/terrain/), 설치 패키지 `node_modules/maplibre-gl/src/shaders/glsl/_prelude.vertex.glsl`의 `get_elevation`, `fill_extrusion.vertex.glsl`의 terrain offset 계산. 공식 저장소 대응 경로는 [extrusion 셰이더](https://github.com/maplibre/maplibre-gl-js/blob/v6.8.0/src/shaders/glsl/fill_extrusion.vertex.glsl)이며, 이번 확인은 로컬 설치 소스 기준이다.

- DEM 고도를 `render_top_m`에 미리 더하면 지형 고도가 이중 적용된다.
- 대표점 하나에 맞춰 세우므로 급경사·넓은 동·타일 경계에서는 부유·매몰·높이 단차가 생길 수 있다. 특히 높은 강조 배율에서 실제 화면 확인이 필요하다. 현재 보간 DEM은 아파트 대지 단차, 옹벽, 교량 상판을 실측 복원한 모델이 아니다.
- 지형 원본의 수직 기준과 정확도는 아직 독립 검증되지 않았다. 실측 건물 높이를 확보해도 자동 배치된 바닥의 해발고도까지 검증되는 것은 아니다.
- 부모 건물과 상세 `building_part`를 동시에 전체 높이로 extrude하면 중복된 덩어리가 생길 수 있다. 유효한 부분 도형을 사용할 때 부모의 전체 덩어리를 억제하는 정책을 명시한다. 부분 누락·높이 미등록·조회량 제한 때문에 부모만 사라지는 경우도 함께 처리한다.
- `has_parts=true`라는 표식만으로 모든 부분이 현재 응답에 들어 있다고 가정하지 않는다. 부분 조회가 잘리면 표시 완전성 상태를 알려야 한다. 건물 개수는 부모 건물 수와 부분 도형 수를 구별해 집계한다.

## 후속 검증 항목

1. 한 단지의 여러 동이 각기 다른 건물 식별자로 연결되는지, 동일 동의 건물 부분이 별도 동으로 집계되지 않는지 확인한다.
2. 기록 높이·층수 추정·높이 없음 세 사례와 `min_height > 0` 사례를 원본 속성과 대조한다.
3. 전체 도형 면적, 좌표계, 단위와 화면 bbox 클리핑 여부를 확인한다.
4. 부모/부분 중복과 부분 누락, 조회 제한, 아파트 필터 적용 시 표시가 일관적인지 확인한다.
5. 건물 선택 직후 다른 건물/표고점을 선택했을 때 늦게 도착한 응답이 새 상세 패널을 덮어쓰지 않는지 확인한다.
6. 2D/2.5D와 지형 강조 변경 후에도 원본 높이·저장 좌표가 유지되는지 확인한다.

이 목록은 다음 개발·검증의 기준이며, 아파트 상세 수집이나 위 항목이 이미 완료됐다는 의미가 아니다.
