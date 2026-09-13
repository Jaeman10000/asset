# 미국 주간(일요일 12:00 KST) 뉴스 리서치 — 재실행 프롬프트 · 체크리스트

누가샀나 일요일 "US MARKET WEEKLY" 영상의 뉴스 근거 파일을 만들거나 보강하는 작업이다.
이 문서를 그대로 에이전트에게 붙여 넣으면 된다. `{중괄호}` 부분만 해당 주로 바꾼다.

- 출력(이 작업이 쓰는 유일한 파일): `data/weekly_us/{BUILD_DATE}/news.json`
- 함께 읽기만 할 파일: `data/weekly_us/{BUILD_DATE}/computed_us_weekly.json` (지수·금리·환율·원자재 숫자. 수정 금지)
- 이번 주 값: `WEEK_START=2026-09-08`, `WEEK_END=2026-09-11`, `BUILD_DATE=20260913`, 월요일 9/7은 노동절 휴장, 직전 종가일 9/4(금)
- 첫 실행: 2026-09-11 17:05 KST. 화·수·목(9/8~9/10) 세션만 반영. 금요일 9/11 세션(CPI 포함)은 `pending`에 있음

---

## 0. 에이전트에게 줄 프롬프트 (복사해서 사용)

```
너는 누가샀나 일요일 미국 주간 영상의 뉴스 리서처다.
대상 주간: 미국 정규장 {WEEK_START} ~ {WEEK_END} (휴장일: {HOLIDAYS}). 직전 종가일 {PREV_CLOSE_DATE}.
작업 폴더: C:/Users/Jeff/Documents/GitHub/asset/market-close
기존 파일 data/weekly_us/{BUILD_DATE}/news.json 이 있으면 먼저 읽고, 빠진 세션(특히 금요일)과
pending 항목을 채워 같은 경로에 다시 써라. 없으면 새로 만든다.
숫자는 data/weekly_us/{BUILD_DATE}/computed_us_weekly.json 을 우선하고, 기사 숫자는 "매체명 기준"으로 적는다.
jobs/us_weekly_research_prompt.md 의 규칙·체크리스트·스키마를 그대로 따른다.
다른 파일은 절대 수정하지 마라. 끝나면 파일 경로와 이벤트 요약(날짜·제목·신뢰도)을 반환해라.
```

---

## 1. 절대 규칙

1. **추천 금지.** 매수·매도·목표주가·투자의견은 쓰지 않는다. 애널리스트 등급이나 목표가는 기사에 있어도 옮기지 않는다. 공급 전망처럼 사실에 가까운 전망만 출처와 함께 쓴다.
2. **원인은 뉴스로 뒷받침하고 완곡하게 쓴다.** 쓸 수 있는 표현: "~와 겹쳤습니다", "~로 풀이됩니다", "~로 볼 수 있습니다", "(매체)는 ~를 배경으로 짚었습니다/꼽았습니다".
   **금지어** (news.json 안에서 `sources`를 뺀 모든 문자열에 적용):
   `때문에` `이유` `덕분` `탓` `영향으로` `나오자` `힘입어`
   단정하는 "~해서 올랐다/내렸다"도 쓰지 않는다.
3. **숫자는 실제 값만 쓴다.** computed 파일 값이나 실제로 열어 본 기사에 있는 숫자만 쓴다. 매체마다 숫자가 다르면 범위로 쓰거나 매체를 밝히고, `source_caveats`에 적는다.
4. **정치·전쟁은 중립적인 사실로만 쓴다.** 트럼프, 이란, 우크라이나 관련은 누가 언제 어디서 무엇을 말하거나 했는지만 출처와 함께 적는다. 평가나 형용사는 넣지 않는다. 시장 연결이 약하면 "직접 연결한 보도는 확인되지 않음"이라고 쓰고 `confidence:"low"`로 둔다.
5. **이벤트마다 실제로 열어 본 URL을 1개 이상 단다.** 검색 결과 요약만 보고 넣지 않는다. WebFetch로 본문을 확인한 URL만 `sources`에 넣는다.
6. 인용문은 15단어(한국어는 한 문장) 이내로 짧게 쓰고, 나머지는 의역한다.
7. 화면 색 규칙(빨강=상승/매수, 파랑=하락/매도)은 렌더 단계에서 적용한다. 이 파일에서는 부호(+/−)만 정확히 쓴다.

