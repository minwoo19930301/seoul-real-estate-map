# 타워팰리스 E/F 높이 기준 검토

확인일: **2026-09-21**. 대상은 `bespoke-tower-palace-e`, `bespoke-tower-palace-f`이며 모델·승인 상태·건축물대장은 변경하지 않았다. 결론은 **기존 191m 모형을 지금 일괄 축소하지 않고, 높이 기준의 불일치를 명시하여 추가 검토하는 것**이다. 건축물대장 184.65m와 건축적 최고점 약191m가 모두 확인되지만, 그 차이가 정확히 어떤 부재나 기준면 때문인지 설명하는 준공 단면도를 확보하지 못했다. 구조설계자의 다른 최고높이 **196.5m**도 확인되어 단순한 두 수치의 차감으로 해결할 수 없다.

| 출처 | E/F 관련 수치 | 확인 범위와 확신 |
|---|---|---|
| [서울시 건축물대장 표제부 OA-22424](https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do), 보존한 2026-09-08 추출본 | E/F 각각 **184.65m**, 지상55층·지하6층 | 정확한 필지·동명으로 연결한 공개 필드. **값·대상 식별은 높음**, 그 값의 상단 부재/기준면은 이 추출본에 없음. 최신 대장을 다시 발급했다는 뜻이 아님. |
| CTBUH/CVU 개별 [Tower E](https://www.skyscrapercenter.com/building/tower-palace-two-tower-e/1946), [Tower F](https://www.skyscrapercenter.com/building/tower-palace-two-tower-f/1947) | 각각 **Architectural 191.1m**, **To Tip 191.1m**, **Helipad 191m**, 55층 | 2026-09-21 두 개별 페이지 직접 확인. **수치와 항목 구분은 높음**. 건물별 실측 원장/표고 도면은 페이지에 제시되지 않음. |
| [CTBUH/CVU 단지 목록](https://www.skyscrapercenter.com/complex/215) | E/F 각각 **191m** | 목록 표시는 정수 단위. 기존 모델의191m 근거다. 개별 페이지의191.1m를 대신하는 더 정밀한 수치가 아님. |
| [SAMOO 설계자 프로젝트](https://www.samoo.com/home/works/view.do?cntntsSn=60) | 지상 **55층**, 지하 **6층**, 준공 **2003년** | 직접 확인한 프로젝트 본문은 층수와 사진을 제공하나 미터 높이 또는 기준 표고를 제공하지 않는다. |
| 금동성, [「타워팰리스-Ⅱ의 구조설계」](https://www.auric.or.kr/user/Rdoc/DocCmag.aspx?dn=129348&returnVal=CMAG), 한국강구조학회지16권4호, 2004.12, pp.29–46 | p.29: **57층(옥탑 포함)**, **지상 최고높이196.5m**, 지하층 깊이22.2m | 구조설계 참여사인 삼우구조컨설턴트 대표의 기술기사. **공개 미리보기 p.29 실제 페이지를 시각 확인**했다. 사진은 준공 후 전경으로 설명된다. 그러나 공개 p.29–30에는 최고점·옥탑별 표고를 연결하는 단면도가 없고, 196.5m와 다른 두 자료의 관계를 설명하지 않는다. |
| [Doka, *Técnica de trepado Doka*](https://www.doka.com/web/media/files/know-how/competence-centre/Monogr%C3%A1fico%20Trepa.pdf), p.86 | Tower Palace II, Seoul, **191m**, 시공 Samsung | 제조사 원본 프로젝트 목록 PDF를 내려받아 해당 페이지를 시각 확인. 약191m가 다른 프로젝트 자료에도 등장함을 뒷받침하나, 지붕/옥탑/기준면 정의가 없어 차이의 해답은 아님. |
| Moon 외, [*An analysis of Land Mark impact factors on high-rise residential buildings value assessment*](https://journals.vilniustech.lt/index.php/IJSPM/article/view/5715), 2010, Table5 p.113 | Tower Palace II **184.65m**, 연면적296,652㎡ | 발행처 [PDF](https://journals.vilniustech.lt/index.php/IJSPM/article/download/5715/4960)의 표를 시각 확인. 방법론은 현장조사·서울GIS·부동산포털·건축물대장을 함께 사용하므로 대장과 독립적인 높이 실측 검증이라고 볼 수 없다. 도면/높이 datum은 없음. |

CTBUH/CVU의 [공개 높이 기준](https://www.skyscrapercenter.com/criteria)은 주요한 외부 보행자 출입구 중 가장 낮은 입구의 문턱 바닥을 기준으로 건축적 최고점까지 측정한다. 건축적 첨탑은 포함하고 안테나·간판 같은 기능성 설비는 제외하며, 상당한 포디엄에 관한 별도 기준도 설명한다. 개별 E/F 페이지는 최고점과 헬리패드를 별도 항목으로 표시한다. **따라서191m가 단순한 주거층 높이인지, 특정 지붕면인지 임의로 바꿔 해석하면 안 된다.** 반대로 대장 추출본에는 기준지반·평균지반·옥탑 산입 여부가 없어, 일반적인 높이 산정 관행을 이 두 동에 실제 적용된 사실로 단정하지 않는다.

정확한 대장 연결과 현재 모델은 [기존 완료단지 높이 감사](apartments-400-existing-height-audit.json)에 남겼다. E는 대장ID `102412211`, 동명 `이동`, F는 `102412210`, 동명 `에프동`이다. 둘 다 `강남구|도곡동|land|467|17`에 속한다. E는 도로명키 `강남구|언주로30길|57|0|지상`도 일치한다. F의 대장 도로명키는 빈 값이지만 정확한 필지와 고유한 동명, 주소DB의 같은 `에프동` 및 도로명키가 대응한다. 주소 하나만으로 높이를 복사한 결과가 아니다.

현재 두 GLB는 각각 최고191m이며, 사진에 따른 단계형 날개·열린 지붕 프레임·금속 아치까지 그 안에 모델링되어 있다. 수치 차이는 다음처럼 구분해야 한다.

- 현재 모형191 − 대장184.65 = **6.35m**.
- CTBUH 개별 건축적 최고점191.1 − 대장184.65 = **6.45m**.
- 구조설계 기사 최고점196.5 − 대장184.65 = **11.85m**.
- 구조설계 기사196.5 − CTBUH191.1 = **5.4m**.

이 차이 중 어느 것도 **옥탑 높이로 확인된 치수는 아니다**. 기사에 옥탑을 포함한57층과 통상55층의 구분이 명시되어 있어 옥탑 포함범위가 다른 높이의 원인일 가능성은 있지만, 이는 **검증되지 않은 가설**이다. 출입구 기준면·허가/준공 단계·기록 오류 등의 가능성도 이 자료만으로 구분할 수 없다. 숫자가 우연히 어떤 층고나 일반적인 높이 제외 범위와 비슷하다는 이유로 원인을 확정하지 않는다.

변경 권고는 다음과 같다.

1. 현 GLB191m를 유지한다. 184.65m로 전체 정점을 비례 축소하거나, 상단을6.35m 잘라내거나, 반대로 기사196.5m로 일괄 확대할 근거가 부족하다.
2. 설명에는 **“CTBUH 단지 목록의 약191m를 따르는 외관 모형; 개별 페이지의 건축적 최고점191.1m, 대장184.65m 및 구조설계 기사196.5m의 기준 차이 미해결”**이라고 구분한다. 현재 외관이191.1m까지 실측 정밀 복원되었다고 주장하지 않는다.
3. 높이 확정에는 각 동의 기준지반/1층 표고, 최상 주거층, 옥탑층, 헬리패드, 지붕 장식 최고점을 함께 표기한 승인 또는 준공 단면도가 필요하다. 확인 후 몸체·옥탑 중 해당 부분만 교정하고 개별 사진 검토를 다시 해야 한다.
4. 주거동 **E/F 두 동 및55층 사실은 여러 자료에서 일치**한다. 이번 미해결 높이 검토를 주거동 누락 판정으로 바꾸거나 기존 `coverageApproved`를 자동 변경하지 않는다. 완성도 검토 중 높이의 확신과 사진의 외관 검토 범위는 별도로 유지한다.

자료 접근의 한계: AURIC는 전체 원문18쪽에50포인트가 필요하다고 표시한다. 공개된 `previewDoc()` 경로에서 제공한 **2쪽만** 읽었으며, 유료 전체 원문을 읽었다고 주장하지 않는다. 공개 미리보기 주소는 [preview](https://www.auric.or.kr/dordocs/preview_rdoc.asp?returnVal=CMAG&dn=129348), 실제 미리보기 PDF 응답은 [PDF viewer](https://www.auric.or.kr/pdf_view/pdf_view2_open.asp?filename=ex_ksscw_200412_007.pdf)다. 이번 범위에서 datum을 조정할 수 있는 치수 단면도는 확보하지 못했다.

검토용 원본과 페이지 렌더는 `/tmp/tower-palace-height-review/`에만 두었다. 저장소에 제3자 사진이나 논문 본문을 복제하지 않았다. 실제 시각 확인 파일은 `auric-preview-1.png`, `doka-86.png`, `landmark-paper-9.png`다. 기존 모델, 편집 가능한 Blender 파일, runtime, manifest, 완료 판정은 변경하지 않았다.

다운로드 원본 SHA-256:

- `auric-preview.pdf`: `b4a79dc21e3f079d8e043efa563e463f5d59801814b2d7a6235ae1b2e6b6ddf1`
- `doka.pdf`: `3b0ecb6290fcdd99b52a728e962bd7a8749a95d60ca579b403f94eb6f3adb21d`
- `landmark-paper.pdf`: `0c2aec8d94d1c920f7e16dac3ab62a43a40c7388d94e37a2a688b3c9eaaa0c3b`
