# Bright Data를 통한 단지 정보 수집

수집은 필요할 때 실행하는 서버 측 Python 작업이다. MCP·상시 프로세스·자동 계정 전환을 설치하지 않는다. 대상 웹사이트에는 직접 요청하지 않고 Bright Data Web Unlocker API만 사용한다.

```sh
python3 scripts/collect_proptech_brightdata.py \
  --url https://kbland.kr/se/c/22859 --upload
```

Bright Data 키는 저장소 밖 `~/.config/brightdata/mcp-accounts.json`의 활성 항목을 실행 시에만 읽는다. Turso는 기존 `~/.config/seoul-map-turso/` 설정으로 `seoul-service`에 접근한다. 쓰기 토큰은 1시간 유효하며 메모리에서만 사용한다. 웹 클라이언트에 인증정보를 전달하지 않는다.

원문 HTML·응답 영수증·추출본은 Git에서 제외된 `data/proptech-brightdata/`에 남는다. 이미 수집한 응답의 재적재는 다음과 같다.

```sh
python3 scripts/collect_proptech_brightdata.py \
  --receipt data/proptech-brightdata/NAME.receipt.json --upload
```

재적재도 Bright Data 응답 표시·HTTP 성공·원문 SHA256·단지 ID를 검증한다. 홈페이지 껍데기·로그인 페이지·빈 응답을 단지 데이터로 적재하지 않는다. 같은 영수증은 같은 snapshot ID를 사용해 중복 적재하지 않는다. 새 조회 시각의 응답은 이력으로 보존한다.

## Turso 테이블

- `proptech_bd_snapshots`: 공급자 단지 ID, URL, 수집 시각, 원문 SHA256, Bright Data 전달 경로, 수집 한계.
- `proptech_bd_facts`: snapshot별 단지·평형 항목, 원문 필드명, JSON 값, 단위, 관측 여부, 원문 데이터 경로.

현재 KB Next.js 응답의 실제 단지 상세·평형 자료만 추출한다. 주차, 난방, 현관구조, 지상 최저·최고층수, 연면적, 방·욕실, 면적, 평면도 열람 URL, 계절별·연평균 총관리비를 화이트리스트로 가져온다. 커뮤니티 게시자·연락처·대출 추천·소유자 프로필은 추출하지 않는다.

`not_observed`와 실제 0을 구분한다. 관리비는 총관리비이며 공용관리비나 연간 합계로 바꾸지 않는다. 평면도 URL 수집이 이미지 다운로드·베이 판독을 의미하지 않는다. 단지 ID는 KB의 ID다. 관리코드와의 병합에는 별도의 주소·단지 대조가 필요하다.

## 아직 수집하지 않은 항목

집주인확인 매물, 급매 표시, 동·층별 실시간 호가, 호가 스프레드, 승강기 대수·속도, 구조 형식, 용도지역, 500m 거래 사례, 커뮤니티 시설, 정비사업 단계·비례율·분담금은 현재 파서가 제공하지 않는다. 다른 시세나 추정값으로 대체하지 않는다. 정비사업 단계를 임의의 진행률 퍼센트로 환산하지 않는다.

닥집의 특정 소유자 나이·부채·자금 압박 프로파일 및 이를 이용한 협상 점수는 수집·생성하지 않는다. 향후 매물 분석은 공개 호가 변동·게시 기간·같은 면적과 거래 유형의 비교 자료로 구성한다.

첫 Bright Data 응답에서 밸류맵·닥집은 앱 화면만, 네이버 첫 화면은 검색 UI만 내려왔다. `jaegaebal.com`은 도메인 안내, 클린업 첫 URL은 빈 응답이었다. HTTP 200만으로 해당 플랫폼 수치가 확보됐다고 보지 않는다. 상세 URL·공개 응답 또는 권한 있는 연결이 확인되어야 다음 파서를 추가한다.

[Bright Data REST 요청](https://docs.brightdata.com/products/web-unlocker/send-your-first-request) · [Turso SQL HTTP](https://docs.turso.tech/sdk/http/reference)