---

## 2. 일요일 재실행 절차 (금요일 세션 채우기)

미 동부 금요일 장 마감은 한국 토요일 05:00(서머타임)이다. 겨울에는 06:00이다. 일요일 오전에는 금요일 데이터와 주말 뉴스가 모두 나와 있다.

1. **기존 파일 읽기.** `news.json`의 `events`, `pending`, `calendar_next`, `source_caveats`를 확인한다. 기존 이벤트는 틀린 게 확인될 때만 고친다(고친 내용은 caveat에 남긴다).
2. **computed 파일 확인.** `computed_us_weekly.json`의 `sessions`에 금요일 날짜가 들어왔는지 본다. 없으면 story 후보의 주간 숫자는 쓰지 말고 `pending`에 남긴다.
3. **금요일 체크리스트** (항목마다 이벤트 1개, 또는 기존 이벤트 보강):
   - [ ] **8월 CPI 실제치와 컨센서스** (08:30 ET = 21:30 KST). 헤드라인과 근원 각각 전월비·전년비를 적는다.
     첫 실행 때 기록한 컨센서스: 헤드라인 +0.4% m/m, 3.4% y/y / 근원 +0.2% m/m, 2.4% y/y (7월 근원 2.5%)
     `actual_vs_expected` 형식 예: `"헤드라인 전월비 0.X% (예상 0.4%) / 전년비 X.X% (예상 3.4%) / 근원 전월비 0.X% (예상 0.2%) / 근원 전년비 X.X% (예상 2.4%)"`
   - [ ] CPI 직후 반응: 2년물·10년물, 달러인덱스, 달러/엔, 지수선물. 언론이 연결한 표현을 그대로 옮긴다
   - [ ] CPI 뒤 **CME 페드워치 9월 인상 확률** (목요일 약 70%)
   - [ ] 8월 실질임금 (CPI와 같은 시각)
   - [ ] **9월 미시간대 소비자심리 예비치** (10:00 ET = 23:00 KST): 지수, 1년 기대인플레, 5~10년 기대인플레. 8월 확정치는 51.7, 1년 기대 4.0%
   - [ ] **금요일 마감 시황**: 3대 지수·SOX·VIX 등락과 언론이 꼽은 배경. 한국어 기사 1개 이상, 영어 기사 1개 이상
   - [ ] **오라클·어도비** 실적 뒤 첫 정규장(금) 등락. 목요일 시간외는 오라클 +4.34%(인베스팅닷컴)~+7%(서울경제), 어도비 −2.14%
   - [ ] 금요일 반도체 흐름 (목요일 SOX −2.66% 이후)
   - [ ] 금요일 유가 정산 가격과 배경 (후티·바브엘만데브, 호르무즈, 사우디 생산, 미·이란 교전)
   - [ ] IEA 9월 석유시장보고서 (9/11 발표로 검색됨). 공식 페이지는 403이었으므로 로이터·블룸버그 기사로 확인
   - [ ] 금~일 **트럼프 발언** (연준·금리 압박, 관세·캐나다, 이란): 발언 원문, 날짜, 장소, 출처
   - [ ] 주말 **지정학**: 이란·호르무즈, 후티(모카·페림섬·바브엘만데브), 우크라이나·러시아(특사 협상, 정유시설 공격)
   - [ ] 연준 블랙아웃은 9/17 23:59 ET까지다. 그 전에 연준 인사 발언 기사가 나오면 이례적이므로 확인한다
4. **pending 정리.** 해결된 항목은 지우고 아직 없는 것만 남긴다. 모두 채웠으면 `"status":"complete"`로 바꾸고 `sessions_covered`에 `"2026-09-11"`을 추가하고 `sessions_pending`을 `[]`로 둔다.
5. **calendar_next 갱신.** 다음 주 일정을 확인해서 추가하거나 수정한다. 항목마다 `source` URL을 단다.
   첫 실행 때 확인한 다음 주 일정: 9/15 엠파이어스테이트, 9/15~16 FOMC(SEP 포함, 발표는 한국 9/17 03:00), 9/16 소매판매·수입물가, 9/16 레나 실적(장 마감 후), 9/17 주택착공·필라델피아 연은, 9/17 블랙아웃 종료, 9/17~18 BOJ, 9/18 산업생산.
   더 확인할 것: 다음 주 대형 실적(마이크론은 9/30로 검색됨), 20년물·TIPS 입찰(computed 파일에 있음), 영란은행 등 다른 중앙은행.
