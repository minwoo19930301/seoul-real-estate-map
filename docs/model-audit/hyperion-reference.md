# 목동 현대하이페리온1차: 사진 기반 개별 재제작

검토일2026-09-20. 기존 `reference-flight-hyperion`과 `apt-a15805114`의 게임용 상대배치·검은 가로띠를 교체할 근거와 제작 기록이다. SKY-L65의 여섯 팔 평면·짙은 유리 입면을 재사용하지 않는다. 하이페리온은 별도의 흰 수평 구조 프레임, 청회색 커튼월, 중앙 석재 벽, 흰 대각선 보강띠와 벌어진 크라운이 핵심이다.

## 직접 확인한 근거와 충돌

| 출처 | 확인 사항 | 시기·한계 |
|---|---|---|
| [현대건설 공식 기사](https://newsroom.hdec.kr/kr/newsroom/news_view.aspx?NewsListType=inter_list&NewsSeq=1120&NewsType=JOURNAL) | 최고69층·256m·2003년 준공. 실제 사진에서 세 타워 높이 차이, 흰 골조와 대각 보강부, 돌출 옥탑·벌어진 기둥 확인. | 기사2024-08-27. 사진 촬영일 미공개. 노을 보정 사진이라 정확한 재료색 추출에는 쓰지 않음. |
| [시공 참여 커튼월 컨설턴트 Summit Facade](https://www.sfacade.net/dongtan-hyperion) · [실제 주간 사진](https://static.wixstatic.com/media/90ddf2_d316ae4e030a46f1b011424d70f6c182~mv2.jpg) | 규모69/59/54층. 실제 저각 사진에서 크림색 프레임·옅은 청회색 유리·중앙 석재벽, 길게 열린 주차층 슬롯, 상부 조경이 있는 포디움 확인. | 프로젝트기간2001–2003. 게시·촬영일은 미공개. 페이지의 지역 표기 Kyunggi는 목동 위치와 불일치하므로 지리 근거로 쓰지 않음. |
| [구조설계 참여자 CTBUH2004 논문](https://global.ctbuh.org/resources/papers/1651-Chung_2004_StructuralDesign.pdf) | Table7: A254m69층/B216m59층/C200m54층. 아웃리거 A9·32·50층, B/C9·32층. L형9개 층 포디움. | 준공 직후 설계 참여자 자료. 검색 도구의 원문 텍스트는 열람됐으나 직접 PDF 다운로드는404. 그림2 평면도를 눈으로 본 것처럼 주장하거나 이를 trace했다고 기록하지 않음. 초록의 C189m와Table7의200m도 서로 다름. |
| [서울시정개발연구원2010 연구](https://www.si.re.kr/sites/default/files/2010-PR-01_0%20(s).pdf) | 표2-7은 A69/B59/C54층을 기재한다. | 현행 건축물대장을 새로 조회한 자료는 아니지만 참여 업체의 층수와 일치한다. |
| [CTBUH B동 데이터베이스](https://www.skyscrapercenter.com/building/mokdong-hyperion-tower-b/1008) | 239.3m·63층으로 다른 참여자 근거와 충돌. | 기존 OSM B239m63층을 확정 사실로 승격하지 않고 충돌로 남김. |
| [CTBUH C동 데이터베이스](https://www.skyscrapercenter.com/building/mokdong-hyperion-tower-c/1633) | 건축 상부 기준201.2m·54층. | 설계 논문200m와 장식 상부/기준고 차이 가능. 원대장의 최고높이 검증은 아님. |

아파트466세대는 기존 서울시 공동주택 원천 레코드 `A15805114`의 수치다. 별도 오피스텔을 합쳐 세 타워 전체466세대라고 표현하지 않는다. 이번에는 아파트 세대수 원천 API를 다시 내려받지 않았다.

## 동별 위치와 높이 결정

각 named OSM 원천 외곽의 중심과 회전을 로컬 SQLite에서 읽었다. C동을 게임 모델 안에 있는 남쪽 타워의 상대좌표로 옮기는 방식은 폐기한다. source 외곽은 단순한 사각형이므로 중심·방위·전체 폭의 근거이며 실제 건축 평면과 동일하다고 주장하지 않는다.

| 동 | 중심 경도, 위도 | 회전 | 적용 층수·전체 높이 | 소유 source ID |
|---|---|---:|---|---|
| A |126.87545148373547,37.527128592512206|−11.22°|69층·256m|`d17a295c-c15f-459a-99f0-78bd56c3155b`|
| B |126.87464809063884,37.52727713855758|−10.07°|59층·216m|`070fa936-533e-4489-8ed1-2b391e7cd6b4`|
| C |126.87445787138337,37.52654683472358|−10.48°|54층·201.2m|`7b59ea22-2e4d-41cb-a79b-c2893081c113`|

B216m는 설계 참여자 기록을 우선한 선택이며, 장식 옥탑 포함 최고높이는 미확정이다. 모델의 상부까지216m로 맞추고 이 한계를 메타데이터에 넣는다. 239m와216m를 근거 없이 혼합하거나59층을63층으로 늘리지 않는다.

## 구성

각 타워는 단면 모서리가 깎인 주거부, 수평 층 프레임·기둥, 청회색 창호의 세부 분할, 중앙 석재 수직축, 흰 대각선 벨트, 단차 있는 펜트하우스·벌어진 옥탑으로 나뉜다. A는 세 벨트, B/C는 두 벨트이며 상부 너비·단차·기둥 수와 층수에 차이를 둔다. 원거리에서 검은 띠를 두르는 대신 보강부의 흰 삼각형이 보여야 한다.

옥탑은 중앙 설비실을 둘러싼 열린 기둥 열과 바깥으로 벌어지는 기둥 상단, 얕은 이중 코니스로 구성한다. 입면의 폭·유리 밝기·코니스 치수는 두 실제 사진의 비율로 수동 추정했다. 설계자가 작성한 치수 CAD를 확보한 것은 아니다. 층고도 포디움 상부와 옥탑 하부 사이를 보간했으며 벨트의 층 번호와 절대 높이 정확도는 구분한다.

L자 주차 포디움은 별도 GLB다. 설계 참여 논문의 L형 설명, 시공사 사진의 열린 주차 슬롯·긴 수평 석재·상부 조경에 근거한다. 세 동 원천 중심을 연결한 구간에서 외곽을 추정했으며, 현대백화점 원천 polygon `c7f66902-54ea-4bac-ae09-73a57bdf98b7`은 차집합으로 제거했다. 교차 면적0m²를 확인했다. 포디움은 **빈 footprintIds**를 사용해 타워 또는 백화점의 원천 건물을 대신 숨기지 않는다. 이웃 CBS·현대41타워도 소유하지 않는다.

## 제작·검증 자료

- 입력·좌표·근거: `data/model-source/bespoke/hyperion/recipe-input.json`, `claimed-source-buildings.json`.
- 단지 전용 작성 코드: `scripts/bespoke/hyperion_prepare.py`, `hyperion_blender.py`.
- 실제 Blender MCP: 전용9877포트의 `execute_blender_code`; 기록 `mcp-build.json`.
- 편집 원본: `hyperion-authored.blend`. 사진 원본은 `/tmp/hyperion-reference/` 열람용이며 blend와 배포 GLB에 넣지 않는다.
- 검토 렌더: `review-southwest.png`, `review-northeast.png`, `review-plan.png`, `review-A-crown.png`, `review-podium-front.png`, `review-A-braces.png`; 실제 viewport는 별도로 캡처한다.
- 통합용: `bundle.json`; 개별 좌표·소유 ID·원본·추정 항목·해시·삼각형 수 포함. 배포 manifest와 실행 코드는 상위 작업에서 별도로 통합한다.

```sh
.venv/bin/python scripts/bespoke/hyperion_prepare.py
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute \
  --port 9877 --script scripts/bespoke/hyperion_blender.py \
  --record data/model-source/bespoke/hyperion/mcp-build.json
```

재생성 시 무시되는 작업 폴더에 입력이 없으면 `modeling/bespoke/hyperion/`의 보존 입력을 읽는다. 실제 지도의 지면 높이, 옛 모형 제거, 백화점·주변 건물 복구와 위치 차이는 통합 후 브라우저에서 확인해야 한다.

2026-09-20 제작 검토 완료: 실제 MCP로 A/B/C와 별도 포디움4GLB 및 편집 가능한 `.blend`를 생성했다. 첫 렌더에서 프레임이 중앙 석재면을 가리고 옥탑 안쪽이 지나치게 비어 보이는 점을 수정했다. 최종 두 전경·평면·A동 옥탑과 실제 MCP viewport를 직접 열어 보았고, 중앙 석재축·흰 대각 벨트·낮고 높은 세 동·L자 주차층이 구분된다. 현장 측량 수준의 평면 재현은 아니며, 특히 모서리 굴곡과 옥탑 치수는 사진 추정이다.

총143,758 triangles·8,360,652 bytes. A52,028/B47,592/C38,252/포디움5,886 triangles다. 모든 GLB의 지면 최저Y는0, 파일 구조·유한 좌표·실제 삼각형 수·SHA·원본 사진/카메라 미포함 검사를 통과했다(`glb-check.json`). 포디움 주변 API 건물 외곽을 추가 조사해 A/B/C를 제외한 다른 원천 건물과1m²를 넘는 교차가 없음을 확인했다(`podium-neighbor-check.json`: 빈 목록). 공개 지도 검증과 배포는 별도 단계다.

## 사진 재대조 후 입면 교정

현대건설의 전경 사진과 컨설턴트의 주간 사진을 다시 직접 열어 비교한 뒤, 중앙 석재축 폭을 A8.0→10.4m, B9.2→11.4m, C7.2→9.3m로 넓혔다. 정면 폭의 약1/4을 차지하는 넓은 석재면이 창 프레임과 따로 읽히도록 한 사진 비율 추정이며, 실측 치수는 아니다. 대각 벨트는 약6.8m마다 반복하던 작은 V를 제거하고 중앙 석재축 양쪽 날개마다 넓은 삼각형 하나를 배치했다. 모따기 면에는 별도 삼각형을 남긴다. `review-A-braces.png`에서 창 여러 칸을 가로지르는 큰 구조 구간과 석재축이 구분되는 것을 확인했다.

컨설턴트 사진의 포디움은 모든 면이 동일한 슬롯이 아니다. 넓은 석재 끝벽의 사각 패널, 긴 주차 슬롯을 끊는 세로 유리 계단 구간, 주차 개구부와 다른 최상부 연속 유리 띠를 각각 분리해 모델링했다. 포디움 입력의 `facadeInterpretation`에 A동 동쪽 끝벽·남쪽 연결 구간의 적용 위치를 명시했다. 사진 자체의 촬영 좌표가 없으므로 이 면 배정은 사진과 단지 위치의 해석이며, 조사된 입면 방향으로 주장하지 않는다. 보이지 않는 나머지 면은 추정이 남는다. 최종 `review-podium-front.png`를 직접 열어 넓은 석재면, 사각 음각 표현, 세로 유리 구간, 상부 띠가 분리되어 보이며 모서리 검은 틈이 제거된 것을 확인했다.

수정은 개별 앵커·층수·전체높이·외곽 소유권을 유지한다. 최종 MCP 실행, viewport/scene 정보, 편집 가능한 원본과 6개 렌더를 갱신하고 4개 GLB의 SHA·삼각형 수·유한 좌표·최저Y0 검사를 다시 통과했다. 원본 사진은 계속 모델에 포함하지 않는다.

## 백화점 외곽에 잘못 적용된69층 모델

통합 지도에서 발견한 약210m짜리 큰 상자는 `survey-upis-32702773`이다. UPIS `현대하이페리온`의 복합용도 레코드에서69층을 가져와 추정 층고3.05m를 곱한210.45m 모델이며, 실제 외곽은 독립된 현대백화점 쪽이다. 로컬 선정 원천 SQLite의 polygon을 미터 좌표로 비교한 결과 A/B/C와 교차0m², 백화점 원천 `c7f66902-54ea-4bac-ae09-73a57bdf98b7`과4541.57m²(조사 외곽91.074%, 백화점 외곽84.953%)가 겹친다. 세 타워와의 최소 간격은 A11.63m/B18.01m/C6.53m다. 동별 대체 footprint ID는 발견되지 않았다. `survey-overlap-review.json`에 원천 외곽·분류·공간 비교를 남겼다.

[현대백화점 공식 목동점 층별 안내](https://www.ehyundai.com/newPortal/DP/FG/FG000000_V.do?branchCd=B00142000)는 지상1–7층을 표시한다. 이는69층을 백화점에 적용한 오류를 확인하는 근거이며, 건물의 실제 미터 높이를 제공하지는 않는다. 백화점 원천의 OSM 레코드는 `w254292805@10`, 부모 없음·자식 없음·높이/층수 미등록이다. 로컬 API도 `extrude=false`, `height_status=missing`, `display_top_m=null`을 반환했다. 따라서 잘못된 조사 모델을 제거해도 원래 백화점의3D solid가 복구된다고 주장할 수 없다. 원천 평면 외곽은 그대로 유지된다.

포디움의 `supersedes`에만 이 잘못 생성된 조사 모델 ID를 명시한다. 이는 부정확한 단지 공통 높이를 적용한 모델의 억제이며, 포디움이 백화점의 소유권을 가진다는 뜻이 아니다. 포디움 `footprintIds`는 계속 빈 배열이고, A/B/C는 기존 세 UUID만 소유한다. 기존 reference의 네 외곽을 일괄 상속하지 않는다. 실제 미터 높이나 별도 상업건물 모델은 추가 근거가 필요한 독립 작업이다.

## 별도 백화점 본관 모델 추가

위의 높이 오적용을 제거한 뒤 백화점을 빈 공간으로 남기지 않기 위해, [현대백화점 공식 목동점 페이지](https://ehyundai.com/newPortal/DP/DP000000_V.do?branchCd=B00142000)의 [실제 전경 사진](https://ehyundai.com/attachfiles/branch/8b29c131d8cc4e8787576fcc65c00ae2.png)을 직접 열어 다섯 번째 모델 `bespoke-hyperion-department-store`를 별도로 만들었다. 사진 촬영일은 미공개이며 현재 공식 페이지에서2026-09-20확인했다. 남쪽5개·동쪽3개 아치와 원형 창, 긴 청록색 상부 유리띠, 밝은 석재 벽, 여러 겹 돌출 코니스, 남동쪽 사선 입구 벽의 액자와 삼각 시계 페디먼트·기둥 입구를 직접 형상화했다. 광고 포스터는 무문양 단색으로, 작은 문자·조각 장식은 생략했다. 원본 사진은 배포하거나 텍스처에 넣지 않았다.

백화점만 `c7f66902-54ea-4bac-ae09-73a57bdf98b7`을 소유한다. 중심은126.87524759969328,37.52652000185615, 회전−10.296981°다. 외곽은 기존 UPIS32702773의 남동쪽 사선 모서리까지 추적하되 잘못된69층 속성은 사용하지 않는다. OSM의 이름·원천 중심은 건물 식별·앵커에 쓰고, 두 데이터의 외곽 차이를 입력에 남겼다. 새 백화점 외곽과 기존 주차 포디움의 교차는0m²다.

공식1–7층 안내와 사진 비율에 따라 주 코니스34.5m·높은 모서리38.5m를 수동 추정했다. 돌출 몰딩을 포함한 최종 GLB 최고점은38.695m다. **실측 또는 건축물대장 높이가 아니다.** 사진에 보이지 않는 북·서측 서비스 입면과 옥상은 단순화했다. 백화점 모델을 더했으므로 전체 bundle의 `retainedUntouchedSourceFootprintIds`는 빈 배열이지만, 주거동·포디움 소유권 자체는 바뀌지 않았다. `reference-flight-hyperion`과 `survey-upis-32702773`을 새 백화점도 교체 대상으로 기록해 옛 복합 모델과 혼합되지 않게 한다.

기존4GLB의 바이트·SHA는 유지했다. 새 백화점은5,311삼각형·289,008바이트이며 전체5GLB는149,069삼각형·8,649,660바이트다. `glb-check.json`으로5개 파일의 최저Y0·유한좌표·삼각형수·해시·이미지/카메라 미포함을 확인했다. `review-department-front.png`, 공식사진과 비슷한 낮은 남동쪽 시점 `review-department-source-view.png`, 전체 `review-with-department.png`를 직접 열어 확인했다. 별도 실제 실행 기록 `mcp-department-build.json`과 viewport/sceneinfo를 보존하며, 기존4개 제작 기록 `mcp-build.json`을 덮어쓰지 않았다. 편집 원본에는 독립 백화점 컬렉션을 추가했다.

재생성은 먼저 기존 하이페리온 준비·제작을 실행하고, 같은 Blender 장면에서 아래 추가 제작을 실행한다. 현재 장면이 다르면 `hyperion-authored.blend`를 선행 MCP 호출로 연 뒤 실행해야 한다. `department-recipe.json`을 함께 보존한다.

```sh
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute \
  --port 9877 --script scripts/bespoke/hyperion_department_blender.py \
  --record data/model-source/bespoke/hyperion/mcp-department-build.json
```
