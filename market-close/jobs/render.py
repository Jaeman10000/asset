"""18:08 렌더 — Remotion으로 card.png(1080×1350) + video.mp4(1080×1920). props = data/D/computed.json.
음성 파일은 render/public/voice/ 로 복사해 staticFile로 참조한다.
"""
from __future__ import annotations

import os

import shutil
import subprocess
import sys
import time
from datetime import datetime

from _common import DATA, ROOT, computed_path, load_json, log, out_dir, save_json

RENDER = ROOT / "render"


def run(d: str, what: str = "all", ed: str = "kr") -> None:
    comp = load_json(computed_path(d, ed))
    if not comp or "total_frames" not in comp:
        raise SystemExit(f"computed_{ed}.json에 장면 길이 없음 — tts 먼저")
    od = out_dir(d, ed)
    vid_id, card_id = ("VideoUS", "CardUS") if ed == "us" else ("Video", "Card")
    pub_voice = RENDER / "public" / "voice"
    pub_voice.mkdir(parents=True, exist_ok=True)
    for f in pub_voice.glob("*.*"):
        f.unlink()
    for f in (od / "voice").glob("*.*"):
        if f.is_file():
            shutil.copy(f, pub_voice / f.name)
    # BGM: data/publish_config.json의 bgm {enabled, file, volume}. 파일은 render/public/ 아래.
    try:
        import publish
        bgm = (publish.config().get("bgm") or {})
        if (bgm.get("enabled") or os.environ.get("BGM") == "1") and (RENDER / "public" / bgm.get("file", "")).exists():
            comp["bgm"] = {"file": bgm["file"], "volume": float(bgm.get("volume", 0.12))}
            log(d, "render", f"BGM {bgm['file']} vol {comp['bgm']['volume']}")
        else:
            comp.pop("bgm", None)
    except Exception as e:
        log(d, "render", f"BGM 설정 무시: {e}")
    props = RENDER / f"props_{ed}.json"
    save_json(props, comp)
    save_json(RENDER / "src" / f"sample_{ed}.json", comp)   # 스튜디오 기본 props
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    jobs = []
    if what in ("all", "card"):
        jobs.append(("card", [npx, "remotion", "still", "src/index.ts", card_id, str(od / "card.png"), f"--props={props}", "--log=error"]))
    if what in ("all", "video"):
        jobs.append(("video", [npx, "remotion", "render", "src/index.ts", vid_id, str(od / "video.mp4"), f"--props={props}", "--log=error", "--concurrency=4", "--crf", "27", "--audio-bitrate=128k"]))   # 10MB 이하 유지(브라우저 업로드 도구 한도). v4 배경 영상은 24면 11.8MB라 27
    for name, cmd in jobs:
        t0 = time.time()
        log(d, "render", f"{name}: {' '.join(cmd[1:6])} …")
        for attempt in (1, 2):
            r = subprocess.run(cmd, cwd=str(RENDER), capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                break
            log(d, "render", f"{name} 실패 rc={r.returncode} (시도 {attempt}/2)\n{r.stdout[-1500:]}\n{r.stderr[-2500:]}")
            if attempt == 1:
                time.sleep(20)
        if r.returncode != 0:
            raise SystemExit(1)
        log(d, "render", f"{name} 완료 {time.time() - t0:.0f}s → {od / ('card.png' if name == 'card' else 'video.mp4')}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"), sys.argv[2] if len(sys.argv) > 2 else "all", sys.argv[3] if len(sys.argv) > 3 else "kr")