6. **story_candidates 다시 쓰기.** 4거래일 전체를 한 줄로 엮는 후보를 2~4개 쓴다. 완곡하게 쓰고, 숫자는 computed 파일이나 기사에서만 가져온다. 금요일 CPI 결과가 어느 쪽이었는지에 따라 서사가 달라지므로 반드시 반영한다.
7. **검증.** 아래 7절 스크립트를 돌린다. JSON 파싱, 금지어 0건, 이벤트마다 `sources` 1개 이상, `confidence` 값을 확인한다.

---

## 3. 새 주간에 적용할 때 (일반 절차)

- 대상 기간: 미국 정규장 월~금. 휴장일(노동절, 추수감사절 등)은 NYSE 휴장 달력으로 확인하고 `sessions`에서 뺀다.
- `BUILD_DATE`: 그 주 토요일(YYYYMMDD). 폴더는 `data/weekly_us/{BUILD_DATE}/`.
- 날짜 기준: 이벤트의 `d`는 미 동부 기준 발생일, `session`은 그 이벤트가 반영된 미국 정규장 날짜. 주말이나 장 마감 후 사건은 다음 세션으로 둔다.
- 시각 환산: 서머타임(3월 둘째 일요일~11월 첫째 일요일)에는 ET+13h(08:30 ET = 21:30 KST, 16:00 ET = 05:00 KST 다음 날). 그 밖에는 ET+14h.
- 연준 블랙아웃: FOMC 첫날 기준 둘째 전 토요일 00:00 ET부터 회의 다음 날 23:59 ET까지. FOMC 일정은 federalreserve.gov/monetarypolicy/fomccalendars.htm 에서 확인한다.
- 지표 발표일: 매년 OMB 일정표(census.gov `censusreleaseglance_{YEAR}.pdf`)에 BLS·Census·BEA·연준(G.17) 날짜가 모두 있다. PDF는 WebFetch가 저장해 준 파일을 Read로 열면 표가 보인다.

### 세션별로 반드시 찾을 것

| 분류 | 찾을 것 |
|---|---|
| 경제지표 | CPI·PPI·고용·소매판매·실업수당 등. 실제치와 컨센서스, 직후 금리·달러 반응 |
| 연준 | 인사 발언(블랙아웃 여부 확인), 인상·인하 확률(CME 페드워치, 폴리마켓). 의장: 케빈 워시(2026) |
| 백악관·트럼프 | 연준 압박, 관세(캐나다 등), 이란 관련 발언, 재정 공약. 발언 원문과 장소 |
| 재무부 | 베선트: 국채 바이백, 엔화 개입 발언 |
| 지정학 | 미·이란 전쟁(호르무즈, 하르그섬, 유조선), 후티(사우디 공격, 바브엘만데브), 우크라이나·러시아 |
| 원유 | WTI·브렌트 정산 가격, OPEC 월간보고서, 사우디 생산, IEA 보고서 |
| 엔·원 | BOJ 회의와 위원 발언, 일본·미국 개입, 달러/엔, 서울 원/달러 종가 |
| 기업 | 실적(오라클·어도비·브로드컴 등), 신제품 행사(애플 9월), AI 발표, SK하이닉스 ADR |
| 반도체 | SOX 등락과 언론이 꼽은 배경(금리, 유가, 메모리 가격, AI 투자 논쟁, 수출 규제) |

---

## 4. 검색어 모음

