# 평일편 '수급 브리핑' 형식 = 경제사냥꾼 7슬롯 위에 수급 순서를 고정한 것 (JJ 2026-09-15 밤)

JJ: "매일 보려는 이유는 그날 장의 수급, 돈이 어디로 갔는지 브리핑이 우선. 수급(외국인·기관·개인·기타)을 나열해 보여주고 돈이 빠졌는지 들어왔는지, 어디에 정체돼 있고 어디로 옮겨 갔는지 → 그 업종 안에서도 주체별 → 대장주 1 + 최대 상승 1의 주체별 매매 → 관련 뉴스와 맞물렸는지 → 내일 볼 포인트." 그리고 "경제사냥꾼 md 시스템 형식을 무조건 이용하면서 이 판을 이어간다."
따라서 **장치(정본 `docs/SCRIPT_SYSTEM_HUNTER_v1.0.md`)는 그대로, 내용의 순서는 매일 같은 수급 순서로 고정**한다. 헌터 1차 구현이 어지러웠던 이유는 S3 체인이 날마다 다른 블록(콜백/이슈/정체…)을 골랐기 때문이다 — 이제 체인은 고정이다.
견본 대본(내용 순서): `docs/scripts/2026-09-15_brief.md`. 내일(9/16) 15:55 자동 제작부터 이 형식.

## 0. 원칙
- 장면 id 는 헌터와 같다: `s0 s1 s2 s3a s3b s3c s4 s5 s6`. 장치 대응은 아래 표. 대사는 매일 새로(전 편과 글자 같은 문장 0, `script_memory.pick`), 이어지는 사실은 "닷새째·9월 들어 매일·N일째"로.
- 습니다체, 한 문장 숫자 ≤2, 100억 단위(1조 5,700억), 부호·방향을 말한다. 종목 추천·목표주가·전망 금지. "여러분"·자기 영상 언급 금지. 시그니처 고정("누가샀나였습니다. 국장 마감은 매일 저녁 5시에 올라옵니다.", d==20260915 는 "내일부터 매일"), 애프터마켓 문장 9/18까지.
- 길이 950~1,150자. 데이터가 없으면 장면을 비우지 않고 §2 대체 규칙으로 채운다. 검사 3회 실패 → build_aplus 폴백(영상은 나간다).

