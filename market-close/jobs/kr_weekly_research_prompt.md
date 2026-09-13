# 국장 주간(토요일 12:00 KST) 뉴스 리서치 — 재실행 프롬프트 · 체크리스트

누가샀나 토요일 "코스피 주간 결산" 영상의 뉴스 근거 파일을 만드는 작업이다.
미국편(`jobs/us_weekly_research_prompt.md`)과 규칙은 같고, 대상만 국내 증시다.

- 출력: `data/weekly/{BUILD_DATE}/news.json` → 검증 뒤 `data/weekly/{BUILD_DATE}/news_verified.json`
- 읽기만 할 파일: `data/weekly/{BUILD_DATE}/computed_weekly.json`(주간 집계, 수정 금지),
  `data/<YYYYMMDD>/computed_kr.json`·`raw/flows.json`·`raw/krx_investors.json`·`raw/kiwoom_sum_1400.json`·`raw/event.json`
- 대상 주간: 그 주 월~금(휴장일 제외). BUILD_DATE = 토요일 YYYYMMDD

---

## 1. 절대 규칙

1. **종목 추천 금지.** 매수·매도·목표주가·투자의견·애널리스트 등급은 옮기지 않는다.
2. **원인은 뉴스로 뒷받침하고 완곡하게.** 쓸 수 있는 표현: "~와 겹쳤습니다", "~로 풀이됩니다", "~로 볼 수 있습니다", "(매체)는 ~를 배경으로 짚었습니다".
   **금지어**(`sources`를 뺀 모든 문자열): `때문에` `이유` `덕분` `탓` `영향으로` `나오자` `힘입어`, 그리고 단정하는 "~해서 올랐다/내렸다".
   최종 확인은 `python -c "from checks import forbidden; ..."`가 아니라 대본 단계의 `checks/forbidden.py`가 잡는다. 여기서도 미리 피한다.
3. **숫자는 실제 값만.** computed 파일 값 또는 직접 열어 본 기사 숫자만. 매체마다 다르면 매체를 밝히고 `note`에 적는다.
   수급 숫자는 키움(ka10059) 기준과 거래소 집계 기준이 다르다. 평일 영상과 같은 **키움 기준**을 쓰고, 언론 수치를 인용할 땐 "(매체 기준, ETF 포함)"처럼 근거를 밝힌다.
4. **이벤트마다 실제로 열어 본 URL 1개 이상.** 검색 결과 요약만 보고 넣지 않는다. WebFetch로 본문을 확인한 것만 `sources`에 넣는다.
5. 인용문은 한 문장 이내로 짧게, 나머지는 의역.
6. `sources[].title`은 기사 원제목 그대로 둔다(폭등·훈풍 같은 표현 포함). **화면·TTS에는 쓰지 않는다.**

## 2. 무엇을 찾나 (한 주 5거래일 × 아래 축)

- 그 주 지수의 고비(7,000선 같은 분기점, 장중 반전, 주간 최대 상승·하락일)
- 투자자별 한 주 순매수·순매도와 날짜별 변화 — 특히 방향이 바뀐 날
- 돈이 빠진 곳과 머문 곳: 업종·테마(`raw/flows.json` table_t 주간 합), 기타법인 상위 종목(자사주 매입 프로그램 `data/buybacks.json`과 연결)
- 그 주 국내 뉴스: 실적·수출입·정책·환율·금리·수급 규제
- 해외발 재료: 미국 지수·반도체지수(`raw/us_index.json`), 연준·CPI, 유가, 지정학
- 주말~다음 주로 넘어가는 예고(일정, 발표 예정)

## 3. 스키마 (events[] 각 항목)

```json
{
  "d": "20260908",
  "title": "짧은 제목(화면 카드용, 20자 안팎)",
  "what": "무슨 일이 있었나 — 날짜·주체·수치를 포함한 사실 서술",
  "market_link": "그날 시장 움직임과 어떻게 맞물렸는지(완곡하게)",
  "our_data": "우리 데이터로 재계산한 값 — 분봉·수급·테마 합 등",
  "confidence": "high | medium | low",
  "verified": true,
  "note": "어떤 기사에서 무엇을 대조했는지",
  "sources": [{"outlet": "매체명", "title": "기사 원제목", "url": "...", "published": "2026-09-08 16:22"}]
}
```

`news_verified.json`은 위 구조에 `verified_meta`(checked_at, method, events_total, events_verified, source_titles_note)를 얹는다.
`verified:false`이거나 `use_in_script:false`인 항목은 대본에 쓰이지 않는다(`run_weekly.py:_news`).

## 4. 체크리스트

- [ ] 거래일마다 최소 1개 이벤트, 주간 전체 8~15개
- [ ] 각 이벤트 `sources` 1개 이상, URL 실제 열람
- [ ] 금지어 검사 통과(`sources` 제외)
- [ ] 숫자 재계산: 지수 종가·등락, 투자자별 합, 테마 합
- [ ] 추천·단정 표현 없음
- [ ] 화면 카드용 3~4개 후보 표시(confidence high/medium)
