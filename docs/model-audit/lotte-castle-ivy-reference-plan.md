# 여의도 롯데캐슬아이비 — 개별 재제작 사전 조사

확인일 2026-09-21. **400세대 조건 충족. 아직 모델 제작·게시하지 않았으며, 현재 외관까지 재현할 준비가 모두 끝났다는 뜻은 아니다.** 이번 작업은 관리코드·용도·원본 윤곽과 사진/설계 자료의 구분까지다.

## 대상과 세대수

- 관리코드 `A15088915`, 기존 fallback `apt-a15088915`.
- 도로명: 서울특별시 영등포구 국제금융로 86. 건축물대장 대표지번: 여의도동 43-4.
- 최신 고정 큐 `docs/model-audit/apartments-400-queue.jsonl.gz`에서 `eligible`: OA-15818 원본 951행과 K-apt 주간 원본 2216행 모두 **주상복합·445세대·2동**. 두 값을 더하지 않았다. K-apt 추출 기준 2026-09-18, 큐 확인일 2026-09-21.
- [서울시 공동주택 통합정보마당의 해당 관리코드](https://openapt.seoul.go.kr/commonPortal/programLink.do?aptCode=A15088915&codParams=&jspNm=%2FopenApt%2FdMenu%2FdangiInfo%2FdangiInfo.open&tr_code=sweb)를 다시 열어 주소·2동·445세대를 확인했다.
- 모수 원자료: [서울시 OA-15818](https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do), [K-apt 공동주택 단지정보](https://www.data.go.kr/data/15073271/fileData.do).
- 정확 주소의 서울시 건축물대장도 주용도/기타용도 **공동주택**, `세대수=445`, `호수=98`로 구분한다. **445에 98을 합산하지 않는다. 98을 오피스텔 세대수라고 판단할 근거도 확보하지 못했다.** 오피스텔을 합쳐 400을 넘긴 단지가 아니다.

## 대장: 동별 값으로 잘못 분할하지 않기

로컬 읽기 전용 DB `data/model-source/residential-survey/register.sqlite`, `reg`:

```sql
SELECT id, parcel_key, road_key, building_dong, main_use, other_use,
       floors, basement, height, households, approval_year, source_hash, raw_json
FROM reg
WHERE parcel_key IN ('영등포구|여의도동|land|43|4',
                     '영등포구|여의도동|land|43|5');
```

반환은 **통합 1행**이다. `building_dong`이 공란이므로 101/102의 개별 표제부를 얻은 것으로 표현하면 안 된다.

| 대장 항목 | 원본 값 |
|---|---|
| ID / CSV 원본행 | `102017214` / 563717 |
| 주/부속·용도 | 주건축물 / 공동주택 |
| 지상 / 지하 | 35 / 6층 |
| 높이 | 112.25m |
| 세대 / 호수 | 445 / 98, 별개 필드 |
| 구조 / 지붕 | 철골철근콘크리트 / (철근)콘크리트 |
| 사용승인 | 2005-12-30 |
| 원본행 SHA256 | `f385996586608124d068f2d8f2be48c1b892485f012a5e2c07dc6c6bf7ebba29` |

[서울시 OA-22424](https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do) CSV `data/sources/seoul-building-register-2026-09-08.csv`, SHA256 `ba00150bbc9b2343fd2ba2fbaaa0c723df7d5dabbbd820345a405e9aaa5162aa`. 수집 감사는 `docs/REGISTER_CSV_AUDIT.md` 및 `data/model-source/residential-survey/register-index-audit.json`.

112.25m는 대장의 단일 높이이며 옥탑·안테나 최고점 또는 두 동별 최고점이 각각 실측 확정된 값이 아니다. 건축사 페이지의 39F/B6·2006 완료는 이 대장의 35F·2005 사용승인과 다르다. 설계/완료 단계 차이일 수 있지만 원인을 확인하지 못했으므로 병기한다. 웹 재가공자료의 동별223/222세대 값은 원대장을 확보하지 못해 제작 확정값으로 사용하지 않는다.

## 동 번호와 기존 윤곽

`data/buildings.sqlite`의 기존 OSM/Overture 원본을 읽었다. 동 번호는 원본 `names.primary`에 있으나 공식 동별 표제부로 재검증한 것은 아니다. 좌표는 원본 경위도 bbox 중심으로, 측량된 출입점이 아니다.

| 대상 | source footprint / OSM | 후보 앵커 lon, lat | 근거·주의 |
|---|---|---|---|
| 북서쪽 101동 | `a3286371-f291-40a6-9d11-140aaf7e3294`, `w681799363@3` | 126.9315588, 37.52040565 | 이름101동, 1507.47㎡, source height112m/min_height8m, num_floors33/min_floor2 |
| 남동쪽 102동 | `da0687ee-3cb2-478b-956d-0247418f90ef`, `w681799368@3` | 126.9319824, 37.51998665 | 이름102동, 1396.50㎡, 같은 source height/min_height/floors |
| 두 동 사이 낮은 연결체 후보 | `2d174f84-d1c6-47b2-bce2-9759575b439d`, `w681799360@2` | 126.9317762, 37.52018955 | 무명197.85㎡, source height30m/min_height8m, 8층. 제3주거동으로 세지 않는다. |

원본 OSM 높이 상태는 `source-reported-unverified`; 공식 대장의 35층과 OSM의 min_floor2/num_floors33 관계도 규칙만으로 확정하지 않는다. OSM 출처 [101](https://www.openstreetmap.org/way/681799363), [102](https://www.openstreetmap.org/way/681799368), [연결체 후보](https://www.openstreetmap.org/way/681799360). 원본 라이선스 ODbL-1.0. 주변 상업 건물이나 전체 공유기단의 소유권은 위 세 ID만으로 자동 확대하지 않는다.

## 실제로 열어 본 설계 자료와 완공사진

### 건축사 직접 게시: 배치도 1장과 CG 2장

[최신공법건축사사무소 Lotte Castle Ivy 프로젝트](https://choeshincm.com/residential/?bmode=view&idx=167044842). 페이지 텍스트는 Seoul·445 households·39F/B6·Completion2006. 이미지 제작일/촬영일 미표기. 세 파일을 내려받아 이미지뷰어로 각각 확인했다.

- [배치도 e5eb76c83a9f9.jpg](https://cdn.imweb.me/upload/S202502034e772ef8f38f0/e5eb76c83a9f9.jpg): 북쪽 화살표, 35m 도로 두 면과12m 도로, 두 대형 타워, 중앙 연결체, 공용 저층부, 양쪽 차량 진출입, 공동주택/판매시설 별도 출입, 선큰과 지붕 H 표시가 보인다. 동 번호나 축척은 없다. 영상 북쪽이 화면좌상향이므로 화면좌우를 지리 동서로 바로 쓰면 안 된다.
- [원경 CG 7cef5e9cdca03.jpg](https://cdn.imweb.me/upload/S202502034e772ef8f38f0/7cef5e9cdca03.jpg): 양쪽 비슷한 타워이지만 계단식 후퇴 상부, 톱니형 전면 돌출, 낮은 중앙 연결부, 공용 유리기단, 돌출 입구 캐노피를 표현한다.
- [하부 시점 CG 3c98775090827.jpg](https://cdn.imweb.me/upload/S202502034e772ef8f38f0/3c98775090827.jpg): 세로 파인 슬롯, 꺾인 입면과 여러 겹 처마선, 연결부의 구조 프레임이 구분된다.

**CG 두 장은 실제 준공사진이 아니다.** 과장된 수평 흰 띠, 안테나, 옥탑 형상을 그대로 완공 현황으로 옮기면 안 된다. 설계도는 자료 출처가 명확한 형상 후보지만 준공도/as-built라는 표시도 없다.

### 실제 운영 참여사 직접 게시 완공 외관

[서운에스티에스/SEANTECS 스포츠센터 운영 실적](https://www.seantecs.co.kr/en/project/project.aspx?CODE=pm), 해당 프로젝트30. [실제 외관 PNG](https://www.seantecs.co.kr/upload/project/%EB%A1%AF%EB%8D%B0%EC%BA%90%EC%8A%AC%EC%95%84%EC%9D%B4%EB%B9%84_%EC%99%B8%EA%B4%80.png)를 직접 열었다. 실적 상세는 발주처 롯데건설/조합, 사업 시작2005-12를 기재한다. 페이지 상세 자료 수정일2024-10-22는 사진 촬영일이 아니다. 주소43-1 표기는 공식 대표지번43-4와 달라 좌표 근거로 사용하지 않는다.

440×447px의 지상 저각 사진이다. 녹청색 유리, 촘촘한 수직 프레임, 일부 굵은 흰 수직대, 각진 전면 돌출과 상층 계단형 후퇴, 진회색 저층 석재·유리 경계가 실제로 보인다. CG처럼 강한 흰 수평 띠만 두르는 건물은 아니다. 전경타워의 최고 옥탑이 잘려 있고 뒤쪽 동은 가려지므로 양쪽 크라운·후면 전체·동 번호·현재 도장색까지 확정하지 못한다.

롯데건설/롯데캐슬 본사 도메인을 별도로 검색했으나 이 단지의 직접 게시 완공 전경과 번호가 있는 준공 배치도는 이번 조사에서 확보하지 못했다. **운영사 사진을 건설사 사진이라고 바꿔 쓰지 않는다.** 검색에서 나온 이름 유사한 엠파이어/골드/헤론은 다른 단지로 제외했다.

임시 열람 파일은 `/tmp/lotte-ivy-research/{architect.html,7cef5e9cdca03.jpg,3c98775090827.jpg,e5eb76c83a9f9.jpg,operator-exterior.png}`. 사진·설계도 재배포 허가를 확인하지 못했으므로 Git/GLB/.blend에 포함하지 않는다. 이 문서는 원문 링크와 관찰만 보존한다.

## 다음 제작의 구체적인 범위와 선행 확인

1. 두 타워를 각자 원본 윤곽에 맞추고, 계단식 상층 후퇴·각진 톱니형 돌출·세로 슬롯·유리/불투명 띠를 동별로 재작성한다. 공통 사각기둥 두 개로 대체하지 않는다.
2. 배치도의 북쪽 방향과 두 도로 교차부를 실제 source footprint/도로와 대조해 최소3개 제어점으로 정합한다. 배치도에 동 번호가 없으므로 OSM101/102 배정은 공식/현장 표지로 보강한다.
3. 미확인 동별 대장, 높은 부분과 낮은 부분의 층수, 최고 옥탑 높이와 안테나 존치 여부를 분리해 확인한다. 통합112.25m를 모든 부분의 높이로 사용하지 않는다.
4. 실제 전경의 반대쪽·크라운·중앙 연결체·상가기단 사진을 추가 확보한다. 지금 한 장의 잘린 완공사진만으로 CG 전체를 최신 완공형상으로 승인하지 않는다.
5. 두 주거타워와 확인된 중앙 연결체/저층부는 별도 component coverage로 기록한다. 기본 주거동 수는2, source polygon 수3을3개 주거동으로 바꾸지 않는다. 지하6개층을 지상으로 모델링하지 않는다.
6. 기존 `apt-a15088915` 전체 fallback은 필요한 두 동 및 합의된 연결체가 준비된 뒤에만 함께 교체한다. 현재 원본 모델·manifest·큐 완료상태는 변경하지 않았다.
