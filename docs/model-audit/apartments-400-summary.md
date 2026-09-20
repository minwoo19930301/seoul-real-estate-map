# 서울 400세대 이상 아파트 개별 모델링 현황

공식 자료 확인일: 2026-09-21. `scripts/build_apartment_bespoke_queue.py`로 생성합니다. **대상 1,417 관리코드, 주거동 전체 검토 완료 7, 미완료 1,410**입니다. 분류 보강 검토 2건과 명시적 비아파트 제외 1건은 큐에 별도로 남깁니다.

## 모수와 중복

[서울시 OA-15818](https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do) 최신 전체 CSV 2,889행을 독립 Sheet totalCount와 대조했습니다. 400세대 이상 아파트 분류는 1,363코드입니다. [국토교통부·K-apt 주간자료](https://www.data.go.kr/data/15073271/fileData.do) 2026-09-18 추출본은 전국 22,547행, 서울 3,335행·고유 3,188코드이고 이 중 대상은 1,385코드입니다. 두 자료의 관리코드 합집합이 대상 모수입니다.

K-apt 서울 자료의 123코드에는 복수 주소 등에 따른 추가 147행이 있습니다. 원본 행 번호와 값은 보존하지만 세대수를 합산하지 않습니다. 서로 다른 관리코드의 동일 주소도 자동으로 같은 단지로 합치지 않습니다. 동일 주소 검토 후보가 있는 큐 기록은 118개입니다. 실제 고유 단지 수는 아직 확정하지 않았습니다.

어느 한 공식 아파트 분류 자료에서 400세대 이상이면 포함합니다. 출처 간 값이 다르거나 서울시 원본이 0이어도 덮어쓰지 않습니다. 메이플자이의 서울시 0/K-apt 3,307, 타워팰리스1차의 0/1,297은 각각 같은 관리코드의 두 근거로 남습니다. 원베일리는 이미 A10023043·2,990세대·23동으로 포함되어 있어 별도 신규 단지로 중복 추가하지 않습니다. 미분류 기록은 이름만으로 아파트로 확정하지 않습니다.

## 완료 기준

관리코드별 명시적인 주거동 목록, 동별 bespoke ID, 실제 사진·배치도 대조 기록, 검토된 원본 GLB SHA, 게시 GLB SHA, 편집 .blend SHA, 실제 MCP 실행 기록 SHA가 모두 일치해야 완료로 계산합니다. 기존 generic/reference 모델, 동일색·높은 삼각형 수, 파일 생성만으로 완료 처리하지 않습니다. 해시 불일치나 사라진 파일은 완료를 자동 해제합니다.

| 관리코드 | 단지 | 상태 | 검증된 bespoke / 확인된 주거동 |
|---|---|---|---:|
| A10020557 | 메이플자이 | partial | 5 / 29 |
| A10023043 | 래미안원베일리 | not_started | 0 / 미확정 |
| A10023083 | 청량리역 롯데캐슬 SKY-L65 | complete_residential_buildings | 4 / 4 |
| A10023188 | 청량리역 한양수자인 그라시엘 | complete_residential_buildings | 4 / 4 |
| A10026988 | 트리마제 | complete_residential_buildings | 4 / 4 |
| A10027908 | 래미안첼리투스 | complete_residential_buildings | 3 / 3 |
| A13527017 | 타워팰리스1차 | complete_residential_buildings | 4 / 4 |
| A13585402 | 타워팰리스2차 | complete_residential_buildings | 2 / 2 |
| A13585403 | 타워팰리스G동 | complete_residential_buildings | 1 / 1 |
| A15805114 | 목동현대하이페리온 | coverage_review_needed | 3 / 미확정 |

타워팰리스·SKY-L65의 완료는 명시된 주거타워에 한정합니다. 공용 저층부·스포츠센터·조경까지 완공 모델이라는 뜻이 아닙니다. 메이플은 일부 사진 대조 개선만 되어 전체 29동 완료가 아닙니다. 하이페리온은 공식 관리단지 2동과 제작한 A/B/C 3타워의 용도 배정 대조가 남아 완료를 보류합니다.

## 위치·자료 한계와 재현

대상 중 19코드는 이전 위치 감사의 해결 좌표가 없습니다. 해결된 좌표도 2026-09-10 당시 관리코드별 대표점이며 건물별 위치·현재 서울 경계 검증을 대신하지 않습니다. 제작 단계에서 원본 건물 윤곽·공식 배치도·동 번호를 별도 확인해야 합니다. 코드와 실제 단지의 대응은 검토된 경우에만 `physicalSiteId`에 기록합니다.

K-apt는 주간 참고 추출물이며 실시간 자료가 아닙니다. 갱신일은 개별 행의 최신성이나 서울 모든 실제 단지의 수록을 보장하지 않습니다. 큐는 대상 확정과 완료 추적을 위한 것으로 도시 전체 모델링 완료 보고가 아닙니다.

고정 공개 입력은 `apartments-400-sources.json.gz`, 명시적 동별 대응은 `apartments-400-coverage.json`, 결과는 `apartments-400-queue.jsonl.gz`와 `apartments-400-summary.json`입니다. 원본 연락처·관리인원·인증 상태·개별 주민 자료는 넣지 않았습니다. 원본 CSV/XLSX 전체는 이 공개 출력에 복사하지 않습니다.

```sh
python scripts/build_apartment_bespoke_queue.py
python -m unittest discover -s tests -p test_apartment_bespoke_queue.py -v
```

새 다운로드를 고정 입력으로 바꿀 때만 `--capture --oa-csv … --oa-count-response … --kapt-xlsx … --kapt-manifest … --checked-on YYYY-MM-DD --oa-updated-on YYYY-MM-DD`를 명시합니다. 기존 source DB·모델·runtime은 수정하지 않습니다.