영어:
- `stock market today {Month} {D} {YYYY}` (Yahoo Finance live blog, CNBC, TheStreet, Kiplinger, Edward Jones)
- `Markets News, Sept. {D}, {YYYY}` (Investopedia 요약. Yahoo Finance에 전재됨)
- `Stock Market Today, Sept. {D}` site:fool.com
- `August CPI {YYYY} actual core` / `CPI report August {YYYY}` / `consumer prices August {YYYY} Reuters`
- `oil prices settle {Month} {D} {YYYY} Brent WTI`
- `Treasury yields {Month} {D} {YYYY} 10-year` / `Fed rate hike odds CME FedWatch after CPI`
- `Trump Truth Social Fed Warsh {Month} {YYYY}` / `Trump tariffs Canada {Month} {YYYY}`
- `Houthis Bab el-Mandeb` / `Iran Hormuz tankers` / `Ukraine Russia talks Witkoff`
- `yen BOJ {Month} {YYYY}` / `Bessent yen`
- `Oracle shares Friday after earnings` / `Adobe shares Friday CEO`
- `University of Michigan consumer sentiment preliminary September {YYYY}`

한국어:
- `뉴욕증시 마감 {M}월 {D}일` / `[뉴욕마감]` / `[뉴욕증시 마감]` / `[글로벌마켓 모닝 브리핑]` / `[데일리국제금융]`
- `미국 8월 CPI 발표 결과 근원` / `美 CPI 예상치 상회` 또는 `하회`
- `필라델피아 반도체지수 {D}일` / `SK하이닉스 ADR`
- `원달러 환율 마감 {M}월 {D}일` / `엔달러 환율 일본은행`
- `유가 WTI 브렌트 마감 후티` / `트럼프 연준 금리 발언`

---

## 5. 이 환경에서 열린 사이트와 막힌 사이트 (2026-09-11 기준)

**열림 (WebFetch 성공):**
finance.yahoo.com(라이브 블로그, Investopedia·Forbes·BeInCrypto 전재), ca.finance.yahoo.com, fool.com, 247wallst.com,
investing.com(기업 실적 요약, 로이터 전재), babypips.com, tradingeconomics.com, fortune.com, pbs.org, cbsnews.com,
abc17news.com(CNN 전재), aljazeera.com, euronews.com, thenationalnews.com, brecorder.com(로이터 전재),
defensenews.com(로이터 전재), timesofisrael.com, en.protothema.gr, eurasiareview.com, edwardconard.com(블룸버그 요약),
federalreserve.gov, sca.isr.umich.edu, philadelphiafed.org, newyorkfed.org, stocktitan.net,
sedaily.com, etoday.co.kr, ajunews.com, seoulfn.com, fnnews.com, hankyung.com, mt.co.kr, ebn.co.kr, tokenpost.kr,
news.sbs.co.kr, biz.heraldcorp.com

**막힘 (403/451/타임아웃):**
cnbc.com, thestreet.com, axios.com, schwab.com, japantimes.co.jp, qz.com, invezz.com, upi.com, thehill.com,
cnn.com(451), iea.org, stocktwits.com, forbes.com(직접 링크), npr.org·usnews.com(타임아웃이 잦음),
tomsguide.com·techradar.com(본문이 잘려서 옴)

CNBC 기사는 같은 내용이 Yahoo, 로이터 전재본, 한국 매체 인용으로 거의 다 있다. Google News RSS 링크(`news.google.com/rss/articles/...`)는 원문이 아니므로 `sources`에 넣지 않는다.
참고로 매일 수집되는 `data/{YYYYMMDD}/raw/news_us.json`에 한국어 마감 기사 제목 목록이 있다. 제목으로 검색해서 원문 URL을 찾으면 된다.

---

## 6. news.json 스키마

```json
{
  "week_start": "YYYY-MM-DD", "week_end": "YYYY-MM-DD", "build_date": "YYYYMMDD",
  "generated_at": "ISO8601+09:00", "status": "partial|complete",
  "sessions_covered": ["YYYY-MM-DD"], "sessions_pending": ["YYYY-MM-DD"],
  "events": [{
    "d": "YYYY-MM-DD",            // 미 동부 기준 발생일
    "session": "YYYY-MM-DD",      // 반영된 미국 정규장 날짜 (확장 필드)
    "kind": "data|policy|politics|geopolitics|oil|rates|fx|trade|company|earnings",  // 확장 필드
    "importance": 1,              // 1~3, 3이 주간 핵심 (확장 필드)
    "title": "짧은 한국어 제목",
    "what": "사실 1~2문장(한국어)",
    "actual_vs_expected": "데이터 발표일 때만. 아니면 빈 문자열",
    "sources": [{"outlet": "", "title": "원문 제목", "url": "실제로 연 URL", "published": "YYYY-MM-DD HH:MM TZ"}],
    "market_link": "언론이 연결한 시장 반응(완곡하게, 매체명 밝히기)",
    "assets": ["SPX","IXIC","DJI","SOX","VIX","US10Y","US2Y","DXY","USDJPY","USDKRW","WTI","GOLD", "티커..."],
    "confidence": "high|medium|low"
  }],
  "calendar_next": [{"date": "YYYY-MM-DD", "event_ko": "", "source": "URL"}],
  "pending": ["아직 안 나온 것"],
  "story_candidates": ["주간을 한 줄로 엮는 후보 2~4개(완곡)"],
  "source_caveats": ["매체 간 숫자 불일치, 오기, 쓰지 않기로 한 내용"]
}
```

