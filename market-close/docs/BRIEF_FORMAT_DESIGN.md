# 평일편 '수급 브리핑' 형식 설계 — JJ 2026-09-15 밤 지시 (헌터 7슬롯은 주간 브리핑용으로 보관)

JJ: "매일 내 영상을 보려는 이유는 그날 장의 수급, 돈이 어디로 갔는지를 브리핑하는 게 우선이야. 수급(외국인·기관·개인·기타)을 나열해 보여주고, 돈이 빠졌는지 들어왔는지, 지금 어디에 정체돼 있고 어디로 옮겨 갔는지. 예: 이차전지·로봇에 돈이 들어왔다 → 수급 현황 다 보여주고 → 코스피·코스닥 등락률과 누가 샀는지 빠졌는지 → 이차전지·로봇으로 돈이 들어왔다 → 그 카테고리 안에서도 외국인·기관·개인 → 대장주 1개와 가장 많이 오른 종목 1개, 외국인·개인·기관이 샀는지 팔았는지 → 관련 뉴스가 있는지, 뉴스와 맞물려 오른 건지 → 내일 주시할 포인트."
견본 대본: `docs/scripts/2026-09-15_brief.md`. 내일(9/16) 15:55 자동 제작부터 이 형식.

## 0. 원칙
- 순서 고정 7장면, 대사는 매일 새로(전 편과 글자 같은 문장 0, `script_memory.pick`), 이어지는 사실은 "닷새째·9월 들어 매일·N일째"로.
- 습니다체, 한 문장 숫자 ≤2, 100억 단위(1조 5,700억), 부호·방향을 말한다(순매도/순매수, 하락/상승). 종목 추천·목표주가·전망 금지. 질문은 안 써도 된다 — 브리핑이다. "여러분" 금지. 자기 영상 언급 금지.
- 길이 900~1,150자(약 2분~2분 20초). 시그니처 고정, 애프터마켓 문장 9/18까지.
- 데이터가 없으면 그 장면을 비우지 않고 대체 규칙(§2)으로 채운다. 어떤 예외에도 영상은 나간다(검사 3회 실패 → aplus 폴백).

## 1. 장면 ↔ 데이터 (id b0~b6)
| id | 내용 | 데이터 | 화면 |
|---|---|---|---|
| b0 코스피 수급 | 외국인·기관·개인·기타법인 순매수를 큰 것부터가 아니라 **외국인 → 기관 → 개인 → 기타법인** 고정 순서로 나열. 외국인·기관 연속일(inv_streak), 기타법인은 상위 2종목·자사주 비중·"9월 들어 매일/N일째"(continuity) | investors.kospi, inv_streak, top_others, buybacks, continuity | 막대 4개(고정 순서), 기타법인 막대 아래 `자사주 99%` |
| b1 코스닥 수급 + 지수 | 코스닥 외국인·기관·개인 + 지수 둘(코스피/코스닥 종가·등락) + 한 줄 판정("코스피는 외국인·기관이 빼고 개인·자사주가 받은 날, 코스닥은 …") | investors.kosdaq, kospi, kosdaq_index | 막대 3개 + 지수 카드 2 |
| b2 돈이 빠진 곳·정체된 곳 | 유출 1위 업종(외+기 합, 외/기 분리, N일째, 어제 대비) + 그 업종 대장주 등락(정체: 값은 안 빠졌는데 돈은 나감 / 자사주가 받침) + 나머지 유출 업종 2~3개 | flows.table_t(<0), flow_store 종목행(ret·value), stock_flows, top_others, others_top | 유출 가로막대(최대 4) + 대장주 등락 칩 + `자사주 +1.63조` 막대 |
| b3 돈이 들어온 곳 | 유입 업종 상위 2(외/기 분리, 등락, 순매수 종목 이름 ≤4, N일째) + 유출 1위 대비 비율 | flows.table_t(>0) | 유입 가로막대(외/기 두 색) + 비율 칩 |
| b4 종목 둘 | ① 유입 1위 업종의 **대장주**(sectors[].leader 또는 거래대금 최대) ② **가장 많이 오른 종목**(그 업종 구성 종목 ∪ 오늘 이슈 종목, 등락률 최대). 각 등락률·외국인·기관·개인 순매수·거래대금 + "누가 밀어 올렸나" 한 줄(최대 순매수 주체; 셋 다 작으면 "큰손 돈은 작았다") | raw/brief_stocks.json(compute 단계에서 ka10059 로 두 종목 당일 행 수집) | 종목 카드 2장(등락률 크게 + 외/기/개 세 줄 + 거래대금) |
| b5 뉴스 | 유입 1위 업종·두 종목 관련 뉴스 ≤2(제목·매체) + 맞물림 판정: 뉴스 있고 외+기 순매수 → "뉴스와 큰손 돈이 같이 갔다"; 뉴스 있고 큰손 작음/매도 → "뉴스가 값을 먼저 올렸다"; 뉴스 없음 → "뉴스 없이 수급만 움직였다" | events.json[d].head(있으면 우선) + news_kr.json(테마·종목 이름 쿼리 추가 수집) | 뉴스 카드 ≤2 + 판정 줄 |
| b6 내일 포인트 | 2~3개: 외국인 순매도 N+1일째 / 유입 업종 이틀째 / 기타법인 선 / 다음 이벤트(FOMC 등 schedule) + 애프터마켓 + 시그니처. next_q 는 ledger.parse_q 형태 | inv_streak, flows, schedule | S6H 재사용(번호 칩·이벤트·애프터마켓·로고) |

