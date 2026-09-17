# -*- coding: utf-8 -*-
"""누가샀나 국장 주간 결산 v2(토요일) — 요일별로 돈이 어디서 빠져 어디에 머물렀나.

JJ 2026-09-17: "주간 브리핑은 그 주에 있었던 일과 각 요일마다 돈이 어디에 머물렀고 어떤 종목 어떤 업종에 들어갔는지를 알려 줘야 해.
월화수목금토일 표로 — 월~금은 돈이 나간 업종(외국인·개인·기관 전부 표시), 들어온 업종과 종목도 요일마다. 마지막 날 금요일엔 돈이 어디에
정체해 있는지 브리핑. 요일마다 오른 종목은 어떤 뉴스·이슈가 있었는지 엮어서, 이벤트로 오른 건지 진짜 돈이 들어온 건지."
+ 돈이 어디로 갈지 '예상'은 전망 금지 규칙 때문에 **과거 기록**으로만 말한다(지난 2년 같은 모양이 몇 번, 다음 거래일 어땠나).

입력: computed_weekly.json(weekly_data.build — days_detail · parked · history · inv · kospi) + news_verified.json(events)
출력: build_weekly(w, news) → run_weekly 가 쓰는 모양 그대로 {"scenes":[{id,min,tts,sub,ask}], title, threads, threads_reply, hook_parts, issues, est_sec}

장면(화면은 render/src/v4/WeeklyV5.tsx — 월~일 표를 w2~w5 가 같이 쓰고 말하는 요일 줄을 밝힌다)
  w0 훅: 한 주 내내 돈이 빠진 업종 ↔ 마지막 날 돈이 머문 업종
  w1 질문: 한 주 동안 돈은 어디서 빠져 어디에 머물렀을까요? + 고정 꼬리
  w2 한 주 요약: 외국인·기타법인 한 주 합, 코스피 한 주 등락
  w3·w4 요일별(마지막 날 빼고 앞뒤로 나눔): 빠진 업종 외국인·기관·개인 → 들어온 업종·종목 → 크게 오른 종목의 이슈와 돈
  w5 마지막 날 + 돈이 머문 곳 + 과거 기록
  w6 다음 주 월요일에 볼 것 + 끝 멘트
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (os.path.join(os.path.dirname(ROOT), "backend"), ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from checks import forbidden  # noqa: E402
from narrate_brief import J, dko, hwon, obj, pct2, subj  # noqa: E402

SIGNOFF = "누가샀나 주간 결산이었습니다. 평일엔 매일 저녁 5시에 국장 마감이 올라옵니다."
WDN = {"월": "월요일", "화": "화요일", "수": "수요일", "목": "목요일", "금": "금요일"}
CPS = 7.35                     # 브리핑 음성 실측 초당 글자
MAX_CHARS = 1300               # 3분(쇼츠) 선
MIN_SEC = {"w0": 5.0, "w1": 4.0, "w2": 6.0, "w3": 8.0, "w4": 8.0, "w5": 8.0, "w6": 6.0}
# 길이가 넘치면 뺄 문장(앞에서부터). 요일마다 빠진 업종의 외국인·기관·개인, 들어온 업종, 돈이 머문 곳은 빼지 않는다(JJ 요구).
DROP = ["w2.kospi", "day.in2", "w5.hist3", "day.riser_small", "w5.park_days", "day.riser", "w5.hist", "w6.q2"]


def _verb(v: float) -> str:
    return "샀" if v > 0 else "팔았"


def _pick(cands: list[str], key: str) -> str:
    """주 번호로 돌린다(지난주와 같은 틀을 매주 쓰지 않게)."""
    return cands[sum(ord(c) for c in key) % len(cands)]


def _news_for(news: dict | list | None, d: str, name: str | None, theme: str | None) -> dict | None:
    evs = news.get("events") if isinstance(news, dict) else (news or [])
    for e in evs or []:
        if not isinstance(e, dict) or str(e.get("d", "")).replace("-", "")[:8] != d:
            continue
        if e.get("verified") is False or e.get("use_in_script") is False or e.get("confidence") not in ("high", "medium"):
            continue
        blob = " ".join(str(e.get(k) or "") for k in ("title", "what", "our_data", "stock", "theme", "reason"))
        if (name and name in blob) or (theme and theme in blob):
            return e
    return None


SAYS: dict = {}     # 화면용: 요일마다 대본이 말한 종목과 이슈(riser_says)


def _ro(w: str) -> str:
    ch = (w or " ")[-1]
    if "가" <= ch <= "힣":
        b = (ord(ch) - 0xAC00) % 28
        return w + ("로" if b in (0, 8) else "으로")
    return w + "로"


def _riser_line(x: dict, news, used: set) -> tuple[str, str] | None:
    """(태그, 문장) — 그날 크게 오른 종목 하나: 이슈가 확인되면 '…소식에 N% 올랐고' + 돈 판정."""
    best = None
    for r in x.get("risers") or []:
        if r["name"] in used:
            continue
        ev = _news_for(news, x["d"], r["name"], r.get("theme"))
        rank = (1 if ev else 0, 1 if r["verdict"]["side"] == "money" else 0, r["ret"] or 0)
        if best is None or rank > best[0]:
            best = (rank, r, ev)
    if not best:
        return None
    _, r, ev = best
    used.add(r["name"])
    SAYS[x["d"]] = {"name": r["name"], "reason": (ev or {}).get("reason") or ""}
    v, fi, P = r["verdict"]["side"], r["verdict"]["fi"], pct2(r["ret"])
    reason = (ev or {}).get("reason") or ""
    k = sum(ord(c) for c in x["d"]) % 3
    head = (f"{J(r['name'])} {reason} 소식에 {P} 올랐고" if reason else
            [f"{J(r['name'], '이', '가')} {P} 올랐고", f"눈에 띈 종목은 {r['name']}, {P} 올랐고", f"{J(r['name'])} 하루 만에 {P} 뛰었고"][k])
    if v == "money":
        tail = (f"외국인과 기관이 {obj(hwon(fi))} 사서 이벤트에 진짜 돈까지 들어온 상승이었습니다." if reason else
                f"외국인과 기관이 {obj(hwon(fi))} 사서 실제로 돈이 들어온 상승이었습니다.")
        tag = "day.riser"
    elif v == "half":
        tail = "외국인과 기관 중 한쪽만 사서, 이벤트 쪽에 가까운 상승이었습니다." if reason else "외국인과 기관 중 한쪽만 사서, 한쪽 돈만 들어온 상승이었습니다."
        tag = "day.riser_small"
    elif v == "indiv":
        tail = "외국인과 기관보다 개인이 끌어올린 상승이었습니다."
        tag = "day.riser_small"
    else:
        tail = "큰돈이 만든 상승은 아니었습니다."
        tag = "day.riser_small"
    return tag, f"{head}, {tail}"


def _day_lines(x: dict, prev: dict | None, news, used: set, i: int = 0) -> list[tuple[str, str]]:
    """i = 그 주의 몇 번째 날 — 요일마다 문장 틀을 바꾼다(같은 틀 다섯 번이면 AI 티, JJ)."""
    wd = WDN.get(x["wd"], x["wd"] + "요일")
    L: list[tuple[str, str]] = []
    o = (x.get("outs") or [None])[0]
    if o:
        th = o["theme"]
        same = prev and (prev.get("outs") or [{}])[0].get("theme") == th
        opener = ([f"{wd}도 {th}에서 돈이 빠졌습니다.", f"{wd} 역시 가장 많이 빠진 곳은 {_ieot(th)}습니다.", f"{wd}까지 {th}에서 돈이 나갔습니다.",
                   f"{wd}에도 {_ieot(th)}습니다."][(i - 1) % 4] if same else
                  [f"{J(wd)} {th}에서 돈이 빠졌습니다.", f"{wd}에 가장 많이 빠진 곳은 {_ieot(th)}습니다."][i % 2])
        F, I = o["foreign"], o["inst"]
        if (F < 0) == (I < 0):
            who = f"외국인이 {hwon(F)}, 기관이 {obj(hwon(I))} {_verb(F)}습니다."
        else:
            who = f"외국인은 {obj(hwon(F))} {_verb(F)}고, 기관은 {obj(hwon(I))} {_verb(I)}습니다."
        L.append(("day.out", opener))
        L.append(("day.out_who", who))
        if o.get("indiv") is not None and abs(o["indiv"]) >= 1:
            L.append(("day.out_indiv", f"개인은 {obj(hwon(o['indiv']))} {_verb(o['indiv'])}습니다."))
    ins = x.get("ins") or []
    if ins:
        i0 = ins[0]
        names = [s["name"] for s in (i0.get("top_stocks") or [])][:2]
        t0 = i0["theme"]
        if names:
            nn = _and_names(names)
            cand = [f"들어온 곳은 {t0}, 그중 {_ieot(nn)}습니다.", f"대신 돈은 {_ro(t0)} 갔고, {nn}에 가장 많이 들어갔습니다.",
                    f"반대로 {t0}에는 돈이 들어왔고, {_ieot(nn)}가 중심{'이었' if False else '이었'}습니다.".replace(f"{_ieot(nn)}가 중심이었", f"{nn}{'이' if _has_bat(nn) else '가'} 중심이었"),
                    f"그날 돈이 들어간 곳은 {t0}, {_ieot(nn)}습니다."]
            L.append(("day.in", cand[i % len(cand)]))
        else:
            L.append(("day.in", f"들어온 곳은 {_ieot(t0)}습니다."))
        if len(ins) > 1:
            L.append(("day.in2", f"{J(ins[1]['theme'], '에도', '에도')} {hwon(ins[1]['net'])}이 들어왔습니다.".replace("에도에도", "에도")))
    elif x.get("inst_ins"):
        a = x["inst_ins"][0]
        L.append(("day.in", f"외국인과 기관을 더해 들어온 업종은 없었고, 기관만 {a['theme']}을 {hwon(a['inst'])}어치 샀습니다."))
    rl = _riser_line(x, news, used)
    if rl:
        L.append(rl)
    return L


def _and_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{names[0]}과 {names[1]}" if _has_bat(names[0]) else f"{names[0]}와 {names[1]}"


def _has_bat(w: str) -> bool:
    ch = (w or " ")[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch in "013678LMNR"


def _ieot(w: str) -> str:
    return w + ("이었" if _has_bat(w) else "였")


def _iyeo(w: str) -> str:
    return w + ("입니다" if _has_bat(w) else "입니다")


def build_weekly(w: dict, news=None) -> dict:
    dd = w.get("days_detail") or []
    issues: list[str] = []
    SAYS.clear()
    if not dd:
        return {"scenes": [], "title": "", "threads": "", "threads_reply": "", "hook_parts": [], "issues": ["days_detail 없음 — weekly_data.build 를 새 판으로 다시 돌려야 한다"], "est_sec": 0}
    wkey = w.get("week_end") or dd[-1]["d"]
    last = dd[-1]
    lwd = WDN.get(last["wd"], last["wd"] + "요일")
    park = w.get("parked") or {}
    outs = [x["outs"][0]["theme"] for x in dd if x.get("outs")]
    main_out = max(set(outs), key=outs.count) if outs else None
    n_out = outs.count(main_out) if main_out else 0
    inv_w = (w.get("inv") or {}).get("week") or {}

    parts: dict[str, list[tuple[str, str]]] = {k: [] for k in ("w0", "w1", "w2", "w3", "w4", "w5", "w6")}
    # w0 훅
    if main_out and park and n_out >= 3:
        a = f"이번 주 {main_out}에서는 {'5일 내내' if n_out >= 5 else dko(n_out).replace('째', '') + ' 동안'} 돈이 빠졌습니다." if n_out < len(dd) else f"이번 주 {main_out}에서는 {len(dd)}일 내내 돈이 빠졌습니다."
        b = f"그런데 {lwd} 장이 끝났을 때 돈이 머문 곳은 {_ieot(park['theme'])}습니다."
    else:
        F, O = inv_w.get("foreign") or 0, inv_w.get("others") or 0
        a = f"이번 주 외국인은 코스피에서 {obj(hwon(F))} {_verb(F)}습니다."
        b = f"같은 주 기타법인은 {obj(hwon(O))} {_verb(O)}습니다." if O else "그런데 코스피는 한 주 동안 버텼습니다."
    parts["w0"] = [("w0.a", a), ("w0.b", b)]
    # w1 질문
    parts["w1"] = [("w1.q", "한 주 동안 돈은 어디서 빠져 어디에 머물렀을까요?"), ("w1.tail", "월요일부터 하루씩 따라가 보겠습니다.")]
    # w2 한 주 요약
    F, O = inv_w.get("foreign") or 0, inv_w.get("others") or 0
    w2 = [("w2.inv", f"한 주 동안 외국인은 {obj(hwon(F))} {_verb(F)}고, 기타법인은 {obj(hwon(O))} {_verb(O)}습니다.")]
    kp = (w.get("kospi") or {}).get("week_chg_pct")
    if kp is not None:
        w2.append(("w2.kospi", f"코스피는 이번 주 {pct2(kp)} {'올랐' if kp > 0 else '내렸'}습니다."))
    parts["w2"] = w2
    # 요일별 — 마지막 날은 w5, 나머지는 앞뒤로 나눈다
    used: set = set()
    head = dd[:-1]
    cut = (len(head) + 1) // 2
    prev = None
    idx = 0
    for sid, chunk in (("w3", head[:cut]), ("w4", head[cut:])):
        for x in chunk:
            parts[sid] += _day_lines(x, prev, news, used, idx)
            prev = x
            idx += 1
    if not parts["w4"]:
        parts.pop("w4")
    parts["w5"] = _day_lines(last, prev, news, used, idx)
    if park:
        tops = [s["name"] for s in park.get("top_stocks") or []][:2]
        parts["w5"].append(("w5.park", f"{lwd} 장이 끝났을 때 돈이 머문 곳은 {park['theme']}입니다."))
        parts["w5"].append(("w5.park_who", f"외국인과 기관이 {obj(hwon(park['net']))} 넣었고, " + (f"{_and_names(tops)}에 가장 많이 들어갔습니다." if tops else "그 업종에 가장 많이 들어갔습니다.")))
        k = park.get("days_in") or 0
        parts["w5"].append(("w5.park_days", f"이번 주 {k}일 돈이 들어온 곳입니다." if k >= 2 else "이번 주 들어 처음 돈이 들어온 곳입니다."))
        h = w.get("history") or {}
        if h.get("n"):
            yrs = max(1, round((datetime.strptime(wkey, "%Y%m%d") - datetime.strptime(h["since"], "%Y%m%d")).days / 365))
            basis = "금요일" if h.get("basis") == "금요일" else "날"
            parts["w5"].append(("w5.hist", f"지난 {yrs}년 동안 {park['theme']}에 돈이 가장 많이 들어간 채 끝난 {basis}은 {h['n']}번이었습니다."))
            parts["w5"].append(("w5.hist2", f"그다음 거래일에도 {park['theme']}에 돈이 들어온 건 {h['cont']}번이었습니다."))
            parts["w5"].append(("w5.hist3", "이번에도 그럴지는 월요일 수급이 답합니다."))
    # w6 다음 주 볼 것
    st = abs(((w.get("inv") or {}).get("streak_end") or {}).get("foreign") or 0)
    fsell = (last.get("inv") or {}).get("foreign") or 0
    w6 = [("w6.q", "다음 주 월요일에 볼 것은 둘입니다.")]
    if st >= 1:
        w6.append(("w6.q1", f"외국인 순{'매도' if fsell < 0 else '매수'}가 {dko(st + 1)} 이어질 것인지."))
    if park:
        w6.append(("w6.q2", f"{park['theme']} 순매수가 {dko((park.get('streak') or 1) + 1)} 이어질 것인지."))
    w6.append(("w6.sign", SIGNOFF))
    parts["w6"] = w6

    # 길이 — 3분 선
    def total() -> int:
        return sum(len(t) for P in parts.values() for _, t in P)

    dropped = []
    for tag in DROP:
        if total() <= MAX_CHARS:
            break
        for sid in list(parts):
            before = len(parts[sid])
            parts[sid] = [p for p in parts[sid] if p[0] != tag]
            if len(parts[sid]) != before:
                dropped.append(f"{sid}:{tag}")
    if total() > MAX_CHARS:
        issues.append(f"길이 {total()}자 > {MAX_CHARS}자 — 뺄 문장이 없다")

    scenes = []
    for sid in ("w0", "w1", "w2", "w3", "w4", "w5", "w6"):
        P = parts.get(sid)
        if not P:
            continue
        tts = " ".join(t for _, t in P)
        sub = "" if sid == "w0" else " ".join(t for tg, t in P if tg != "w6.sign")
        ask = next((t for _, t in P if t.endswith("?")), "")
        scenes.append({"id": sid, "min": MIN_SEC[sid], "tts": tts, "sub": sub, "ask": ask, "tags": [tg for tg, _ in P]})
    for sc in scenes:
        if hits := forbidden.find(sc["tts"]):
            issues.append(f"{sc['id']} 금지어 {hits}")

    title = (f"{main_out}에서 {len(dd)}일 내내 빠진 돈, {lwd}엔 어디에 머물렀을까?" if (main_out and park and n_out >= len(dd)) else
             f"이번 주 돈은 어디서 빠져 {lwd}엔 어디에 머물렀을까?")
    th = [f"이번 주 {main_out}에서는 {n_out}일 동안 돈이 빠졌어." if main_out else "이번 주 돈이 어디로 갔는지 요일별로 따라가 봤어.",
          f"외국인은 한 주 동안 {hwon(F)}을 {'샀어' if F > 0 else '팔았어'}.".replace("을 샀어", "을 샀어")]
    for x in dd:
        if x.get("ins"):
            th.append(f"{x['wd']}요일엔 {x['ins'][0]['theme']}에 돈이 들어왔어.")
        else:
            th.append(f"{x['wd']}요일엔 돈이 들어온 업종이 없었어.")
    if park:
        th.append(f"{lwd} 장이 끝났을 때 돈이 머문 곳은 {park['theme']}{'이야' if _has_bat(park['theme']) else '야'}.")
        th.append(f"너넨 다음 주에도 {park['theme']}에 돈이 남을 거라고 봐?")
    else:
        th.append("너넨 다음 주 돈이 어디로 갈 거라고 봐?")
    threads = "\n".join(th)
    reply = "요일별로 빠진 곳과 들어온 곳은 영상에 표로 정리했어.\n영상 전체는 여기 → {YT}\n월요일엔 " + (f"{park['theme']}에 돈이 남는지 볼게." if park else "돈이 어디로 가는지 볼게.")
    return {"scenes": scenes, "title": title, "threads": threads, "threads_reply": reply, "hook_parts": [a, b], "hook_type": "v2",
            "dropped": dropped, "issues": issues, "est_sec": round(total() / CPS, 1), "chars": total(),
            "props_extra": {"weekly_v": 2, "riser_says": {d: v for d, v in SAYS.items() if any(v["name"] in t for P in parts.values() for tg, t in P if tg.startswith("day.riser"))}}}


if __name__ == "__main__":
    import json
    bd = sys.argv[1] if len(sys.argv) > 1 else "test0917"
    w = json.load(open(os.path.join(ROOT, "data", "weekly", bd, "computed_weekly.json"), encoding="utf-8"))
    nv = os.path.join(ROOT, "data", "weekly", bd, "news_verified.json")
    news = json.load(open(nv, encoding="utf-8")) if os.path.exists(nv) else {}
    out = build_weekly(w, news)
    print("제목:", out["title"])
    for sc in out["scenes"]:
        print(f"[{sc['id']}] {sc['tts']}")
    print(f"-- {out['chars']}자 ≈ {out['est_sec']}초 · 뺀 문장 {out['dropped']} · 문제 {out['issues']}")
    print("── 쓰레드 ──"); print(out["threads"]); print("── 답글 ──"); print(out["threads_reply"])
