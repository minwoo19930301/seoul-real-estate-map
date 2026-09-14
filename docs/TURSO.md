# Turso로 서울 지도 데이터 운영하기

지도 표시와 현재 상세 API가 읽는 데이터는 `seoul-service` DB 한 개에 들어간다. 건물·도로·지형의 RTree와 테이블 간 JOIN은 이 DB 안에서 실행된다. 데이터셋별 `metadata` 테이블은 `buildings_metadata`, `terrain_metadata`처럼 이름을 구분한다.

큰 `apartment_sources.sqlite` 원본은 동일한 스키마를 가진 25개 구별 DB와 `shared` DB로 나눈다. 서울 외 지역, 지역을 확정할 수 없는 데이터, 공통 출처 기록은 `shared`에 보관한다. 행을 버리지 않으며 원본 테이블별 행 수와 분할 후 합계를 검사한다. 서비스용 추출본과 원본은 일부 중복되지만 원본을 보존하면서 화면 조회를 단순하게 유지하기 위한 구성이다.

## 실행

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci
npm run build
export SEOUL_TURSO_CONFIG="$HOME/.config/seoul-map-turso/runtime.json"
npm run start:turso
```

`runtime.json`은 서버 전용 파일이다. DB 읽기 토큰이 들어 있으므로 Git이나 프런트엔드에 넣지 않는다. `SEOUL_TURSO_CONFIG`가 없으면 기존 로컬 SQLite를 사용한다. 북마크 쓰기는 로컬 DB에 유지한다. 지형 PNG와 모션용 지형 파일은 `public/data/terrain`에서 제공한다.

설정 형식:

```json
{
  "version": 1,
  "databases": {
    "buildings.sqlite": {
      "hostname": "YOUR-DATABASE.turso.io",
      "token": "YOUR-READ-ONLY-TOKEN",
      "metadata_table": "buildings_metadata",
      "bytes": 0
    }
  }
}
```

실제 생성되는 설정에는 모든 서비스 데이터셋이 포함된다. 로컬 DB 파일이 없는 경우에도 등록된 원격 DB를 조회한다. HTTP SQL 연결은 요청마다 독립적으로 열고 닫으며 서버 읽기 전용으로 사용한다. 원격 응답 크기·지연과 제공자의 무료 사용량 한도는 여전히 적용된다.

## 데이터 다시 준비하고 올리기

원본 SQLite는 로컬 `data/`에 보관한다. 원본 다운로드 파일과 토큰은 GitHub에 포함하지 않는다.

```sh
python3 scripts/prepare_turso.py --output data/turso-export-new
python3 scripts/upload_turso.py --export data/turso-export-new
python3 scripts/upload_turso.py --export data/turso-export-new --verify-only
```

업로더는 `~/.config/seoul-map-turso/accounts.json`과 계정별 토큰 파일을 읽는다. 계정별 예상 용량을 배분하고 도쿄 리전에 그룹을 만든다. 업로드 전 로컬 SHA-256을 확인하고, 업로드 후 원격 테이블별 행 수를 로컬과 비교한다. 체크포인트와 DB 읽기 토큰은 같은 로컬 설정 디렉터리에 저장한다. 업로드 권한 토큰은 하루 후 만료된다.

현재 스냅샷과 다른 데이터로 기존 DB를 자동 덮어쓰지 않는다. 새 스냅샷을 배포하려면 별도 이름과 체크포인트를 사용하도록 구성하거나, 기존 배포를 확인하고 명시적으로 교체해야 한다. 같은 스냅샷의 중단된 업로드는 체크포인트로 재개한다.

`docs/turso-upload-report.json`은 인증 정보가 없는 업로드 결과다. 계정별 용량, DB 주소, 로컬 체크섬, 원격 행 수가 기록된다.

## 제한

- 구별 DB를 가로지르는 검색·집계는 서버에서 여러 DB를 조회해 합쳐야 한다. 현재 지도 API는 서비스 DB를 사용하므로 이 분산 조회가 필요하지 않다.
- 계정 장애·삭제 시 해당 원격 데이터가 사라질 수 있다. 로컬 원본과 분할 스냅샷을 보존한다.
- 서비스 데이터 갱신 시 서비스용 추출본도 다시 만들어야 한다. 실시간 동기화는 구현하지 않았다.
- 여러 무료 계정의 허용 여부는 확인되지 않았다. 코드 자체는 단일 계정의 여러 DB에서도 사용할 수 있다.

공식 문서: [업로드 API](https://docs.turso.tech/api-reference/databases/upload), [SQL over HTTP](https://docs.turso.tech/sdk/http/reference).

## 구별 원본 조회

```sh
python3 scripts/query_turso.py --district gangnam --sql 'SELECT COUNT(*) AS rows FROM molit_apartment_price_2025'
```

`shared`를 지정하면 서울 외 지역 및 지역 미확정 원본을 조회한다. SQL과 결과만 터미널에 표시하고 토큰은 출력하지 않는다.
