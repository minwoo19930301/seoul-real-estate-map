# 도곡 타워팰리스 A–G 개별 재제작

범위는 타워팰리스 1·2·3차의 **주거 타워 일곱 동**이다. 서울 전체 모델링 완료나 건축 실측 복원을 뜻하지 않는다. 기존 게임 모델의 타원형 G동, 원뿔 옥탑, 반복되는 공통 입면을 재사용하지 않고 SAMOO 완공 사진, SWA 문자 표기 배치도, 이름이 확인되는 개별 OSM 윤곽을 대조해 Blender에서 제작했다.

## 출처와 확인 범위

|자료|확인한 사항|한계|
|---|---|---|
|[SAMOO 1차](https://www.samoo.com/home/works/view.do?cntntsSn=59), 사진 `seq=3,4,5`|2002년, 59·66·59·42층, 직사각 몸체, 폭넓은 수평 창 띠, 안뜰 면의 중앙 유리 슬롯과 석재 기둥, 중간층 열린 공간, 후퇴한 거주 펜트하우스와 평지붕|사진 촬영일과 입면 실측 치수는 공개되지 않음|
|[SAMOO 2차](https://www.samoo.com/home/works/view.do?cntntsSn=60), 사진 `seq=3,5,9`|2003년, 55층 두 동, 각진 함몰 입면, 단계별로 다른 날개 높이, 굵은 흰 수평 띠, 삼각형 열린 지붕 프레임, 금속 아치|E/F의 가려진 면별 지붕 높이 배정은 사진 해석|
|[SAMOO 3차](https://www.samoo.com/home/works/view.do?cntntsSn=61), 사진 `seq=3,4,5,6,11`|2004년, 69층, 공식 설명의 세 갈래 Y형 평면, 높이가 다른 날개와 수직 핀, 푸른 커튼월, 깊은 루버 면, 녹색 석재 저층부|날개별 높이, 지붕 안쪽 설비 치수는 미공개|
|[SWA 프로젝트 시트](https://swacdn.s3.amazonaws.com/1/988ea28b_towerpalace.pdf)|원본 내 445×311 배치도에 A–G 문자 표기. 3개 블록과 4+2+1 동 배치 확인|측량도 아님. 소개문 `three towers`를 동 개수 근거로 쓰지 않음|
|[CTBUH/CVU 단지 목록](https://www.skyscrapercenter.com/complex/215)|A/C 209m, B 234m, D 153m, E/F 191m, G 264m와 동별 차수|A/C·D의 OSM 211/154m와 높이 기준면 차이는 해결되지 않음|
|[삼성물산 시공 기록](https://www.secc.co.kr/ko/business/portfolio/housing/124)|상세 설명의 1차 4동·1,297세대, 3차 1동·480세대, 공사 시기|상단 요약의 2차/3차 표기 혼동을 그대로 전파하지 않음|

공식 사진 주소 형식은 `https://www.samoo.com/home/works/content/download.do?seq=3&cntntsSn=59`이며 차수와 사진 번호는 위 표와 `recipe-input.json`에 명시했다. 실제 사진을 직접 열어 형태를 비교했다. 원본 사진은 검토용 임시 폴더에만 두며 `.blend`, GLB, 배포 폴더에 포함하지 않는다.

## 일곱 동의 소유권

모든 새 모델은 `reference-flight-tower-palace`를 함께 대체한다. 단지 전체를 일곱 GLB로 완성한 뒤 통합해야 한다. 하나만 준비하거나 로드된 상태에서 이전 일곱 동 전체를 없애면 안 된다.

|새 ID 접미사|동/차수|높이·층수|단독 소유 source footprint|추가로 대체하는 기존 GLB|
|---|---|---|---|---|
|`-a`|A / 1차|209m · 59F|`9197849d-bf83-4832-9abe-0e78bd90981c`|`residential-9197849d-bf83-4832-9abe-0e78bd90981c`|
|`-b`|B / 1차|234m · 66F|`995d5ddd-41d8-44aa-89d0-78b5b8207de6`|`residential-995d5ddd-41d8-44aa-89d0-78b5b8207de6`|
|`-c`|C / 1차|209m · 59F|`2d2c76d4-7f8d-48f7-895a-eb2cd30da173`|`residential-2d2c76d4-7f8d-48f7-895a-eb2cd30da173`|
|`-d`|D / 1차|153m · 42F|`acdd801b-57dc-4384-b867-3cef5d194fa9`|`apt-a13585403`|
|`-e`|E / 2차|191m · 55F|`0aa4cf05-c633-4f2b-83c5-604b8629272d`|`apt-a13585402`|
|`-f`|F / 2차|191m · 55F|`c6873a11-88e5-4129-bc93-19bc68cd7bd5`|`apt-a13585402`|
|`-g`|G / 3차|264m · 69F|`0279553d-08e7-48de-bd31-6016d2b5445c`|`apt-a13585403`|

ID 전체 접두사는 `bespoke-tower-palace`다. 기존 `apt-a13585403`은 이름과 달리 G와 D를 같이 소유했으므로 새 D/G 모두 그 잘못 묶인 GLB를 대체하지만, 새 모델의 지도 윤곽 소유권은 각각 한 개뿐이다. 3차 스포츠센터, 도로, 공용 상가·조경 포디엄을 근접했다는 이유로 소유하지 않는다. 타워 개수는 footprint 개수가 아니라 이름이 명시된 CTBUH 목록과 건축가의 4+2+1 구성으로 확인했다.

## 개별 형상 판단

1차 A–D는 서로 다른 source 치수·각도와 높이를 적용한다. 바깥 면의 큰 수평 창 띠와 안뜰 면의 중앙 슬롯을 구분했다. 안뜰 방향은 배치도와 사진을 대조해 A/B WSW, C NNW, D ENE로 해석했다. 이 면에서만 두 돌출 석재 기둥, 가운데 유리 슬롯, 중간 열린 층을 가로막는 중앙 석재 패널을 넣었다. 거주 펜트하우스에는 몸체와 다른 넓은 세로 프레임과 후퇴한 유리 슬롯을 넣고 평평한 코니스로 마감한다. 네 면에 똑같은 중앙 장식을 복제하지 않는다.

2차 E/F는 각자의 이름 있는 윤곽 안에서 중앙부와 네 어깨를 나누고 높이를 달리한다. 실제 사진의 넓은 흰 띠, 검은 환기 패널, 안으로 꺾인 창 면, 열린 삼각형 프레임, 두 개의 금속 아치가 중심이다. 최상부 석재 스크린도 통째로 빈 벽으로 두지 않고 SAMOO60 seq3과 SAMOO59 seq4에 보이는 위쪽 모서리의 큰 어두운 개구부, 그 아래 유리 띠와 가까운 꺾임 면의 창을 넣었다. 확인되지 않은 반대 면에 같은 개구부를 복제하지 않았다. 같은 설계군이라 공유되는 창 원시는 있지만 기존 둥근 유리 원통이나 1차 옥탑을 재사용하지 않는다. 날개별 151–181m 전후 높이와 보이지 않는 면의 대응은 **사진 비례 추정**이다.

G는 상세 OSM Y형 윤곽의 톱니 모양과 깊게 들어간 면을 그대로 유지하고 세 방사형 몸체로 나눈다. 최고 264m는 CTBUH 값이며 253/218m의 나머지 날개는 사진 비례 추정이다. 커튼월의 가는 수평선보다 강한 수직 은색 핀, 함몰부의 어두운 루버, 날개마다 다른 종료 높이를 만들었다. 옥탑 유리보다 금속 핀이 일부 더 올라오도록 분리했고 중앙 원뿔·첨탑은 없다. 정확한 날개별 실제 높이나 미공개 내부 구조를 복원했다고 주장하지 않는다.

SWA 배치도 일곱 점을 source centroid에 맞춘 affine 잔차는 약 3.0–8.6m다. 이는 배치도 문자와 블록 관계를 검증하는 보조자료이며, 최종 동 좌표는 각 source의 centroid를 독립 사용한다. 지상층 높이는 총높이와 사진 비례로 보간하며 창틀 폭, 벽 돌출량, 설비, 가려진 면은 실측값이 아니다.

## 편집·재구성

`tower-palace-authored.blend`에 일곱 동의 형상·재질을 편집 가능한 별도 collection으로 보존한다. 검토용 바닥·카메라·조명은 `REVIEW_ONLY_NOT_EXPORTED` collection에 있으며 GLB에 포함하지 않는다. Blender 축은 동 X / 북 Y / 위 Z, GLB는 동 X / 위 Y / 남 Z다. 각 GLB는 자체 WGS84 anchor의 로컬 좌표로 내보낸다.

저장된 `.blend`에서는 전체 단지 배치를 보기 위해 각 오브젝트에 `bundle.assets[].blendSceneOffsetEN` 이동을 적용해 두었다. 수동 재수출할 때 해당 오프셋을 빼야 기존 좌표와 일치한다. 통합 publisher는 geometry를 재중심화하지 않으므로 이 값을 무시하면 이중 이동이 발생한다.

재구성 입력은 `claimed-source-buildings.json`, `source-observations.json`, `recipe-input.json`이다. `modeling/bespoke/tower-palace`에 보존했으며 두 스크립트가 해당 경로를 fallback으로 읽는다. 레시피 수정 후 준비 스크립트를 다시 실행하면 authored 결정을 덮어쓰므로 준비 코드도 함께 수정해야 한다.

```sh
.venv/bin/python scripts/bespoke/tower_palace_prepare.py
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute \
  --port 9877 --script scripts/bespoke/tower_palace_blender.py \
  --record data/model-source/bespoke/tower-palace/mcp-build.json
```

이 명령은 이미 작동 중인 전용 Blender MCP와 Python 환경이 필요하다. 소스 사진을 자동 수집하거나 공개되지 않은 CAD를 복원하는 명령이 아니다. 결과의 지도 중첩·실제 배포 검증은 root 통합 단계에서 별도로 수행한다. 본 문서는 단독으로 공개 배포 완료를 뜻하지 않는다.
