"""참고 채널 대본 수집기 — 다른 채널의 자막을 내려받아 '기법 연구용' 텍스트로 정리한다.

용도(JJ 2026-09-13 지시): 경제사냥꾼 채널의 쇼츠·롱폼 대본을 모아 성공 요인·스토리 기법을 분석하고,
주간 브리핑을 만들 때 '그 주에 같은 사건을 남들은 어떻게 풀었나'를 참고한다.
**표현을 베끼지 않는다.** 우리 대본은 우리 데이터와 우리 틀로 쓰고, 여기서는 구조·순서·장치만 배운다.

저장: data/refs/<channel_key>/index.json        영상 목록(제목·조회수·길이·업로드일)
      data/refs/<channel_key>/scripts/<id>.txt  자막을 문장으로 합친 대본(타임스탬프 유지)

실행:
  python collect_refs.py list   --channel UC7usMJDHmtbs_oegmzQKKMA --key hunter
  python collect_refs.py fetch  --key hunter --tab shorts --recent 40 --top 40
  python collect_refs.py fetch  --key hunter --tab videos --recent 20 --top 20
  python collect_refs.py fetch  --key hunter --since 20260907          (그 주에 올라온 것만)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from _common import venv_bin

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "data" / "refs"
YTDLP = venv_bin("yt-dlp")


def _run(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run([str(YTDLP), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def list_channel(channel: str, key: str) -> dict:
    """채널의 videos·shorts 목록을 한 번에 받아 index.json으로 저장."""
    base = REFS / key
    base.mkdir(parents=True, exist_ok=True)
    out: dict = {"channel": channel, "fetched_at": datetime.now().isoformat(timespec="seconds"), "tabs": {}}
    for tab in ("videos", "shorts"):
        r = _run(["--flat-playlist", "-J", f"https://www.youtube.com/channel/{channel}/{tab}"])
        if r.returncode != 0:
            print(f"  {tab} 실패 rc={r.returncode}: {r.stderr[-300:]}", file=sys.stderr)
            continue
        entries = (json.loads(r.stdout) or {}).get("entries") or []
        out["tabs"][tab] = [{"id": e.get("id"), "title": e.get("title"), "views": e.get("view_count"),
                             "duration": e.get("duration"), "url": e.get("url")} for e in entries if e.get("id")]
        print(f"  {tab}: {len(out['tabs'][tab])}개")
    (base / "index.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ── 자막 → 대본 ─────────────────────────────────────────────
_TAG = re.compile(r"<[^>]+>")
_TS = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.\d{3} --> ")


def vtt_to_script(vtt: str) -> str:
    """유튜브 자동자막 vtt → '[m:ss] 문장' 줄. 롤업 자막의 중복 줄을 걷어낸다."""
    lines, cur_t, seen, out = vtt.split("\n"), None, set(), []
    for ln in lines:
        m = _TS.match(ln.strip())
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            cur_t = h * 3600 + mi * 60 + s
            continue
        t = _TAG.sub("", ln).strip()
        if not t or t.startswith(("WEBVTT", "Kind:", "Language:")) or cur_t is None:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append((cur_t, t))
    # 같은 초에 여러 줄이면 합치고, 문장 끝(., ?, !)에서 끊는다
    merged, buf, t0 = [], "", None
    for t, txt in out:
        if t0 is None:
            t0 = t
        buf = (buf + " " + txt).strip()
        if re.search(r"[.?!]$", txt):
            merged.append((t0, buf)); buf, t0 = "", None
    if buf:
        merged.append((t0 or 0, buf))
    return "\n".join(f"[{t // 60}:{t % 60:02d}] {s}" for t, s in merged)


def fetch_one(vid: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 200:
        return True
    with tempfile.TemporaryDirectory() as td:
        r = _run(["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "ko,ko-orig",
                  "--sub-format", "vtt", "-o", str(Path(td) / "%(id)s.%(ext)s"),
                  f"https://www.youtube.com/watch?v={vid}"], timeout=180)
        cand = sorted(Path(td).glob("*.vtt"), key=lambda p: (".ko-orig." not in p.name, -p.stat().st_size))
        if not cand:
            print(f"  자막 없음 {vid} (rc={r.returncode})", file=sys.stderr)
            return False
        script = vtt_to_script(cand[0].read_text(encoding="utf-8", errors="replace"))
        if len(script) < 120:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(script, encoding="utf-8")
        return True


def pick(items: list[dict], recent: int, top: int, since: str | None) -> list[dict]:
    """최근 N개 + 조회수 상위 N개(중복 제거). since(YYYYMMDD)가 있으면 업로드일 필터는 호출자가 채운다."""
    chosen, seen = [], set()
    for x in items[:recent]:
        if x["id"] not in seen:
            seen.add(x["id"]); chosen.append(x)
    for x in sorted(items, key=lambda y: -(y.get("views") or 0))[:top]:
        if x["id"] not in seen:
            seen.add(x["id"]); chosen.append(x)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "fetch"])
    ap.add_argument("--channel"); ap.add_argument("--key", required=True)
    ap.add_argument("--tab", default="shorts", choices=["shorts", "videos"])
    ap.add_argument("--recent", type=int, default=30); ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--since")
    a = ap.parse_args()
    base = REFS / a.key
    if a.cmd == "list":
        list_channel(a.channel, a.key); return
    idx = json.loads((base / "index.json").read_text(encoding="utf-8"))
    items = idx["tabs"].get(a.tab) or []
    chosen = pick(items, a.recent, a.top, a.since)
    print(f"{a.tab} {len(chosen)}개 수집")
    ok = 0
    for i, x in enumerate(chosen, 1):
        if fetch_one(x["id"], base / "scripts" / f"{x['id']}.txt"):
            ok += 1
        if i % 10 == 0:
            print(f"  {i}/{len(chosen)} (성공 {ok})", flush=True)
    print(f"완료 {ok}/{len(chosen)} → {base / 'scripts'}")


if __name__ == "__main__":
    main()