## 2. 대체 규칙
- 유입 업종이 없는 날: b3 = "들어온 곳이 없었습니다. 가장 덜 빠진 곳은 …", b4 = 유출 1위 업종 대장주 + 그 업종에서 가장 덜 내린(또는 오른) 종목, b5 = 유출 업종 뉴스.
- 이슈(events.json) 없는 날: b5 는 news_kr.json 에서 업종·종목 이름이 제목에 든 기사만. 없으면 "뉴스 없이 수급만" 한 문장.
- 기타법인이 작은 날(<3,000억): b0 에서 자사주 문장 생략, 대신 "기타법인 N억" 한 마디.
- 코스닥 수급 없음: b1 은 지수 둘 + 코스피 판정 한 줄.
- callback(어제 약속)은 b6 앞머리 한 문장으로 회수("어제 보자고 한 외국인 순매도, 닷새째 이어졌습니다") — b0 에서 이미 N일째를 말했으면 생략.

## 3. 파일·계약
- `jobs/collect_brief.py` (compute 단계, flows 뒤): 유입 1위 업종의 대장주·최대 상승 종목 코드 선정 → ka10059 당일 행(외/기/개·거래대금·등락) → `raw/brief_stocks.json` `{theme, stocks:[{code,name,role,pct,foreign,inst,indiv,value}]}`; `collect_news.main(d,"kr", extra=[...])` 에 업종·종목 쿼리 추가.
- `jobs/narrate_brief.py`: `build(c, avoid=None, attempt=0) -> dict` — 반환 키는 build_aplus 호환 + `format="brief"`, `brief` 사전(화면용, 장면마다 `steps` = 문장 수), scenes id `b0..b6`, `next_q`, `watch`, `hook_parts`(썸네일·제목용: 첫 줄 "외국인 1조 5,700억 순매도", 둘째 줄 "돈은 이차전지·로봇으로"), `protagonist`, `contrast`, `check`, `bars`, `s2_title`, `s3_title`, `s3_story`, `event_used`, `others_top`, `weekend_watch`, `hook_id="B"`, `devices`.
  ```
  brief = {
   "b0": {"market":"코스피","bars":[{"name":"외국인","v":-15736,"days":-5},{"name":"기관","v":-9044,"days":-3},{"name":"개인","v":8324},{"name":"기타법인","v":16431}],
          "others":{"v":16431,"top":[{"name":"SK하이닉스","v":11182},{"name":"삼성전자","v":5084}],"share":0.99,"days_word":"9월 들어 매일"}},
   "b1": {"market":"코스닥","bars":[{"name":"외국인","v":241},{"name":"기관","v":1107},{"name":"개인","v":-1398}],
          "index":[{"name":"코스피","close":6627.26,"chg_pct":-0.85},{"name":"코스닥","close":812.41,"chg_pct":0.70}],"verdict":"..."},
   "b2": {"out":[{"theme":"반도체","v":-20429,"foreign":-13373,"inst":-7056,"ret":-0.24,"streak":-5,"y":-38339}, {...}],
          "leaders":[{"name":"삼성전자","pct":-0.2},{"name":"SK하이닉스","pct":-0.41}],"support":{"label":"자사주","v":16266}},
   "b3": {"in":[{"theme":"이차전지","v":937,"foreign":479,"inst":458,"ret":3.1,"names":["LG에너지솔루션","삼성SDI","포스코퓨처엠","에코프로비엠"],"streak":1}, {...}],
          "ratio":{"out_theme":"반도체","out":20429,"in":1313,"text":"16분의 1"}},
   "b4": {"stocks":[{"name":"LG에너지솔루션","role":"대장주","theme":"이차전지","pct":3.98,"foreign":8,"inst":413,"indiv":-324,"value":1215,"driver":"기관"},
                    {"name":"삼현","role":"최대 상승","theme":"로봇","pct":29.8,"foreign":13,"inst":26,"indiv":-37,"value":548,"driver":"작음"}]},
   "b5": {"news":[{"title":"...","source":"파이낸셜뉴스","theme":"이차전지"},{...}],"verdict":[{"theme":"이차전지","kind":"together","text":"뉴스와 외국인·기관 순매수가 같이 갔다"},{"theme":"로봇","kind":"news_first","text":"..."}]},
   "b6": {"watch":[{"q":"외국인 순매도가 엿새째 이어지는지","threshold":"6거래일째"},{"q":"이차전지 순매수가 이틀째 이어지는지","threshold":"이틀째"}],
          "event":{"label":"미국 금리 결정","when":"목요일 새벽 3시","note":"인상 확률 92%"}|null,"after_market":true,"when":"저녁 5시"}
  }
  ```
