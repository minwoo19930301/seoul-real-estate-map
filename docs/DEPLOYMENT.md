# Seoul Real Estate Map 자동 배포

운영 주소: https://seoul-elevation.vercel.app

기존 Vercel 프로젝트에서 프런트엔드와 Python API를 함께 운영합니다. DB는 기존 Turso `seoul-service`를 읽기 전용으로 사용합니다. 개인 컴퓨터의 실행 프로세스나 파일 시스템에 의존하지 않습니다.

## main 병합부터 배포까지

`.github/workflows/deploy.yml`은 PR에서 Node 검사, Python 호스팅/API 검사, 자산 체크섬, production build를 검증합니다. `main`에 병합하거나 push하면 같은 검증 후 Vercel에 자동 배포합니다. `workflow_dispatch`로 `main`을 다시 배포할 수도 있습니다. 다른 브랜치를 수동 실행해도 운영 배포는 하지 않습니다.

배포가 끝나면 운영 `/api/health`의 `release_sha`가 해당 Git 커밋과 같은지 확인하고, 원본 등고선 8,570개·표고점 45,870개, 실제 지형 PNG, GLB 모형과 홈페이지를 확인합니다. 서울시청 검색과 실제 지도 범위의 등고선·건물·도로·장소 조회도 gzip 요청으로 검사합니다. 실패하면 Actions 실행이 실패로 표시되며 다음 커밋에서 수정해 다시 배포할 수 있습니다. Vercel 빌드가 실패하면 기존 운영 배포가 유지됩니다.

API는 `vercel.json`의 `routes`로 전달합니다. 이름 있는 `rewrites` 매개변수는 Vercel이 쿼리에 추가하므로, 쿼리 키를 엄격히 검사하는 기존 API에서는 사용하지 않습니다.

## 인증과 계정

- GitHub repository secret: `VERCEL_TOKEN`
- GitHub repository variables: `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
- Vercel server environment: `SEOUL_TURSO_CONFIG_JSON` (암호화), `SEOUL_ALLOW_HOSTED=1`, `SEOUL_ALLOWED_ORIGINS=https://seoul-elevation.vercel.app`
- 배포별 `SEOUL_RELEASE_SHA`: Actions의 Git 커밋 SHA

Turso 토큰은 Vercel 서버 환경변수에만 둡니다. Git, 브라우저 번들, 로그에 넣지 않습니다. 계정의 기존 Vercel 토큰을 교체하면 GitHub의 `VERCEL_TOKEN`도 갱신합니다.

## 대형 지도 자산

약 2.776GB의 활성 GLB 모형과 보존된 이전 GLB을 CLI 소스 업로드에 포함하지 않습니다. Vercel 빌드가 동일한 Git 커밋에서 `public/models`를 가져오고 `public/data/deployment-assets.json`의 SHA-256을 검사합니다. GitHub Actions의 `contents: read` 토큰은 이 빌드에만 전달되며 장기 GitHub 토큰은 저장하지 않습니다. 지형 타일은 함수 패키지에도 포함하여 사람 시점/도로 지면 계산을 유지합니다.

신규 주거 모형은 지역별 하위 폴더에 보관합니다. 자산 manifest 갱신 시 `public/models`를 재귀 순회하여 index·타일 JSON·GLB 모두 포함합니다.

모형이나 지형을 변경할 때는 배포 자산 manifest도 갱신해야 합니다. 누락·변조되면 빌드는 중단됩니다. 서비스 DB 내용 갱신은 기존 `docs/TURSO.md` 절차를 따릅니다. 코드 병합이 원본 DB를 덮어쓰지는 않습니다.

## 저장 위치

운영 사이트의 저장한 위치는 브라우저 localStorage에 보관합니다. 방문자끼리 공유되지 않으며 함수 재시작에 영향받지 않습니다. 브라우저 데이터를 지우면 함께 지워집니다. localhost 실행은 기존 로컬 SQLite 북마크를 유지합니다.

## 저장소 이름과 운영 주소

GitHub 저장소는 `minwoo19930301/seoul-real-estate-map`입니다. 이름 변경 뒤에도 기존 Vercel 프로젝트와 운영 주소를 유지합니다. `scripts/prepare_hosted_assets.py`는 새 저장소의 동일한 커밋에서 자산을 가져옵니다. 브라우저 저장 위치의 기존 키도 유지하므로 이름 변경으로 저장한 위치가 사라지지 않습니다.
