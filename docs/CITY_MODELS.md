# 주요 빌딩의 기존 Blender 모델

`seoul-flight-game`에서 검증했던 독립 제작 GLB 4종을 원본 바이트 그대로 재사용합니다. 기존 Blender 원본은 `data/model-source/seoul-landmarks.blend`, 원래 출처·검증·렌더 이미지는 같은 폴더에 보존했습니다. 4개 GLB·좌표·회전·치수와 Blender master의 원본 일치를 [재사용 감사](../data/model-source/reuse-proof.json)에 기록했습니다. 이 모델은 공개 높이를 맞춘 참고 재현이며 공식 CAD·현장 측량·사진측량 모델이 아닙니다. 창 간격, 외장 재질, 평면 폭·깊이와 세부 구조는 추정입니다.

| 모델 | 모델 전체 높이 | 높이와 위치 기준 |
|---|---:|---|
| 롯데월드타워 | 555m | [설계사 KPF](https://www.kpf.com/project/lotte-world-tower), 갈라진 정상부 포함. OSM way 914963586 |
| 63빌딩 | 249.58m | [서울역사박물관](https://museum.seoul.go.kr/archive/archiveNew/NR_archiveView.do?ctgryId=CTGRY489&fileId=H-TRNS-102535-491&fileSn=300&type=A&upperNodeId=CTGRY491), 미확인 안테나 추가 없음. OSM way 64989671 |
| N서울타워 | 236.7m | [운영사 제원](https://www.nseoultower.co.kr/global/intro2.asp)의 탑신 135.7m + 철탑 101m. 현재 OSM relation 16474080 |
| 무역센터 트레이드타워 | 256.5m | [CTBUH/CVU](https://www.skyscrapercenter.com/building/trade-tower/1141)의 건축 높이·헬리패드 228m, 기술 설비 포함 끝 256.5m. OSM way 74056379 |

근정전의 기존 26m는 창작 추정치이므로 이번 4종 목록에서 제외했습니다. `coex.glb`는 저층 COEX 전시장이 아닌 트레이드타워입니다. 모델 좌표는 기존 검증한 tower footprint 중심을 유지하며 공식 위치 측량값이라고 주장하지 않습니다.

| ID | 경도, 위도 | 폭 축 회전(동쪽에서 반시계방향) |
|---|---|---:|
| sixtythree | 126.9402516, 37.5198496 | 38.2202° |
| lotte | 127.102679, 37.5125537 | 22.5573° |
| nseoul | 126.9882805, 37.5512700 | 0° |
| coex | 127.0610204, 37.5103271 | 22.9297° |

원래 GLB는 미터 단위이며 바닥 중심이 원점, +Y가 위쪽입니다. yaw=0에서 +X는 동쪽, +Z는 남쪽입니다. 앞면 실루엣·금빛 63빌딩·은청색 롯데·회백색 N타워·청회색 계단형 트레이드타워의 원래 mesh와 PBR 재질을 보존했습니다. 참고 사진은 링크만 보존하며 사진을 텍스처로 재배포하지 않습니다.

## 지면과 높이

MapLibre 6.8의 `render(gl, args)`와 `args.defaultProjectionData.mainMatrix`로 Three.js custom layer를 그립니다. `queryTerrainElevation()`은 렌더된 DEM 표면의 강조 배율이 이미 적용된 고도를 반환하므로 모델의 **바닥 이동에만** 그대로 사용합니다. 모델의 X/Y/Z 치수는 모두 1m=1m 비율이며 높이에 강조 배율을 다시 곱하지 않습니다. 예를 들어 지형 4배에서 롯데 모델 자체는 555m로 남습니다. 바닥 고도는 보간 모델값이며 건물대장 높이·원본 표고점 조회값이 아닙니다.

N서울타워 공개 문서의 지반 고도는 운영사와 서울시 자료 사이 차이가 있으므로 어느 공개 지반 값을 이 지도의 실측 정답처럼 덮어쓰지 않습니다. 현재 등고선·표고점 보간 DEM에 놓습니다. 개별 모델 바닥은 중심점의 지면에 놓이는 평평한 바닥이므로 경사 지면에서 기단과 약간 교차할 수 있습니다. 기단이 접하도록 외관 높이를 임의로 늘이지 않습니다.

## 표시와 원본 건물 보존

`/models/footprint-matches.json`은 원본 OSM ID로 확인한 현재 건물 GERS ID와 연관 부분 도형을 지정합니다. 반경 안의 다른 건물을 일괄 삭제하지 않습니다. 모델이 실제로 로드되고, 검증을 통과하고, DEM과 GPU 렌더가 준비된 2.5D 상태에서만 해당 ID의 일반 입체 도형을 대체하도록 콜백을 보냅니다. 원본 외곽선·높이 조회는 유지합니다. 모델 OFF, 2D, 실패, 화면 밖에서는 대체 대상 ID가 해제됩니다. N서울타워의 원본 4m/7m 낮은 기단 부분은 유지합니다.

`CityModels` API:

```ts
const models = new CityModels(map, {
  onState: state => { status.textContent = state.message; },
  onActiveFootprints: ids => buildings.setModelFootprints(ids),
});
models.setFootprintMatches(matches);
await models.init();
models.setMode(is25d);
models.setVisible(showMajorModels);
models.updateTerrain(); // terrain mode/exaggeration change
models.setTrees(placements); // optional decorative greenery from checked polygons
models.setTreesVisible(showTrees); // independent of building visibility
```

## 성능과 검증

처음에는 manifest만 받습니다. zoom 13 이상에서 화면 범위를 20% 확대한 영역에 들어오는 모델만 지연 로드하고 그립니다. 네 GLB 총 1,474,460 bytes이며 같은 모델은 다시 다운로드하지 않습니다. 반복 애니메이션 루프가 없고, 지도 이동·지형 tile content·컨트롤 변화 때만 다시 그립니다. 상태 UI와 건물 대체 필터는 내용이 달라질 때만 호출합니다.

선택적인 나무는 실제 개별 나무의 위치·높이 자료가 아닌 녹지 시각화 장식입니다. 줄기와 수관을 두 InstancedMesh에 묶고 버퍼를 재사용합니다. 같은 좌표 목록이나 빈→빈 전달은 빠르게 반환하며, 나무 토글은 건물 모델 토글과 독립입니다. 나무 생성 위치의 원본 폴리곤·제외 범위는 [GREENERY.md](GREENERY.md)를 참고하세요.

`node --test tests/city-models.test.mjs`의 9개 테스트 통과:

- 현재 Three.js GLTFLoader로 4개 GLB를 직접 파싱하고 SHA-256·바닥 원점·전체 치수 확인.
- 지형 1/2/4배에서 모델의 높이 1배·동/남/상 축 유지.
- 화면 밖 미로드·미렌더, 동일 프레임 상태 알림 중복 억제.
- 2D·숨김·DEM 미준비·GPU 실패 시 일반 건물 대체 해제. 잘못된 manifest의 동기 실패 후 로딩 상태도 정상 종료.
- 나무 버퍼 재사용·건물 OFF와 독립적인 나무 표시.

TypeScript 검사도 통과했습니다. 실제 브라우저 WebGL·스크린샷 확인은 별도 실행 증거로 기록합니다.

## 이번 Blender 실행 기록

Blender 4.5.11 LTS의 background 재수출을 두 번 시도했지만, 파일 로드 전 macOS Metal 초기화의 `supports_barycentric_whitelist`에서 SIGSEGV(exit 139)가 발생했습니다. 새 export가 성공했다고 기록하지 않습니다. 기존 GLB와 이전 Blender 검증 자료를 보존했고, 이번에는 현재 GLTFLoader·물리 치수·SHA 일치로 재사용 무결성을 검증했습니다.

재수출 명령은 준비되어 있습니다. 입력 `.blend`를 수정하지 않고 `data/model-source/reexport-2026-09-09/`에 별도로 출력하며 원본 GLB와 SHA를 비교합니다.

```sh
/opt/homebrew/bin/blender --background data/model-source/seoul-landmarks.blend \
  --python scripts/export_city_models.py
```

사용한 MapLibre 계약은 [공식 Three.js+terrain 예제](https://maplibre.org/maplibre-gl-js/docs/examples/adding-3d-models-using-threejs-on-terrain/)와 설치된 `node_modules/maplibre-gl/src/style/style_layer/custom_style_layer.ts`, `src/render/terrain.ts`에서 확인했습니다.

2026-09-09 최종 Chrome 검증: 네 위치의 전체 실루엣과 주변 자료 렌더링 확인, GLB 각1회 로드, 지형4→1에서도 높이동일, 정착 후1초0프레임, 페이지 오류0. 결과는 `tests/screenshots/city-model-render-proof.json`과 `city-model-*.png`에 있습니다. 압축 운영 빌드에서도 N서울타워·장식 나무240개와 gzip 전송을 별도 확인했습니다.