`confidence` 기준:
- `high`: 사실이 2개 이상 매체에서 일치하고, 언론이 시장 움직임과 명시적으로 연결함
- `medium`: 매체가 1개뿐이거나 숫자가 다르거나 연결이 간접적임
- `low`: 사실은 확인됐지만 시장과 직접 연결한 보도가 없음(정치 발언, 우크라이나 등)

---

## 7. 검증 스크립트

```bash
cd C:/Users/Jeff/Documents/GitHub/asset/market-close/jobs
PYTHONIOENCODING=utf-8 C:/Users/Jeff/Documents/GitHub/asset/backend/.venv/Scripts/python.exe - <<'PY'
import json
p = '../data/weekly_us/20260913/news.json'   # BUILD_DATE 교체
j = json.load(open(p, encoding='utf-8'))
bad = ['때문에', '이유', '덕분', '탓', '영향으로', '나오자', '힘입어']
hits = []
def walk(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            if k != 'sources':
                walk(v, f'{path}.{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, f'{path}[{i}]')
    elif isinstance(o, str):
        hits.extend((b, path) for b in bad if b in o)
walk(j)
for e in j['events']:
    assert e['sources'] and all(s['url'].startswith('http') for s in e['sources']), e['title']
    assert e['confidence'] in ('high', 'medium', 'low'), e['title']
    assert 'news.google.com' not in json.dumps(e['sources']), e['title']
print('forbidden hits:', hits or 'none')
print('events:', len(j['events']), '| pending:', len(j['pending']), '| status:', j.get('status'))
PY
```

---

## 8. 첫 실행에서 정리한 이번 주 흐름 (금요일 전까지)

- 배경(9/4~9/7): 8월 고용 +16.2만 명, 실업률 4.1%. 9월 인상 확률 약 60%. 트럼프·밴스가 금리 인하를 공개 요구함. 연준 블랙아웃은 9/5부터. 미 특사가 모스크바·키이우를 방문했으나 합의 발표는 없음.
- 9/8(화): 후티가 사우디 에너지시설을 공격하고 하르그섬 인근 충돌이 보도됨. 캐나다 보복관세 발효, 트럼프가 봄바디어를 경고. 다우 −1.18%. 반도체는 강세(인텔 +9%, 퀄컴-아마존 계약). 헬스케어 약세(암젠 −10%). 베선트가 "I am the house"라고 발언했고 엔화는 강세.
- 9/9(수): 미군이 이란 유조선 5척을 파괴했고 이란은 선박 10척 공격으로 맞섬. 브렌트 101.21달러. 재무부 바이백을 60억 달러로 3배 늘렸으나 10년물은 4.83~4.85%로 상승. 애플이 폴더블 듀오를 공개(당일 −0.28%). 메타 뮤즈로 +6.55%. SK하이닉스 ADR +7.05%(상장 후 최고).
- 9/10(목): PPI 전년비 5.4%(예상 5.3%), 근원 전월비 0.2%(예상 0.3%). 후티가 모카를 장악했고 사우디 생산이 1990년 이후 최저. WTI 102.48달러(+6.69%). 10년물 4.95%, 30년물 19년 만의 최고. 인상 확률 약 70%. ECB가 2.5%로 인상. SOX −2.66%. 애플 +3.56%. 오라클은 장중 −5.38%였고 실적 발표 뒤 시간외 상승. 어도비는 CEO 교체를 발표.
- 9/11(금): CPI를 비롯한 금요일 항목은 모두 `pending`.