## 1. 장면(고정 순서) ↔ 장치 ↔ 데이터
| id | 장치(정본) | 내용(매일 이 순서) | 데이터 | 화면 |
|---|---|---|---|---|
| **s0** | 모순 후킹 | 오늘 수급에서 부딪히는 숫자 둘. 후보(헌터 M1~M7 그대로, 세기 순): M1 주인공 순매도 ↔ 지수 소폭 · M2 오후 2시 ↔ 마감 · M3 업종 유출 ↔ 등락 소폭 · M7 유출 ↔ 유입 N분의 1 · M4 이슈 등락 ↔ 유입 작음 · M5 · M6. 첫 단어 숫자/주체, 인사·날짜 금지 | investors, intraday, flows, event | S0H 재사용 |
| **s1** | 단일 질문 선언 | 질문은 **항상 돈의 행방**: "오늘 그 돈이 어디로 갔느냐 / 누가 받았느냐" 계열(틀 5벌 회전). "오늘은 이것 하나만 봅니다" 류 꼬리 | — | S1H 재사용 |
| **s2** | 대변→차단 + **코스피 수급 나열** | 뻔한 답("개인이 받았다"/"새 돈이 들어왔다") → 외국인 → 기관 → 개인 순으로 **넷 다 숫자로** 나열(연속일 포함) → "그런데 [화면 지시어] 네 번째 막대" 기타법인 + 상위 2종목·자사주 비중·"9월 들어 매일/N일째" → 다음 질문(코스닥은 어땠나) | investors.kospi, inv_streak, top_others, continuity | S2H 재사용(막대 4개 고정 순서, 자사주 카드) |
| **s3a** | 데이터 블록 1 + 콜백 | **코스닥 수급 3주체 + 지수 둘**(코스피·코스닥 종가·등락) + 한 줄 판정(코스피는 외국인·기관이 빼고 개인·자사주가 받은 날, 코스닥은 …) + **어제 보자고 한 숫자 회수**(도장 이어짐/끊김, 월요일은 주말편 것도) → "그런데 [반전]" → 질문("그럼 빠진 돈은 어느 업종에서 나갔을까요?") | investors.kosdaq, kospi/kosdaq index, callback, weekend_watch | **새 화면** S3aB: 코스닥 막대 3 + 지수 카드 2 + 콜백 카드·도장 |
| **s3b** | 데이터 블록 2 | **돈이 빠진 곳·정체된 곳**: 유출 1위 업종(외/기 분리, N일째, 어제 대비) + "왼쪽 막대를 보세요" + 그 업종 대장주 등락(값은 안 빠졌는데 돈은 나감) + 자사주 받침(있으면) + 나머지 유출 2~3개 → "그런데" 또는 질문("그럼 그 돈은 어디로 들어갔을까요?") | flows.table_t(<0), flow_day 종목행, stock_flows, others_top | S3bH 개조: 유출 가로막대 + 대장주 등락 칩 + 자사주 막대 |
| **s3c** | 데이터 블록 3 + 이동 선언 | **돈이 들어온 곳**: "이번엔 들어온 쪽입니다"(이동 선언 1회) + 유입 상위 2 업종(외/기 분리, 등락, 순매수 종목 ≤4, N일째) + 유출 1위 대비 비율("16분의 1") → 질문("그럼 그 안에서 누가 샀을까요?") | flows.table_t(>0) | **새 화면** S3cB: 유입 가로막대(외/기 두 색) + 종목 이름 + 비율 칩 |
| **s4** | 1차 자료 한 칸 | "직접 열어봤습니다, 키움 종목별 투자자 표, M월 D일 마감 기준" → **대장주 1 + 최대 상승 1**: 등락·외국인·기관·개인·거래대금 + 계산 1개(검산): 주도 주체 순매수 ÷ 거래대금(%) 또는 두 종목 큰손 합 ÷ 개인 순매도(배) + "누가 밀어 올렸나" 한 줄 | raw/brief_stocks.json(compute 단계 ka10059 수집) | **새 화면** S4B: 표(종목 2행 × 외/기/개/거래대금) + 강조 칸 + 계산식 |
| **s5** | 양면 판정 + 뒤집히는 조건 + 콜백 + 한계 | **뉴스와 맞물렸나**: 뉴스 ≤2(제목·매체) → 양면 프레임 고정 "뉴스가 올린 값이면 큰손 돈은 작습니다 / 돈이 올린 값이면 외국인·기관이 같이 삽니다 → 오늘 [업종]은 [돈/뉴스] 쪽입니다"(두 업종이면 각각 한 줄) → 뒤집히는 조건 하나(임계값: "내일 [업종]에 외국인·기관 돈이 N억 넘게 들어오면") → S0 숫자 콜백(계산) → 한계 1문장(주체별 합계라 종목 사이 이동은 안 보임 등) | news_kr.json(업종·종목 이름 쿼리), events.json head, brief_stocks | **새 화면** S5B: 뉴스 카드 ≤2 + 좌우 판정 카드 + 조건 줄 + 콜백 칩 |
| **s6** | 내일 관측값 + 시각 + 시그니처 | 2~3개(외국인 순매도 N+1일째 / 유입 업종 이틀째 / 기타법인 선) + 다음 이벤트 시각 + 애프터마켓 + 시그니처. next_q 는 ledger.parse_q 형태 | inv_streak, flows, schedule | S6H 재사용 |

문장 규칙 10·체크리스트 11항(정본 §4·§5)은 그대로 검사한다. 블록(s3a·s3b·s3c) 끝은 "그런데" 문장 또는 질문, 화면 지시어 ≥4, "그런데" 블록당 1회.

## 2. 대체 규칙
- 유입 업종 없음: s3c = "들어온 곳이 없었습니다. 가장 덜 빠진 곳은 …" + 비율 대신 "전부 유출". s4 = 유출 1위 업종 대장주 + 그 업종에서 가장 덜 내린 종목. s5 = 유출 업종 뉴스.
- 이슈(events.json) 없음: s5 뉴스는 news_kr.json 제목에 업종·종목 이름이 든 기사만. 없으면 "뉴스 없이 수급만 움직인 날" + 판정은 돈 쪽.
- 기타법인 <3,000억: s2 자사주 문장 생략, "기타법인 N억" 한 마디.
- 코스닥 수급 없음: s3a 는 지수 둘 + 코스피 판정 + 콜백.
- 어제 약속 없음: s3a 콜백 문장 생략, 대신 외국인 연속일 사실.
- brief_stocks 수집 실패: s4 는 flow_day 의 외/기·등락·거래대금만으로(개인은 말하지 않음), 계산은 외+기 ÷ 거래대금.
- 오후 2시 스냅 없음: M2 제외. intraday 가 16시 이후 수집이면 M2 제외.

