"""게시 — python publish.py YYYYMMDD [us|kr] [--go] [--targets=youtube,tiktok,threads] [--public]
SPEC §3 게시. 결과는 out/D/ed/publish.json (플랫폼별 id·URL·시각), 한 번 올린 대상은 다시 올리지 않는다.

모드(data/publish_config.json):
  confirm(기본, 첫 4주) — run_day는 게시하지 않는다. JJ가 review.html 확인 뒤 `publish.py D ed --go` 실행.
                          유튜브 private(API 심사 전엔 어차피 private 고정), 틱톡 SELF_ONLY(심사 전 강제), 스레드는 공개 게시.
  auto                  — run_day가 review 뒤 자동 게시. 공개 범위는 config의 privacy 값.
--go 없이 실행하면 드라이런: 제목·설명·캡션·이미지 URL만 출력하고 아무것도 올리지 않는다.

플랫폼 제약(2026-09 기준):
  YouTube  videos.insert 1,600 unit/일 10,000 → 하루 2편 OK. API 심사(감사) 전 프로젝트의 업로드는 private로 잠긴다 → 스튜디오에서 수동 공개.
  TikTok   Content Posting API 앱 심사 전엔 privacy_level SELF_ONLY만 허용(비공개). 심사 뒤 PUBLIC_TO_EVERYONE.
  Threads  이미지 게시는 공개 URL 필요 → 공개 저장소 assets 브랜치에 카드 이미지를 푸시해 raw URL 사용. 텍스트 500자.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from _common import day_dir, DATA, computed_path, load_json, log, out_dir, save_json
from app.keychain import get_api_key  # noqa: E402
import auth  # noqa: E402

ROOT = DATA.parent
REPO = ROOT.parent                       # asset/
ASSETS_DIR = ROOT / ".assets"            # assets 브랜치 워크트리
CONFIG = DATA / "publish_config.json"
DEFAULT_CONFIG = {"mode": "confirm", "youtube": {"privacy": "private", "category": "25"}, "tiktok": {"privacy": "SELF_ONLY"},
                  "threads": {"enabled": True, "media": "card", "link_in_reply": True}, "assets_branch": "assets", "publish_at": {"kr": "17:00"}, "editions": {"kr": True, "us": False},
                  "targets": ["threads"]}


def spoken_time(hhmm: str) -> str:
    """'07:30' → '아침 7시 30분', '18:30' → '저녁 6시 30분'"""
    h, m = int(hhmm[:2]), int(hhmm[3:5])
    part = "새벽" if h < 6 else "아침" if h < 11 else "오후" if h < 17 else "저녁" if h < 21 else "밤"   # 17시 = 저녁 5시(JJ 2026-09-15)
    return f"{part} {h if h <= 12 else h - 12}시" + (f" {m}분" if m else "")


def publish_at_dt(d: str, ed: str) -> datetime:
    hhmm = config()["publish_at"].get(ed, "17:00")
    return datetime.strptime(d + hhmm, "%Y%m%d%H:%M")


def edition_enabled(ed: str) -> bool:
    return bool(config().get("editions", {}).get(ed, ed == "kr"))
HASHTAGS = {"kr": "#주식 #코스피 #국장 #한국주식 #수급 #외국인순매수 #BRAND #Shorts", "us": "#나스닥 #미국주식 #서학개미 #반도체 #주식 #BRAND #Shorts"}
DISCLAIMER = "공개 데이터(키움증권 REST·야후 파이낸스·BLS·Google News)로 자동 생성한 브리핑입니다. AI 음성. 종목·매매 추천이 아니며 투자 판단의 책임은 본인에게 있습니다."


def config() -> dict:
    c = load_json(CONFIG) or {}
    out = json.loads(json.dumps(DEFAULT_CONFIG))
    for k, v in c.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    out["upload_times"] = {k: spoken_time(v) for k, v in out.get("publish_at", {}).items()}
    if not CONFIG.exists():
        save_json(CONFIG, {k: v for k, v in out.items() if k != "upload_times"})
    return out


# ── 문안 ──
def _desc_summary(comp: dict) -> str:
    """설명란 맨 위 '오늘 한눈에' — 우리 축(수급·돈의 이동·쏠림)과 예고 검증·내일 볼 것만 네 줄."""
    import narrate
    won = narrate.won
    inv = (comp.get("investors") or {}).get("kospi") or {}
    lines = ["오늘 한눈에"]
    if inv:
        def w(v):
            return f"{won(abs(v))} {'순매수' if v > 0 else '순매도'}" if v else "—"
        lines.append(f"· 수급: 개인 {w(inv.get('indiv') or 0)} / 외국인 {w(inv.get('foreign') or 0)} / 기관 {w(inv.get('inst') or 0)} / 기타법인 {w(inv.get('others') or 0)}")
    moves = comp.get("moves") or []
    lead = max([m for m in moves if (m.get("t") or 0) > 0], key=lambda m: m["t"], default=None)
    if lead:
        cold = next((m["theme"] for m in moves if (m.get("t") or 0) < 0 and m.get("moved_to") == lead["theme"]), None)
        if lead.get("state", "").startswith("쌓임") and (lead.get("streak") or 0) >= 2:
            lines.append(f"· 돈이 머문 곳: {lead['theme']} {narrate.days_ko(lead['streak'])} ({won(lead['t'])})")
        elif cold:
            lines.append(f"· 돈의 이동: {cold} → {lead['theme']} ({won(lead['t'])})")
        else:
            lines.append(f"· 돈이 간 곳: {lead['theme']} ({won(lead['t'])})")
    ev = comp.get("event") or {}
    if ev.get("stocks"):
        _k, _top = narrate.event_pick(ev)
        lines.append(f"· 오늘의 이슈: {ev.get('label')} — " + ", ".join(f"{x['name']} {'+' if x['pct'] > 0 else '−'}{abs(x['pct']):.1f}%" for x in _top))
    cb = comp.get("callback")
    if cb and cb.get("check", {}).get("theme"):
        lines.append(f"· 어제 예고 검증: {cb['check']['theme']} {'이어짐' if cb['ok'] else '끊김'}")
    watch = comp.get("watch") or []
    if watch:
        lines.append(f"· 내일 볼 것: {watch[0]['q']}")
    return "\n".join(lines) + "\n\n"


def texts(comp: dict, ed: str) -> dict:
    brand = comp.get("brand") or "밤낮장"
    H = {k: v.replace("BRAND", brand.replace(" ", "")) for k, v in HASHTAGS.items()}
    d = comp["date"] if ed == "kr" else comp["session_et"]
    # 오늘의 검색 키워드(유튜브 자동완성·구글 트렌드) — 없으면 빈 값
    tr = {"title": None, "tags": [], "hashtags": []}
    if ed == "kr":
        try:
            import trends
            ents = [m["theme"] for m in (comp.get("moves") or [])[:3]] + [x["name"] for x in (comp.get("stocks") or [])[:2]]
            tr = trends.pick(comp["date"], ents, " ".join(sc.get("tts", "") for sc in comp.get("scenes", [])))
        except Exception:
            pass
    if tr["hashtags"]:
        # 유튜브는 앞 3개 해시태그를 제목 위에 노출 → #코스피 다음에 검색 해시태그 2개
        parts = H["kr"].split()
        H["kr"] = " ".join(parts[:2] + [h for h in tr["hashtags"] if h not in parts][:1] + parts[2:])
    ev_pub = comp.get("event") or {}
    if comp.get("format") == "aplus" and not comp.get("event_used"):
        ev_pub = {}
    if ed == "kr" and ev_pub.get("stocks") and ev_pub.get("hashtags"):
        parts = H["kr"].split()
        H["kr"] = " ".join([parts[0]] + [h for h in ev_pub["hashtags"] if h not in parts][:2] + parts[1:])
    md = f"{int(d[4:6])}/{int(d[6:8])}"
    mdk = f"{int(d[4:6])}월 {int(d[6:8])}일"
    if ed == "kr":
        k = comp["kospi"]; chg = k.get("chg_pct") or 0
        bars = (comp.get("investors") or {}).get("bars") or []
        buyers = [b["name"] for b in sorted(bars, key=lambda b: -(b["v"] or 0)) if b["name"] != "기타법인" and (b["v"] or 0) > 0][:2]
        side = f"{'·'.join(buyers)}이 샀다" if buyers else ("기타법인이 샀다" if any(b["name"] == "기타법인" and (b["v"] or 0) > 0 for b in bars) else "")
        import narrate
        moves = [m for m in (comp.get("moves") or []) if (m.get("t") or 0) > 0]
        lead = max(moves, key=lambda m: m["t"])["theme"] if moves else None
        title = kr_title(comp, tr)
        label = "국내장 마감"
    else:
        ix = (comp.get("idx") or {}).get("IXIC") or (comp.get("index") or {}).get("QQQ") or {}
        pct = ix.get("pct")
        hook = (comp["scenes"][0].get("tts") or "").split("마감입니다.", 1)[-1].strip()
        cause = hook.split(" 나스닥")[0].strip(" ,") if " 나스닥" in hook and not hook.startswith("나스닥") else ""
        cause = cause.replace("고용보고서 뒤", "").strip()
        if pct is not None:
            head = f"{mdk} 나스닥 {abs(pct):.2f}% {'오른' if pct > 0 else '내린'} 이유" + (f" — {cause}" if cause and len(cause) <= 24 else "")
        else:
            head = f"{mdk} 미국장 마감 — {comp.get('headline') or ''}"
        title = f"{head} | 미국장 마감 #Shorts"
        label = "미국장 마감"
    title = title[:100]
    script = "\n".join(sc["tts"] for sc in comp["scenes"])
    when = (comp.get("upload_times") or {}).get("kr") or "저녁 5시"
    import narrate
    summary = _desc_summary(comp) if ed == "kr" else ""
    img = ((comp.get("event") or {}).get("image") or {}) if ed == "kr" else {}
    credit = f"\n{img['credit']} — {img['src_url']}" if img.get("src_url") else ""
    desc = f"{title.replace(' #Shorts', '')}\n{narrate.josa(brand)} 매일 {when}, 국장 마감을 '누가 샀고 돈이 어디로 갔는지' 중심으로 정리합니다.\n\n{summary}{script}\n\n{DISCLAIMER}{credit}\n\n{H[ed]}"
    base = ["주식", "한국주식", "한국 주식", "코스피", "코스피 마감", "국장", "국장 마감", "수급", "외국인 순매수", "기관 순매수", "주식 초보", "장 마감 브리핑", "오늘의 증시", brand] if ed == "kr"         else ["나스닥", "미국 주식", "서학개미", "반도체", "주식", "미국장 마감", brand]
    dyn = [m["theme"] for m in (comp.get("moves") or [])[:3]] + [x["name"] for x in (comp.get("stocks") or [])[:2]] +           ([g["term"] for g in [comp.get("glossary")] if g] if ed == "kr" else [x["name"] for x in (comp.get("movers") or [])[:3]])
    if ed == "kr" and ev_pub.get("stocks"):
        _k, _top = narrate.event_pick(ev_pub)
        dyn = list(ev_pub.get("keywords") or []) + [x["name"] for x in _top] + dyn
    tags = list(dict.fromkeys(base + [t for t in dyn if t] + (tr.get("tags") or [])))[:30]
    tiktok_title = (title.replace(" #Shorts", "") + "\n" + H[ed].replace("#Shorts", "#주식브리핑"))[:2200]
    body = (comp.get("threads_text") or comp.get("caption") or "").strip()
    if ed == "kr" and comp.get("threads_facts"):
        threads = body + "\n#국장"                     # v4: 해시태그는 하나, 영상 링크·내일 볼 것은 첫 답글
        reply = comp.get("threads_reply") or ""
    else:
        tag = H[ed].replace(" #Shorts", "")
        threads = body + "\n\n" + tag
        if len(threads) > 500:
            threads = body[: 500 - len(tag) - 3].rstrip() + "\n\n" + tag
        reply = "영상 전체는 여기서 → {YT}"
    return {"title": title, "description": desc[:5000], "tags": tags, "tiktok_title": tiktok_title, "threads": threads, "threads_reply": reply}



# ── 유튜브 제목(국장) — 그날의 '다른 점'을 앞세우고, 전날과 같은 틀·같은 검색어는 피한다 ──
def _norm_title(t: str) -> str:
    import re as _re
    return _re.sub(r"[\d,.%조억천만]+|\s+", "", t)


def _recent_titles(d: str, days: int = 3) -> list[str]:
    from datetime import datetime as _dt, timedelta as _td
    out = []
    base = _dt.strptime(d, "%Y%m%d")
    for i in range(1, days + 1):
        pd = (base - _td(days=i)).strftime("%Y%m%d")
        f = out_dir(pd, "kr") / "youtube_title.txt"
        if f.exists():
            out.append(f.read_text(encoding="utf-8").strip())
    return out


def kr_title_v3(comp: dict, tr: dict) -> str:
    """A+ 형식 제목: '{주인공} {금액} 팔았는데|샀는데 코스피 {대비}, 누가 샀나|팔았나 | {M/D} {만기일·이슈 키워드 또는 국장 마감} #회차'.
    날짜·'오늘'로 시작하지 않는다. 종목명·'올랐다'·'때문에·이유' 없음. 숫자는 전부 실데이터."""
    import narrate_aplus as na
    d = comp["date"]
    md = f"{int(d[4:6])}/{int(d[6:8])}"
    P = comp["protagonist"]
    sold = P["sold"]
    ct = comp.get("contrast") or {}
    opp = (ct.get("text") or "").startswith("그런데")          # 주체와 지수가 반대 방향일 때만 '~는데'
    verb = ('팔았는데' if sold else '샀는데') if opp else ('순매도·' if sold else '순매수·')
    head = f"{P['name']} {na._amt(P['amount'])} {verb}{'' if not opp else ' '}코스피 {ct.get('short') or ''}, 누가 {'샀나' if sold else '팔았나'}"
    kws = []
    iso = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    for x in comp.get("schedule") or []:
        if (x.get("d") or "")[:10] == iso and "동시만기" in (x.get("t") or ""):
            kws.append("네 마녀의 날")
    ev = comp.get("event") or {}
    if ev.get("stocks") and ev.get("keywords") and comp.get("event_used", True):
        kws.append(ev["keywords"][0])
    ep = comp.get("ep")
    tail = f"{md} " + ("·".join(kws) if kws else "국장 마감") + (f" #{ep:03d}" if ep else "")
    return f"{head} | {tail}"[:100]


def kr_title(comp: dict, tr: dict) -> str:
    import narrate
    if comp.get("format") == "aplus" and comp.get("protagonist"):
        return kr_title_v3(comp, tr)
    d = comp["date"]
    mdk = f"{int(d[4:6])}월 {int(d[6:8])}일"
    k = comp["kospi"]; chg = k.get("chg_pct") or 0.0
    inv = (comp.get("investors") or {}).get("kospi") or {}
    f_, i_, p_, o_ = inv.get("foreign") or 0, inv.get("inst") or 0, inv.get("indiv") or 0, inv.get("others") or 0
    won = narrate.won
    moves = [m for m in (comp.get("moves") or []) if (m.get("t") or 0) > 0]
    lead = max(moves, key=lambda m: m["t"]) if moves else None
    turns = ((comp.get("intraday") or {}).get("turns") or [])
    hi_gap = (k["high"] / k["close"] - 1) * 100 if k.get("high") and k.get("close") else 0
    lo_gap = (k["close"] / k["low"] - 1) * 100 if k.get("low") and k.get("close") else 0
    both_buy = f_ > 0 and i_ > 0
    both_sell = f_ < 0 and i_ < 0
    pair = "외국인·기관"
    amt_pair = (f"{won(min(f_, i_))}씩" if both_buy and abs(f_ - i_) <= 0.15 * max(f_, i_) else f"{won(f_)}·{won(i_)}") if both_buy else ""
    updn = "올랐" if chg > 0 else "내렸"
    pct = f"{abs(chg):.2f}%"

    cands = []
    # 00) 오늘의 이슈(events.json)가 있으면 그 결과가 첫 후보 — 사람들이 그날 검색하는 말(아이폰18 등)을 맨 앞에
    ev = comp.get("event") or {}
    if ev.get("stocks"):
        kind, top = narrate.event_pick(ev)
        kw = (ev.get("spoken") or ev.get("label") or "").replace("과 ", "·").replace("와 ", "·")
        grp = ev.get("group") or "관련주"
        p0 = f"{top[0]['name']} {'+' if top[0]['pct'] > 0 else '−'}{abs(top[0]['pct']):.1f}%"
        p1 = f"{top[1]['name']} {'+' if top[1]['pct'] > 0 else '−'}{abs(top[1]['pct']):.1f}%" if len(top) > 1 else ""
        if kind == "up":
            cands.append(f"{mdk} {kw} 나오자 '{grp}' 올랐다, {p0}")
        elif kind == "down":
            cands.append(f"{mdk} {kw} 나왔는데 '{grp}'는 왜 내렸나?")
        elif kind == "mixed":
            cands.append(f"{mdk} {kw} 발표에도 '{grp}' 엇갈렸다, {p0}")
    # 0) 어그로 공식(JJ 9/9): '센 사실(진짜 숫자) + 반대 결과는 왜? + (산 쪽·영상 속 종목)'
    #    센 사실 우선순위: 개인 5일 누적 10조↑ > 개인 하루 1조↑ > 외국인 하루 5천억↑ 매도. 반대 결과가 없으면 '왜?' 대신 결과를 붙인다.
    kx = load_json(day_dir(d) / "krx_investors.json") or {}
    days = [r for r in (kx.get("kospi_days") or []) if r.get("date") and r["date"] <= d][:5]
    cum_p = sum(r.get("indiv") or 0 for r in days) if len(days) >= 4 else 0
    buyers3 = sorted([(n, v) for n, v in (("외국인", f_), ("기관", i_)) if v > 0], key=lambda x: -x[1]) or ([("기타법인", o_)] if o_ > 0 else [])
    stock0 = next((x["name"] for x in (comp.get("stocks") or []) if x.get("name")), None)
    teaser = "·".join([f"{buyers3[0][0]} {won(buyers3[0][1])}"] if buyers3 else []) + (f"·{stock0}" if stock0 else "")
    teaser = f" ({teaser})" if teaser else ""
    why = f"코스피는 왜 {'올랐나' if chg > 0 else '내렸나'}?"
    if cum_p <= -100000:
        fact = f"개인이 {len(days)}일간 '{won(abs(cum_p))}' 팔았"
    elif p_ <= -10000:
        fact = f"개인이 '{won(abs(p_))}' 팔았"
    elif f_ <= -5000:
        fact = f"외국인이 '{won(abs(f_))}' 팔았"
    else:
        fact = ""
    plain = None
    if fact:
        if chg > 0:
            cands.append(f"{mdk} {fact}는데, {why}{teaser}")
        else:
            plain = f"{mdk} {fact}다, 코스피 {pct} 내렸다{teaser}"
    if not fact and chg < 0 and (f_ >= 5000 or i_ >= 5000):
        big = "외국인" if f_ >= i_ else "기관"
        cands.append(f"{mdk} {big} {won(max(f_, i_))} 샀는데, {why}{teaser}")
    # 1) 셋 다 같은 방향 / 둘이 팔고 하나만 산 날
    three = [("개인", p_), ("외국인", f_), ("기관", i_)]
    sellers = [n for n, v in three if v < 0]
    buyers = [n for n, v in three if v > 0]
    if len(sellers) == 3 and o_ > 0:
        cands.append(f"{mdk} 개인·외국인·기관 다 팔았는데 기타법인이 {won(o_)} 받았다, 코스피 {pct} {updn}다")
    elif len(sellers) == 2 and len(buyers) == 1:
        b = buyers[0]; bv = dict(three)[b]
        cands.append(f"{mdk} {'·'.join(sellers)} 다 팔았다, {b} 혼자 {won(bv)} 샀다, 코스피 {pct} {updn}다")
    elif len(buyers) == 2 and len(sellers) == 1 and chg < 0:
        cands.append(f"{mdk} 코스피 {pct} 내렸는데 {'·'.join(buyers)}은 샀다, 판 건 {sellers[0]} {won(abs(dict(three)[sellers[0]]))}")
    # 2) 장중→마감 부호 전환
    t0 = turns[0] if turns else None
    if t0 and t0["kind"] == "flip":
        cands.append(f"{mdk} {t0['name']}, 오후 2시 {won(abs(t0['a']))} {'팔다' if t0['a'] < 0 else '사다'} 마감엔 {won(abs(t0['b']))} {'샀다' if t0['b'] > 0 else '팔았다'}")
    # 3) 장중 고점 찍고 밀린 날 / 저점 찍고 반등한 날
    if hi_gap >= 1.5 and chg < 0:
        cands.append(f"{mdk} 코스피 {narrate.idx(k['high'])} 찍고 밀렸는데 {pair}{'은 ' + amt_pair + ' 샀다' if both_buy else '은 팔았다' if both_sell else ' 엇갈렸다'}")
    if lo_gap >= 1.5 and chg > 0:
        cands.append(f"{mdk} 코스피 {narrate.idx(k['low'])}까지 밀렸다 {pct} 반등, {pair}{'이 ' + amt_pair + ' 받았다' if both_buy else '은 팔았다' if both_sell else ' 엇갈렸다'}")
    # 4) 막판 유입(more) — 외국인·기관
    if t0 and t0["kind"] == "more" and t0["key"] in ("foreign", "inst") and t0["b"] > 0:
        cands.append(f"{mdk} {t0['name']} 오후 2시 {won(abs(t0['a']))}에서 마감 {won(abs(t0['b']))}로 막판 매수, 코스피 {pct} {updn}다")
    # 5) 지수와 수급이 엇갈린 날
    if chg < 0 and both_buy:
        cands.append(f"{mdk} 코스피 {pct} 내렸는데 {pair}은 '{amt_pair}' 샀다")
    if chg > 0 and both_sell:
        cands.append(f"{mdk} 코스피 {pct} 올랐는데 {pair}은 팔았다" + (f", 산 쪽은 개인 {won(p_)}" if p_ > 0 else ""))
    # 6) 연속일 4일 이상
    st = comp.get("inv_streak") or {}
    for key, nm in (("foreign", "외국인"), ("inst", "기관")):
        n = (st.get(key) or {}).get("streak") or 0
        if abs(n) >= 4:
            cands.append(f"{mdk} {nm} {abs(n)}일째 {'샀다' if n > 0 else '팔았다'}, 코스피 {pct} {updn}다")
            break
    if plain:
        cands.append(plain)
    # 7) 사건이 없는 날 — 매일 고정 시리즈(경제사냥꾼의 '투자 포인트'처럼 같은 문장 반복)
    cands.append(f"{mdk} 국장 마감, 오늘 누가 샀고 돈은 어디로 갔나")

    # 경제사냥꾼 실측(2026-09-10): 제목은 25~35자 한 문장, 대괄호·구분선·해시태그 없음, 핵심어 하나만 '따옴표'. 검색어는 문장 안에 넣는다.
    recent = _recent_titles(d)
    recent_norm = {_norm_title(t) for t in recent}
    cands = [c.replace("약 ", "") for c in cands]
    KW = ("코스피", "국장", "한국주식", "주식")

    def finish(head: str) -> str:
        t = head.strip()
        if not any(k in t for k in KW):
            t = t.replace(mdk, f"{mdk} 국장", 1) if t.startswith(mdk) else f"국장 {t}"
        return t[:100]

    for head in cands:
        title = finish(head)
        if _norm_title(title) not in recent_norm or head == cands[-1]:
            return title
    return finish(cands[-1])


# ── YouTube ──
def yt_access_token() -> str:
    r = httpx.post("https://oauth2.googleapis.com/token", data={"client_id": get_api_key("youtube", "client_id"), "client_secret": get_api_key("youtube", "client_secret"),
                                                               "refresh_token": get_api_key("youtube", "refresh_token"), "grant_type": "refresh_token"}, timeout=30)
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"YouTube 토큰 갱신 실패: {j}")
    return j["access_token"]


def youtube_upload(video: Path, t: dict, privacy: str, category: str, publish_at: datetime | None = None) -> dict:
    """publish_at(KST)이 미래면 private + publishAt으로 올려 유튜브가 그 시각에 공개한다(API 감사 통과 전엔 private 잠금이라 예약이 안 풀릴 수 있음)."""
    tok = yt_access_token()
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}
    if publish_at and publish_at > datetime.now() and privacy == "public":
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    meta = {"snippet": {"title": t["title"], "description": t["description"], "tags": t["tags"][:30], "categoryId": category, "defaultLanguage": "ko", "defaultAudioLanguage": "ko"},
            "status": status}
    size = video.stat().st_size
    r = httpx.post("https://www.googleapis.com/upload/youtube/v3/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                   headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                            "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                   content=json.dumps(meta, ensure_ascii=False).encode("utf-8"), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube 업로드 세션 실패 {r.status_code}: {r.text[:300]}")
    loc = r.headers["Location"]
    with open(video, "rb") as f:
        up = httpx.put(loc, headers={"Authorization": f"Bearer {tok}", "Content-Type": "video/mp4", "Content-Length": str(size)}, content=f.read(), timeout=600)
    if up.status_code not in (200, 201):
        raise RuntimeError(f"YouTube 업로드 실패 {up.status_code}: {up.text[:300]}")
    j = up.json()
    st = j.get("status") or {}
    return {"id": j["id"], "url": f"https://youtube.com/shorts/{j['id']}", "privacy": st.get("privacyStatus", privacy), "publish_at": st.get("publishAt") or status.get("publishAt")}


# ── TikTok ──
def tiktok_upload(video: Path, title: str, privacy: str) -> dict:
    tok = auth.tiktok_access_token()
    size = video.stat().st_size
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    body = {"post_info": {"title": title, "privacy_level": privacy, "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                          "video_cover_timestamp_ms": 1000},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}}
    r = httpx.post("https://open.tiktokapis.com/v2/post/publish/video/init/", headers=h, content=json.dumps(body).encode(), timeout=60)
    j = r.json()
    if (j.get("error") or {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init 실패: {j}")
    data = j["data"]
    with open(video, "rb") as f:
        up = httpx.put(data["upload_url"], headers={"Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"},
                       content=f.read(), timeout=600)
    if up.status_code not in (200, 201, 206):
        raise RuntimeError(f"TikTok 업로드 실패 {up.status_code}: {up.text[:300]}")
    pid = data["publish_id"]
    status = "PROCESSING_UPLOAD"
    for _ in range(30):
        time.sleep(5)
        s = httpx.post("https://open.tiktokapis.com/v2/post/publish/status/fetch/", headers=h, content=json.dumps({"publish_id": pid}).encode(), timeout=30).json()
        status = (s.get("data") or {}).get("status", status)
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            break
    if status == "FAILED":
        raise RuntimeError(f"TikTok 게시 실패: {s}")
    return {"publish_id": pid, "status": status, "privacy": privacy}


# ── Threads (이미지 = 공개 저장소 assets 브랜치 raw URL) ──
def _git(*args, cwd: Path = REPO) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def _repo_slug() -> str:
    url = _git("remote", "get-url", "origin")
    slug = url.rstrip("/").removesuffix(".git")
    slug = slug.split("github.com")[-1].lstrip(":/")
    return slug


def host_file(src: Path, d: str, ed: str, branch: str, kind: str = "card") -> str:
    """파일(카드 png·영상 mp4)을 assets 브랜치에 커밋·푸시하고 raw URL을 돌려준다.
    스레드는 미디어를 공개 URL로만 받는다. jsDelivr(cdn.jsdelivr.net)는 GitHub raw와 달리
    mp4에 video/mp4 Content-Type을 주므로 영상은 jsDelivr 경로를 쓴다."""
    if not (ASSETS_DIR / ".git").exists():
        subprocess.run(["git", "worktree", "prune"], cwd=str(REPO), capture_output=True)
        exclude = REPO / ".git" / "info" / "exclude"
        if exclude.exists() and "market-close/.assets" not in exclude.read_text(encoding="utf-8", errors="replace"):
            exclude.open("a", encoding="utf-8").write("\nmarket-close/.assets\n")
        remote_has = subprocess.run(["git", "ls-remote", "--heads", "origin", branch], cwd=str(REPO), capture_output=True, text=True).stdout.strip()
        if remote_has:
            _git("fetch", "origin", f"{branch}:{branch}")
            _git("worktree", "add", str(ASSETS_DIR), branch)
        else:
            _git("worktree", "add", "--detach", str(ASSETS_DIR))
            _git("checkout", "--orphan", branch, cwd=ASSETS_DIR)
            subprocess.run(["git", "rm", "-rfq", "."], cwd=str(ASSETS_DIR), capture_output=True)
            (ASSETS_DIR / "README.md").write_text("밤낮장 게시용 카드 이미지(Threads 첨부). 자동 생성.\n", encoding="utf-8")
            _git("add", "README.md", cwd=ASSETS_DIR)
            _git("commit", "-qm", "assets: init", cwd=ASSETS_DIR)
            if os.environ.get("PUBLISH_NO_PUSH") != "1":
                _git("push", "-u", "origin", branch, cwd=ASSETS_DIR)
    rel = f"{d[:4]}/{d[4:6]}/{d}_{ed}_{kind}{src.suffix}"
    dst = ASSETS_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst)
    _git("add", rel, cwd=ASSETS_DIR)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(ASSETS_DIR)).returncode != 0:
        _git("commit", "-qm", f"{kind} {d} {ed}", cwd=ASSETS_DIR)
    if os.environ.get("PUBLISH_NO_PUSH") != "1":
        _git("push", "origin", branch, cwd=ASSETS_DIR)
    slug = _repo_slug()
    if src.suffix.lower() == ".mp4":
        return f"https://cdn.jsdelivr.net/gh/{slug}@{branch}/{rel}"
    return f"https://raw.githubusercontent.com/{slug}/{branch}/{rel}"


def _th_container(uid: str, tok: str, params: dict, wait: bool = True) -> str:
    """컨테이너 생성 후 처리 완료까지 대기. 영상은 인코딩에 시간이 걸린다(최대 5분)."""
    r = httpx.post(f"https://graph.threads.net/v1.0/{uid}/threads", data={**params, "access_token": tok}, timeout=90).json()
    if "id" not in r:
        raise RuntimeError(f"Threads 컨테이너 실패: {r}")
    cid = r["id"]
    if not wait:
        return cid
    for _ in range(100):
        s = httpx.get(f"https://graph.threads.net/v1.0/{cid}", params={"fields": "status,error_message", "access_token": tok}, timeout=30).json()
        st = s.get("status")
        if st == "FINISHED":
            return cid
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads 미디어 처리 실패: {s}")
        time.sleep(3)
    raise RuntimeError("Threads 미디어 처리 시간 초과(5분)")


def threads_post(text: str, image_url: str | None = None, video_url: str | None = None,
                 carousel: list[dict] | None = None, reply_to: str | None = None) -> dict:
    """스레드 게시. carousel=[{"image_url":…}|{"video_url":…}, …]이면 캐러셀(2~20개).
    reply_to가 있으면 그 게시물의 답글로 올린다(링크는 답글에 두는 운영 방침용)."""
    tok = auth.threads_access_token()
    meta = load_json(auth.AUTH_DIR / "threads.json") or {}
    uid = meta.get("user_id") or "me"
    if carousel:
        kids = []
        for item in carousel:
            p = {"is_carousel_item": "true"}
            if item.get("video_url"):
                p.update({"media_type": "VIDEO", "video_url": item["video_url"]})
            else:
                p.update({"media_type": "IMAGE", "image_url": item["image_url"]})
            kids.append(_th_container(uid, tok, p))
        params = {"media_type": "CAROUSEL", "children": ",".join(kids), "text": text}
    elif video_url:
        params = {"media_type": "VIDEO", "video_url": video_url, "text": text}
    elif image_url:
        params = {"media_type": "IMAGE", "image_url": image_url, "text": text}
    else:
        params = {"media_type": "TEXT", "text": text}
    if reply_to:
        params["reply_to_id"] = reply_to
    cid = _th_container(uid, tok, params)
    p = httpx.post(f"https://graph.threads.net/v1.0/{uid}/threads_publish", data={"creation_id": cid, "access_token": tok}, timeout=90).json()
    if "id" not in p:
        raise RuntimeError(f"Threads 게시 실패: {p}")
    perm = httpx.get(f"https://graph.threads.net/v1.0/{p['id']}", params={"fields": "permalink", "access_token": tok}, timeout=30).json()
    return {"id": p["id"], "url": perm.get("permalink"), "media": {"image": image_url, "video": video_url, "carousel": carousel}}


# ── 본체 ──
def publish(d: str, ed: str, go: bool = False, targets: list[str] | None = None, public: bool = False) -> dict:
    cfg = config()
    if not edition_enabled(ed):
        log(d, "publish", f"{ed} 편은 게시 대상이 아님(editions 설정) → 건너뜀")
        return {"date": d, "edition": ed, "results": {}, "skipped": "edition disabled"}
    comp = load_json(computed_path(d, ed))
    if not comp:
        raise SystemExit(f"computed_{ed}.json 없음")
    od = out_dir(d, ed)
    video, card = od / "video.mp4", od / "card.png"
    state_p = od / "publish.json"
    state = load_json(state_p) or {"date": d, "edition": ed, "results": {}}
    # 영상이 없거나 대본보다 낡았으면 글만 올라가는 사고가 난다(음성 단계가 죽은 날).
    if go:
        cp = computed_path(d, ed)
        if not video.exists() or video.stat().st_size < 100_000:
            log(d, "publish", "⚠ video.mp4 없음 — 게시 중단(영상 없이 글만 올라가지 않도록)")
            return {"date": d, "edition": ed, "results": state["results"], "skipped": "video missing"}
        if cp.exists() and video.stat().st_mtime < cp.stat().st_mtime - 1:
            log(d, "publish", "⚠ video.mp4 가 대본보다 낡음 — 게시 중단(렌더가 다시 돌아야 한다)")
            return {"date": d, "edition": ed, "results": state["results"], "skipped": "video stale"}

    t = texts(comp, ed)
    targets = targets or cfg.get("targets") or ["youtube", "tiktok", "threads"]
    yt_priv = "public" if public else cfg["youtube"]["privacy"]
    tt_priv = "PUBLIC_TO_EVERYONE" if public else cfg["tiktok"]["privacy"]
    pa = publish_at_dt(d, ed)
    log(d, "publish", f"{ed} {'실행' if go else '드라이런'} targets={targets} yt={yt_priv}{' 예약 ' + pa.strftime('%H:%M') if pa > datetime.now() and yt_priv == 'public' else ''} tt={tt_priv}")
    if not go:
        print(f"[YouTube] 공개 {yt_priv}" + (f", 예약 공개 {pa:%m/%d %H:%M}" if pa > datetime.now() and yt_priv == "public" else ""))
        print(f"[YouTube] 제목({len(t['title'])}자): {t['title']}\n[YouTube] 설명 앞부분: {t['description'][:160]}…\n[TikTok] {t['tiktok_title'][:120]}…\n[Threads] ({len(t['threads'])}자)\n{t['threads']}")
        print(f"파일: {video} ({video.stat().st_size // 1024 if video.exists() else 0} KB), {card}")
        return state
    for tg in targets:
        if tg in state["results"] and state["results"][tg].get("ok"):
            log(d, "publish", f"{tg}: 이미 게시됨 → 건너뜀 {state['results'][tg].get('url') or state['results'][tg].get('id')}")
            continue
        try:
            if tg == "youtube":
                if not get_api_key("youtube", "refresh_token"):
                    raise RuntimeError("YouTube 미연결 — python auth.py youtube")
                res = youtube_upload(video, t, yt_priv, cfg["youtube"]["category"], publish_at_dt(d, ed))
            elif tg == "tiktok":
                if not get_api_key("tiktok", "refresh_token"):
                    raise RuntimeError("TikTok 미연결 — python auth.py tiktok")
                res = tiktok_upload(video, t["tiktok_title"], tt_priv)
            elif tg == "threads":
                if not cfg["threads"].get("enabled"):
                    continue
                if not get_api_key("threads", "access_token"):
                    raise RuntimeError("Threads 미연결 — python auth.py threads")
                media = cfg["threads"].get("media", "card")     # card | video | carousel
                br = cfg["assets_branch"]
                img = host_file(card, d, ed, br, "card") if card.exists() else None
                vid = host_file(video, d, ed, br, "video") if (media in ("video", "carousel") and video.exists()) else None
                if media == "carousel" and img and vid:
                    # 카드가 먼저 — 피드 미리보기에 숫자가 보여야 한다(영상 첫 프레임은 로고 화면)
                    res = threads_post(t["threads"], carousel=[{"image_url": img}, {"video_url": vid}])
                elif media == "video" and vid:
                    res = threads_post(t["threads"], video_url=vid)
                else:
                    res = threads_post(t["threads"], image_url=img)
                yt = (state["results"].get("youtube") or {}).get("url")
                if cfg["threads"].get("link_in_reply", True) and yt:
                    try:
                        rep = threads_post((t.get("threads_reply") or "영상 전체는 여기서 → {YT}").replace("{YT}", yt), reply_to=res["id"])
                        res["reply_url"] = rep.get("url")
                    except Exception as e:
                        log(d, "publish", f"threads 답글 실패(본문은 게시됨): {e}")
            else:
                continue
            res["ok"] = True; res["at"] = datetime.now().isoformat(timespec="seconds")
            log(d, "publish", f"{tg}: OK {res.get('url') or res.get('id') or res.get('publish_id')}")
        except Exception as e:
            res = {"ok": False, "error": str(e)[:500], "at": datetime.now().isoformat(timespec="seconds")}
            log(d, "publish", f"{tg}: 실패 {e}")
        state["results"][tg] = res
        save_json(state_p, state)
    return state


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else datetime.now().strftime("%Y%m%d")
    ed = args[1] if len(args) > 1 else "kr"
    tg = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--targets=")), None)
    publish(d, ed, go="--go" in sys.argv, targets=tg, public="--public" in sys.argv)
