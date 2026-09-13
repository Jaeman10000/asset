"""주간편 실행기 (2026-09-11~) — python run_weekly.py kr|us BUILD_DATE [--stage=script|video|all] [--no-fetch]

kr = 토요일 국장 주간 결산(장면 w0~w6, jobs/weekly_data.py + narrate_weekly.py, render/src/v4/WeeklyV4.tsx)
us = 일요일 미국 주간 결산(장면 uw0~uw6, jobs/us_weekly_data.py + narrate_us_weekly.py, render/src/v4/WeeklyUSV4.tsx)

진행(JJ 2026-09-11): 대본 먼저 → JJ 확인·수정 → 영상.
  script: 데이터 → 대본 → (script_override.json 반영) → data/<dir>/<date>/script.json, out/<dir>/<date>/script.txt
  video : script.json으로 음성(edge-tts) → 렌더(Video, crf 27) → 업로드 문구(youtube_*.txt, threads*.txt, UPLOAD.md)
뉴스는 검증 파일(news_verified.json)에서 verified=true(미국편은 use_in_script≠false)만 쓴다.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

from _common import DATA, ROOT, load_json, save_json

RENDER = ROOT / "render"
KIND = {"kr": {"dir": "weekly", "data": "computed_weekly.json", "tag": "#국장", "label": "주간 결산"},
        "us": {"dir": "weekly_us", "data": "computed_us_weekly.json", "tag": "#미장", "label": "미국 주간 결산"}}
BGM_FILE, BGM_VOL = "bgm/bgm_B_dark_arp.wav", 0.07   # 채널 시그니처 사운드(JJ 2026-09-12 확정)
DISCLAIMER = "공개 데이터(키움증권 REST·거래소 집계·야후 파이낸스·미 재무부·언론 보도)로 자동 생성한 브리핑입니다. AI 음성. 종목·매매 추천이 아니며 투자 판단의 책임은 본인에게 있습니다."


def _log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [weekly] {msg}", flush=True)


def _week_end(build_date: str) -> datetime:
    b = datetime.strptime(build_date, "%Y%m%d")
    d = b - timedelta(days=1)
    while d.weekday() != 4:          # 직전 금요일
        d -= timedelta(days=1)
    return d


def _news(kind: str, base) -> dict:
    n = load_json(base / "news_verified.json") or load_json(base / "news.json") or {"events": []}
    ev = [e for e in n.get("events") or [] if e.get("verified", True) and e.get("use_in_script", True) is not False]
    return {**n, "events": ev}


def _check_threads(body: str, reply: str, tag: str) -> list[str]:
    """쓰레드 본문 검사 — script_override.json으로 덮어쓴 것도 반드시 통과해야 한다.
    기준(JJ 2026-09-12): 처음 보는 사람이 그 글만 읽고 이해되게. 축약 종결형·채팅 기호·압축 숫자 금지."""
    from checks import forbidden
    bad: list[str] = []
    lines = [x for x in (body or "").strip().splitlines()]
    if not lines or lines[-1].strip() != tag:
        bad.append(f"끝 줄이 {tag}가 아님")
    live = [x.strip() for x in lines if x.strip() and x.strip() != tag]
    if not (3 <= len(live) <= 14):
        bad.append(f"본문 {len(live)}줄(3~14)")
    if len(body or "") > 500:
        bad.append(f"본문 {len(body)}자(500 초과)")
    for x in live + [l for l in (reply or "").splitlines()[1:] if l.strip()]:
        if hits := forbidden.find_threads(x):
            bad.append(f"금지어 {hits} — {x[:24]}")
        if re.search(r"(팜|음|함|짐|옴|됨|뜀|빠짐|올림|내림)\s*\.{0,2}$", x):
            bad.append(f"축약 종결형 — {x[:24]}")
        if re.search(r"[ㅋㅎ]", x):
            bad.append(f"채팅 기호 — {x[:24]}")
        if re.search(r"\d+\.\d+조", x):
            bad.append(f"압축 숫자(9.9조 형태) — {x[:24]}")
    return bad


def stage_script(kind: str, date: str, fetch: bool = True) -> dict:
    k = KIND[kind]
    base = DATA / k["dir"] / date
    base.mkdir(parents=True, exist_ok=True)
    we = _week_end(date)
    if kind == "kr":
        import weekly_data, narrate_weekly
        w = weekly_data.build(we.strftime("%Y%m%d"), date, fetch=fetch)
        news = _news(kind, base)
        out = narrate_weekly.build_weekly(w, news)
    else:
        import us_weekly_data, narrate_us_weekly
        w = us_weekly_data.build(we.strftime("%Y-%m-%d"), date)
        news = _news(kind, base)
        out = narrate_us_weekly.build_us_weekly(w, news)
    # JJ·운영자 수정본(있으면 장면·제목·쓰레드를 그대로 덮어씀)
    ov = load_json(base / "script_override.json") or {}
    for sc in out["scenes"]:
        if sc["id"] in (ov.get("scenes") or {}):
            sc["tts"] = ov["scenes"][sc["id"]]
            if sc.get("sub") is not None and sc["id"] not in ("w0", "uw0"):
                sc["sub"] = sc["tts"]
    for key in ("title", "threads", "threads_reply"):
        if ov.get(key):
            out[key] = ov[key]
    from checks import forbidden
    issues = {sc["id"]: forbidden.find(sc["tts"]) for sc in out["scenes"] if forbidden.find(sc["tts"])}
    th_bad = _check_threads(out["threads"], out["threads_reply"], k["tag"])   # override로 덮어써도 검사는 돈다
    if th_bad:
        issues["threads"] = th_bad
    script = {"kind": kind, "date": date, "week_end": we.strftime("%Y%m%d"), "scenes": out["scenes"], "title": out["title"],
              "threads": out["threads"], "threads_reply": out["threads_reply"], "hook_parts": out.get("hook_parts"),
              "screen_news": ov.get("screen_news"), "view": ov.get("view"), "props_extra": ov.get("props_extra"), "issues": issues, "built_at": datetime.now().isoformat(timespec="seconds")}
    save_json(base / "script.json", script)
    od = ROOT / "out" / k["dir"] / date
    od.mkdir(parents=True, exist_ok=True)
    txt = [f"제목: {script['title']}", ""] + [f"[{s['id']}] {s['tts']}" for s in script["scenes"]] + ["", "── 쓰레드 ──", script["threads"], "", "── 첫 답글 ──", script["threads_reply"]]
    (od / "script.txt").write_text("\n".join(txt), encoding="utf-8")
    _log(f"{kind} 대본 저장 {base / 'script.json'} (금지어 {issues or '없음'})")
    return script


async def _tts(scenes: list[dict], od) -> float:
    import tts
    from app.keychain import get_api_key
    voice = get_api_key("tts", "voice") or "ko-KR-InJoonNeural"
    (od / "voice").mkdir(exist_ok=True)
    t = 0.0
    for sc in scenes:
        p = od / "voice" / f"{sc['id']}.mp3"
        dur, bounds = await tts.synth(tts.speakable(sc["tts"]), p, voice)
        length = max(sc.get("min") or 4.0, dur + tts.GAP)
        sc.update({"audio": f"voice/{p.name}", "audio_sec": dur, "sec": round(length, 2), "start": round(t, 2),
                   "frames": int(round(length * tts.FPS)), "bounds": bounds, "cues": tts.make_cues(bounds)})
        t += length
    return t


def stage_video(kind: str, date: str) -> None:
    k = KIND[kind]
    base = DATA / k["dir"] / date
    script = load_json(base / "script.json")
    if not script:
        raise SystemExit("script.json 없음 — --stage=script 먼저")
    w = load_json(base / k["data"]) or {}
    news = _news(kind, base)
    od = ROOT / "out" / k["dir"] / date
    od.mkdir(parents=True, exist_ok=True)
    scenes = json.loads(json.dumps(script["scenes"]))
    total = asyncio.run(_tts(scenes, od))
    ds, de = w.get("week_start") or "", w.get("week_end") or ""
    rng = f"{int(ds[4:6])}/{int(ds[6:8])}–{int(de[4:6])}/{int(de[6:8])}" if len(ds) == 8 and len(de) == 8 else \
        f"{int(ds[5:7])}/{int(ds[8:10])}–{int(de[5:7])}/{int(de[8:10])}" if len(ds) == 10 and len(de) == 10 else ""
    screen_news = script.get("screen_news") or [
        {"d": e.get("d"), "title": e.get("title"), "line": e.get("market_link") or e.get("what"), "src": ((e.get("sources") or [{}])[0]).get("outlet", "")}
        for e in (news.get("events") or []) if e.get("confidence") in ("high", "medium")][:4]
    props = {**w, "news": screen_news, "scenes": scenes, "brand": "누가샀나", "date_label": f"{rng} 주간", "week_range": rng,
             "edition": "weekly_" + kind, "format": "weekly", "visual": "v4", "hook_parts": script.get("hook_parts"),
             "view": script.get("view"), "total_sec": round(total, 2), "total_frames": int(round(total * 30)), "fps": 30,
             "caption": "", "warnings": [], "watch": [], "schedule": [], "moves": [], "stocks": []}
    props.update(script.get("props_extra") or {})   # 화면용 보조 데이터(물가 카드·인상 확률·월요일 볼 것)
    if (RENDER / "public" / BGM_FILE).exists():          # 채널 시그니처 배경음(나레이션이 주인공)
        props["bgm"] = {"file": BGM_FILE, "volume": BGM_VOL}
    pub_voice = RENDER / "public" / "voice"
    pub_voice.mkdir(parents=True, exist_ok=True)
    for f in pub_voice.glob("*.*"):
        f.unlink()
    for f in (od / "voice").glob("*.*"):
        shutil.copy(f, pub_voice / f.name)
    pf = RENDER / f"props_weekly_{kind}.json"
    save_json(pf, props)
    save_json(od / "props.json", props)
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    cmd = [npx, "remotion", "render", "src/index.ts", "Video", str(od / "video.mp4"), f"--props={pf}", "--log=error", "--concurrency=4", "--crf", "27", "--audio-bitrate=128k"]
    t0 = time.time()
    _log(f"렌더 시작 {total:.0f}초 영상")
    for attempt in (1, 2):
        r = subprocess.run(cmd, cwd=str(RENDER), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            break
        _log(f"렌더 실패 rc={r.returncode} (시도 {attempt}/2)\n{r.stderr[-1500:]}")
        time.sleep(10)
    if r.returncode != 0:
        raise SystemExit(1)
    _log(f"렌더 완료 {time.time() - t0:.0f}s → {od / 'video.mp4'} ({(od / 'video.mp4').stat().st_size / 1e6:.1f}MB)")
    _texts(kind, script, w, od, rng)


def _texts(kind: str, script: dict, w: dict, od, rng: str) -> None:
    k = KIND[kind]
    body = "\n".join(s["tts"] for s in script["scenes"])
    if kind == "kr":
        tags = ["코스피", "코스피 주간", "주간 증시", "국내증시", "증시", "주식", "한국주식", "외국인", "외국인 순매도", "개인 순매도", "기관 순매수",
                "기타법인", "자사주", "자사주 매입", "삼성전자", "SK하이닉스", "반도체", "반도체주", "코스피 7000", "유가", "금리", "수급", "국장", "누가샀나"]
        hashtags = "#코스피 #삼성전자 #SK하이닉스 #자사주 #외국인순매도 #반도체 #국내증시 #주간증시 #누가샀나"
    else:
        tags = ["미국주식", "미장", "나스닥", "S&P500", "다우", "미국 증시", "주간 증시", "필라델피아 반도체", "엔비디아", "AMD", "국제유가", "WTI",
                "미국 국채 금리", "10년물 금리", "달러", "엔화", "환율", "CPI", "PPI", "FOMC", "연준", "트럼프", "누가샀나"]
        hashtags = "#미국주식 #나스닥 #유가 #금리 #환율 #FOMC #미장 #주간증시 #누가샀나"
    desc = (f"{script['title']}\n누가샀나 {k['label']} — {rng} 한 주 동안 돈이 어디서 빠져 어디로 갔는지, 그 주 뉴스와 함께 정리합니다. "
            f"평일엔 매일 오후 4시 30분에 국장 마감이 올라옵니다.\n\n{body}\n\n{DISCLAIMER}\n\n{hashtags}")
    (od / "youtube_title.txt").write_text(script["title"], encoding="utf-8")
    (od / "youtube_description.txt").write_text(desc[:5000], encoding="utf-8")
    (od / "youtube_tags.txt").write_text(", ".join(tags), encoding="utf-8")
    th = script["threads"].rstrip()
    if not th.endswith(k["tag"]):
        th += "\n" + k["tag"]
    (od / "threads.txt").write_text(th, encoding="utf-8")
    (od / "threads_reply.txt").write_text(script["threads_reply"], encoding="utf-8")
    (od / "UPLOAD.md").write_text(f"# {k['label']} {rng}\n\n제목: {script['title']}\n\n태그: {', '.join(tags)}\n\n쓰레드:\n{th}\n\n첫 답글:\n{script['threads_reply']}\n", encoding="utf-8")
    _log(f"업로드 문구 저장 → {od}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    kind = args[0] if args else "kr"
    date = args[1] if len(args) > 1 else datetime.now().strftime("%Y%m%d")
    stage = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--stage=")), "all")
    if stage in ("script", "all"):
        s = stage_script(kind, date, fetch="--no-fetch" not in sys.argv)
        print((ROOT / "out" / KIND[kind]["dir"] / date / "script.txt").read_text(encoding="utf-8"))
    if stage in ("video", "all"):
        stage_video(kind, date)