## 3. 파일·계약
- `jobs/collect_brief.py`(compute 단계, flows 뒤): 유입 1위 업종(없으면 |순매수| 최대 업종)의 대장주(flow_store sectors[].leader → 없으면 거래대금 최대)와 최대 상승 종목(그 업종 구성 종목 ∪ raw/event.json 종목, 등락 최대) → ka10059 당일 행(외/기/개·거래대금·등락, events.json pct_fix 우선) → `raw/brief_stocks.json` `{theme, stocks:[{code,name,role:"대장주"|"최대 상승",theme,pct,foreign,inst,indiv,value,close}]}`. 실패해도 예외 없이 `{}` 저장·로그. `collect_news.main(d,"kr", extra=[업종명+" 강세", 종목명1, 종목명2])` 로 뉴스 추가 수집(run_day compute 단계 순서: collect_news 기본 → collect_event → collect_brief → collect_news extra).
- `jobs/narrate_brief.py`: `build(c, avoid=None, attempt=0) -> dict`. 반환 = 헌터와 같은 키(build_aplus 호환 + `format="brief"`, `hunter` 사전을 **그대로 재사용**해 화면이 읽게 하되 필요한 키를 더한다):
  ```
  hunter = {
   "s0": {헌터 S0 계약 그대로},
   "s1": {"q","tail","text"},
   "s2": {"naive","naive_name","bars":[외국인,기관,개인 순 고정, days],"reveal":{"name":"기타법인","v","days","days_word","top":[…],"share"},"said_share":true},
   "s3a": {"kosdaq":{"bars":[{"name","v"}×3]}, "index":[{"name":"코스피","close","chg_pct"},{"name":"코스닥",…}], "verdict":"코스피는 … 코스닥은 …",
           "promise","result","ok","num","changed":{…}|null, "steps":[…]},
   "s3b": {"out":[{"theme","v","foreign","inst","ret","streak","y"},…≤4], "leaders":[{"name","pct"}…], "support":{"label":"자사주","v"}|null, "steps":[…]},
   "s3c": {"in":[{"theme","v","foreign","inst","ret","names","streak"},…≤2], "ratio":{"out_theme","out","in","text"}|null, "steps":[…]},
   "s4": {"doc":"키움 종목별 투자자 표 · 9/15 마감 기준", "date", "stocks":[{"name","role","theme","pct","foreign","inst","indiv","value","driver"}×2],
          "calc":{"expr","result","lhs","rhs","value","kind","verified":true}, "steps":[…]},
   "s5": {"news":[{"title","source","theme"}≤2], "a":"뉴스가 올린 값", "b":"돈이 올린 값", "verdicts":[{"theme","side":"a"|"b","text"}], "verdict":"a"|"b",
          "condition","limit","support":{"label","value"},"callback":{"a","b","text"}, "steps":[…]},
   "s6": {헌터 S6 계약 그대로}
  }
  ```
  scenes 는 `{"id","min","tts","sub","steps"}`(steps 수 = 문장 수). 문장 후보 ≥3벌, `script_memory.pick(cands, d, exact, masked, avoid=…, offset=attempt)` 문장 단위 회피, continuity 로 이어짐 문장. 헌터의 `hwon/hshort/Picker/J/subj/obj/_was/ro/_callback/_s6` 는 import 해 재사용한다(복사 금지).
- `render/src/v4/BriefV4.tsx`: `BRIEF_COMP = {s0:S0H, s1:S1H, s2:S2H, s3a:S3aB(새), s3b:S3bB(새: 유출 막대+대장주 칩+자사주), s3c:S3cB(새), s4:S4B(새), s5:S5B(새), s6:S6H}`; `Video.tsx` 는 `p.format === "brief"` 면 이 맵. HunterV4 에서 VBars/HBars/Grad/Logo/useSteps/short/spoken/fmtPctS/S0H/S1H/S2H/S6H 를 export 해 쓴다.
- `jobs/qa_script.check_brief(scenes, comp)`: check_hunter 의 11항·규칙 검사 + 브리핑 고정 내용 검사: s2 에 외국인·기관·개인 세 이름과 숫자 3개 이상(문장별 ≤2), s3a 에 코스닥·코스피, s3b 에 빠졌|나갔|순매도, s3c 에 들어왔|순매수|들어온 곳이 없었, s4 에 두 종목 이름과 외국인/기관/개인, s5 에 뉴스·쪽입니다·뒤집히는 조건, s6 임계값·시그니처. 실패 `"[s3b] 규칙 :: 문장"`. 총 ≤1,150자 실패, <900 경고.
- `jobs/compute.py`: `script_format == "brief"` → `_build_fmt(narrate_brief, "브리핑")`(헌터와 같은 재시도·폴백), narration_inputs 에 `brief_stocks`·`news_items`·`flow_day` 추가. `data/publish_config.json` `script_format: "brief"`.
- `jobs/brief_try.py DATE… --cross [--attempt N]`: hunter_try 와 같은 오프라인 시험(raw/brief_stocks.json 없으면 collect_brief 를 scratch 출력으로 그 자리에서 실행).

## 4. 검증
- `brief_try.py 20260911 20260914 20260915 --cross`: check_brief 통과, exact 0, 950~1,150자. 9/15 결과가 `docs/scripts/2026-09-15_brief.md` 의 사실·순서와 같은지(문장은 달라도 됨).
- 5일 연쇄 폴백 0, 조사 오류 0, tsc 통과, 9/15 실 데이터 스틸 9장면×2.
