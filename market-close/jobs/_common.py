"""공통: 경로, 백엔드 임포트, 숫자 파싱, 키움 호출 래퍼."""
from __future__ import annotations

import re

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent          # market-close/
REPO = ROOT.parent                                      # asset/
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

DATA = ROOT / "data"
OUT = ROOT / "out"
LOGS = ROOT / "logs"

KIWOOM_BASE = "https://api.kiwoom.com"
KIWOOM_PATHS = {
    "chart": "/api/dostk/chart",
    "sect": "/api/dostk/sect",
    "mrkcond": "/api/dostk/mrkcond",
    "stkinfo": "/api/dostk/stkinfo",
    "rkinfo": "/api/dostk/rkinfo",
    "frgnistt": "/api/dostk/frgnistt",
    "us_chart": "/api/us/chart",
}


def day_dir(d: str) -> Path:
    p = DATA / d / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def out_dir(d: str, ed: str = "kr") -> Path:
    p = OUT / d / ed
    (p / "voice").mkdir(parents=True, exist_ok=True)
    return p


def computed_path(d: str, ed: str = "kr") -> Path:
    return DATA / d / f"computed_{ed}.json"


def log(d: str, stage: str, msg: str) -> None:
    LOGS.mkdir(exist_ok=True)
    line = f"{datetime.now().strftime('%H:%M:%S')} [{stage}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:  # cp949 콘솔
        print(line.encode("utf-8", "replace").decode("cp949", "replace"), flush=True)
    with open(LOGS / f"{d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def num(v: Any, default: float = 0.0) -> float:
    """키움 문자열 숫자 → float. '+123', '-45', '--45'(이중 마이너스), '1,234' 처리."""
    if v is None:
        return default
    s = str(v).replace(",", "").strip()
    if not s:
        return default
    neg = s.startswith("-")
    s = s.lstrip("+-")
    try:
        x = float(s)
    except ValueError:
        return default
    return -x if neg else x


def save_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


async def kiwoom_call(hc, token: str, cat: str, api_id: str, body: dict, cont: str = "N", nk: str = ""):
    """카테고리+TR 호출. (json, cont-yn, next-key) 반환. 429(초당 제한)는 1.2s·2.4s·4.8s 대기 후 재시도.
    실측: 연속조회를 쉼 없이 부르면 해외 차트에서 429가 난다. 모든 호출 뒤 0.25s 쉰다."""
    import asyncio
    for attempt in range(4):
        r = await hc.post(
            f"{KIWOOM_BASE}{KIWOOM_PATHS[cat]}",
            headers={"authorization": f"Bearer {token}", "api-id": api_id, "cont-yn": cont, "next-key": nk},
            json=body,
        )
        if r.status_code == 429 and attempt < 3:
            await asyncio.sleep(1.2 * (2 ** attempt))
            continue
        r.raise_for_status()
        await asyncio.sleep(0.25)
        return r.json(), r.headers.get("cont-yn", "N"), r.headers.get("next-key", "")
    raise RuntimeError("unreachable")


def prev_trading_day(d: str) -> str:
    """아카이브 저장 날짜 기준 직전 거래일(없으면 달력 하루 전)."""
    try:
        from app.services import flow_store  # noqa
        dates = [x.replace("-", "") for x in flow_store.saved_dates()]
        prior = [x for x in dates if x < d]
        if prior:
            return max(prior)
    except Exception:
        pass
    from datetime import timedelta
    dt = datetime.strptime(d, "%Y%m%d") - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


# 제목 끝 날짜(JJ 2026-09-19 "내일부터"): 날짜는 제목 맨 뒤에 붙인다 — 쇼츠 피드는 앞 40자만 보이니 훅이 먼저, 날짜는 검색용.
# 앞에 붙은 날짜("9월 18일 …")는 떼어 뒤로 옮기고, 이미 뒤에 날짜가 있으면 그대로 둔다.
_DATE_RE = r"(\d{1,2}월\s*\d{1,2}일|\d{1,2}/\d{1,2})"


def tag_tail(title: str, tag: str) -> str:
    """정보형 제목 — **날짜를 붙이지 않는다**(JJ 2026-09-21).
    "정보성 영상은 날짜를 앞으로 안 보여줘도 될 것 같아. 그러면 유기적으로 업로드 날짜 변경할 때 그냥 바꾸면 되니까."
    국장 마감·주간 브리핑은 그대로 date_tail 을 쓴다(날짜 항상 붙임)."""
    import re
    t = (title or "").strip()
    t = re.sub(r"^\s*" + _DATE_RE + r"\s*", "", t).strip()
    t = re.sub(r"\s*#\d{2,4}(?=\s|$)", "", t).strip()
    m = re.search(r"^(.*?)\s*\|\s*([^|]*)$", t)
    if m:                                   # 이미 '| 9/30 환율' 이면 날짜만 떼고 꼬리표는 살린다
        head, last = m.group(1).strip(), re.sub(_DATE_RE, "", m.group(2)).strip(" ·-")
        return (f"{head} | {last}" if last else head)[:100]
    return (f"{t} | {tag}" if tag else t)[:100]


def strip_date(s: str) -> str:
    """썸네일 태그·배지에서 날짜만 떼어 낸다 — '9/25 로봇 해설' → '로봇 해설'."""
    import re
    return re.sub(_DATE_RE, "", s or "").strip(" ·-") or (s or "").strip()


def date_tail(title: str, tail: str) -> str:
    import re
    t = (title or "").strip()
    t = re.sub(r"^\s*" + _DATE_RE + r"\s*", "", t).strip()
    t = re.sub(r"\s*#\d{2,4}(?=\s|$)", "", t).strip()          # 회차 번호(#010)는 넣지 않는다(SCRIPT_GUIDE §8)
    if re.search(r"\|\s*[^|]*" + _DATE_RE + r"[^|]*$", t):
        return t[:100]
    return f"{t} | {tail}"[:100]


def pct_speech_issues(text: str) -> list[str]:
    """말하는 %는 소수 첫째 자리까지, .0 은 뗀다(JJ 9/18 '2.66% → 2.6%', 9/19 '5.01% → 5%').
    기준금리 수준(일본 1.25%, 3.75에서 4%)만 허용 — 시장 금리(10년물 5.01%)는 말할 땐 5%."""
    bad = []
    for sent in re.split(r"(?<=[.?!])\s+", text):
        for m in re.finditer(r"(\d+\.\d{2,}|\d+\.0)%", sent):
            if re.search(r"기준금리|정책금리|금리를\s*\S*\s*(올려|내려)", sent) and not m.group(1).endswith(".0"):
                continue
            bad.append(m.group(0))
    return bad


# ══════════════════════════════════════════════════════════════════════════════
# OS 무관 경로 — 맥미니(darwin-arm64)로 옮겨도 그대로 돌게 (2026-09-24)
# 윈도우에만 있던 것: remotion ffmpeg(.exe), 맑은 고딕, .venv/Scripts, 세션별 스크래치.
# ══════════════════════════════════════════════════════════════════════════════
def ffmpeg_path() -> Path | None:
    """remotion 이 깔아 둔 ffmpeg — 플랫폼 패키지 이름이 OS마다 다르다.

    win32-x64-msvc / darwin-arm64 / darwin-x64 / linux-x64-gnu … 무엇이든 찾는다.
    """
    base = ROOT / "render" / "node_modules" / "@remotion"
    for pat in ("compositor-*/ffmpeg.exe", "compositor-*/ffmpeg"):
        for p in sorted(base.glob(pat)):
            if p.is_file():
                if sys.platform == "darwin":
                    # 맥 빌드는 옆의 libav*.dylib 를 '@rpath' 없이 찾는다 — 폴더를 알려 줘야 뜬다(자식 프로세스가 물려받는다)
                    os.environ["DYLD_LIBRARY_PATH"] = str(p.parent)
                return p
    import shutil as _sh
    w = _sh.which("ffmpeg")
    return Path(w) if w else None


_FONT_CANDS = (
    "C:/Windows/Fonts/malgunbd.ttf", "C:/Windows/Fonts/malgun.ttf",                 # 윈도우
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",                                   # macOS 기본 한글
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/NanumGothicBold.ttf", "/Library/Fonts/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",                          # 리눅스
)


def korean_font() -> Path | None:
    """자막을 그릴 한글 폰트 — 없으면 None(부르는 쪽이 글자 없이 진행한다)."""
    for c in _FONT_CANDS:
        p = Path(c)
        if p.exists():
            return p
    return None


def venv_bin(name: str) -> Path | None:
    """가상환경 실행파일 — 윈도우는 .venv/Scripts/<name>.exe, 그 외는 .venv/bin/<name>."""
    base = ROOT.parent / "backend" / ".venv"
    for rel in (f"Scripts/{name}.exe", f"bin/{name}"):
        p = base / rel
        if p.exists():
            return p
    import shutil as _sh
    w = _sh.which(name)
    return Path(w) if w else None


def scratch_dir(sub: str = "") -> Path:
    """임시 작업 폴더 — 세션 스크래치가 있으면 그걸, 없으면 OS 임시 폴더."""
    import os as _os
    import tempfile as _tf
    base = _os.environ.get("CLAUDE_SCRATCHPAD") or _tf.gettempdir()
    p = Path(base) / "nugasatna" / sub if sub else Path(base) / "nugasatna"
    p.mkdir(parents=True, exist_ok=True)
    return p