- `render/src/v4/BriefV4.tsx`: `BRIEF_COMP = {b0..b6}`; `Video.tsx` 는 `p.format === "brief"` 면 이 맵을 본다. HunterV4 의 VBars/HBars/Logo/Grad/S6H 를 재사용(필요하면 HunterV4 에서 export).
- `jobs/qa_script.check_brief(scenes, comp)`: 7장면 존재·순서, 장면별 문장 수 상한(b0 5·b1 4·b2 5·b3 5·b4 5·b5 4·b6 5), 한 문장 숫자 ≤2, 금지어(여러분·지난 영상·사세요·목표가·비중·관망·전망), 마지막 문장 시그니처, 전 편 exact 겹침 0(창 5·올라간 편·장부 문장 예외), 총 ≤1,150자. 실패 문자열 `"[b2] 규칙 :: 문장"`.
- `jobs/compute.py`: `script_format == "brief"` 분기 — 헌터와 같은 재시도·폴백 구조(`_build_hunter` 를 일반화해 `_build_fmt(name, module)`), narration_inputs 에 `brief_stocks`, `news_items`, `flow_day`(flow_store.load_day(d)["stocks"]·["sectors"]) 추가. `data/publish_config.json` `script_format: "brief"`.
- `jobs/brief_try.py DATE… --cross [--attempt N]`: hunter_try 와 같은 오프라인 시험(9/15 는 raw/brief_stocks.json 이 없으면 collect_brief 를 그 자리에서 돌려 scratch 에 저장).

## 4. 검증
- `brief_try.py 20260911 20260914 20260915 --cross`: 세 편 check_brief 통과, exact 0, 900~1,150자. 9/15 대본이 `docs/scripts/2026-09-15_brief.md` 와 같은 사실·같은 순서인지.
- 5일 연쇄 폴백 0, 조사 오류 0. tsc 통과, 9/15 실 데이터 스틸 7장면×2.
