"""대본·영상 자동 점검 — JJ에게 보내기 전에 반드시 통과시킨다.

배경(2026-09-12~13 JJ 지적에서 나온 규칙):
  · 3분을 넘으면 쇼츠 피드에서 빠진다. 평일 2분, 주말 3분.
  · 축약 종결형("팜/오름")·채팅 기호·압축 숫자(9.9조)는 쓰지 않는다.
  · 대본을 고치면 화면이 그대로라 말과 어긋난다 → 렌더 뒤 장면별 프레임을 뽑아 눈으로 대조한다.
  · 마지막 사실 뒤에는 '그래서 무슨 뜻'이 있어야 한다.
  · 최근 편과 문장 뼈대가 겹치면 AI 티가 난다.

실행:
  python qa_script.py script --kind us --date 20260913     대본만 점검(렌더 전)
  python qa_script.py frames --kind us --date 20260913     렌더된 영상에서 장면별 프레임 추출
  python qa_script.py all    --kind kr --date 20260912
kind: day(평일) | kr(토 국장 주간) | us(일 미국 주간)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FF = Path(r"C:/Users/Jeff/Documents/GitHub/asset/market-close/render/node_modules/@remotion/compositor-win32-x64-msvc/ffmpeg.exe")
CPS = 7.2                                   # edge-tts InJoon +20% 실측 초당 글자수
LIMIT = {"day": 115, "kr": 175, "us": 175}  # 초 상한. 평일 2분·주말 3분에서 안전 여유를 뺀 값
FLOOR = {"day": 100, "kr": 150, "us": 150}  # 초 하한. 1:30은 짧다(JJ 2026-09-13) — 평일은 1:45~1:55가 자리
CLOSE_MAX = {"day": 285, "kr": 215, "us": 215}   # 마무리 두 장면(s5+s6) 자수 상한. 평일 285 = 20260911 확정본 278 + 여유
# 매 편 똑같이 들어가는 고정문 — 뼈대 중복 검사에서 뺀다(빼지 않으면 매일 '겹침'으로 잡힌다)
FIXED = ("그 답이 궁금하면 구독해 두세요.", "누가샀나였습니다.", "국장 마감은 매일 오후 4시 30분에 올라옵니다.",
         "누가샀나 주간 결산이었습니다.", "누가샀나 미국 주간 결산이었습니다.",
         "평일엔 매일 오후 4시 30분에 국장 마감이 올라옵니다.")
DIRS = {"day": ("", "kr"), "kr": ("weekly", ""), "us": ("weekly_us", "")}

BAD_END = re.compile(r"(팜|음|함|짐|옴|됨|뜀|빠짐|올림|내림|삼|샀음|팔았음)\s*\.{0,2}$")
CHAT = re.compile(r"[ㅋㅎㅠㅜ]")
TIGHT_NUM = re.compile(r"\d+\.\d+조")
# '그래서 무슨 뜻'으로 인정하는 표현. 해석(앞)이거나 다음 확인점(뒤)이면 통과.
MEANING = re.compile(r"뜻|셈|모습|보입니다|볼 수 있|가까워|남아 있|의미|같은 배|한 주입니다|한 주였|"
                    r"볼 건|볼 것|확인하|확인됩니다|봅니다|보겠습니다|이어지는지|사느냐|사는지")


def out_dir(kind: str, date: str) -> Path:
    a, b = DIRS[kind]
    return ROOT / "out" / a / date / b if a else ROOT / "out" / date / b


def data_script(kind: str, date: str) -> Path:
    a, _ = DIRS[kind]
    return ROOT / "data" / a / date / "script.json" if a else ROOT / "data" / date / "computed_kr.json"


def load_scenes(kind: str, date: str) -> list[dict]:
    p = data_script(kind, date)
    d = json.loads(p.read_text(encoding="utf-8"))
    return d["scenes"] if kind in ("kr", "us") else d.get("scenes") or []


def recent_scripts(kind: str, date: str, n: int = 3) -> list[str]:
    """같은 편의 직전 N편 대본(뼈대 비교용)."""
    a, b = DIRS[kind]
    base = ROOT / "out" / a if a else ROOT / "out"
    ds = sorted([x for x in base.iterdir() if x.is_dir() and x.name.isdigit() and x.name < date], reverse=True)
    out = []
    for d in ds[:n]:
        f = (d / b / "script.txt") if b else (d / "script.txt")
        if f.exists():
            out.append(f.read_text(encoding="utf-8"))
    return out


def mask(s: str) -> str:
    """숫자·주체를 가려 문장 뼈대만 남긴다."""
    s = re.sub(r"[\d,.]+%?", "N", s)
    for w in ("외국인", "기관", "개인", "기타법인", "반도체", "에너지", "헬스케어", "코스피", "나스닥", "S&P500", "다우"):
        s = s.replace(w, "X")
    return re.sub(r"\s+", "", s)


def check_script(kind: str, date: str) -> list[str]:
    scenes = load_scenes(kind, date)
    bad: list[str] = []
    total = sum(len(s["tts"]) for s in scenes)
    sec = total / CPS + 0.4 * len(scenes)
    if sec > LIMIT[kind]:
        bad.append(f"길이 {sec:.0f}초 > 한도 {LIMIT[kind]}초 ({total}자, {int(sec - LIMIT[kind]) * CPS:.0f}자 줄여야 함)")
    elif sec < FLOOR[kind]:
        bad.append(f"길이 {sec:.0f}초 < 하한 {FLOOR[kind]}초 — 짧으면 성의 없어 보인다({total}자)")
    close = sum(len(x["tts"]) for x in scenes[-2:])
    if close > CLOSE_MAX[kind]:
        bad.append(f"마무리 {close}자 > {CLOSE_MAX[kind]}자 — 끝이 길면 이탈한다")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "jobs"))
    from checks import forbidden
    import tts as _tts                        # 실제로 들리는 문장으로 검사한다(2.3조는 '2조 3천억'으로 읽힌다)
    for s in scenes:
        t = _tts.speakable(s["tts"])
        if hits := forbidden.find(t):
            bad.append(f"{s['id']} 금지어 {hits}")
        for line in re.split(r"(?<=[.?!])\s+", t):
            if line and BAD_END.search(line.strip()):
                bad.append(f"{s['id']} 축약 종결형 — {line[:26]}")
            if line and CHAT.search(line):
                bad.append(f"{s['id']} 채팅 기호 — {line[:26]}")
        if TIGHT_NUM.search(t):
            bad.append(f"{s['id']} 압축 숫자(9.9조 형태) — 풀어 쓸 것: {TIGHT_NUM.findall(t)}")
    last = scenes[-2]["tts"] + scenes[-1]["tts"] if len(scenes) > 1 else scenes[-1]["tts"]
    if not MEANING.search(last):
        bad.append("마지막에 '그래서 무슨 뜻'이 없음 — 사실만 나열하고 끝남")
    qs = sum(1 for s in scenes if "?" in s["tts"])
    if qs < max(2, len(scenes) // 3):
        bad.append(f"질문이 {qs}개뿐 — 장면마다 다음 질문으로 이어지는지 볼 것")
    def _skel(txt: str) -> set[str]:
        return {mask(x) for x in re.split(r"(?<=[.?!])\s+", txt) if len(x) > 12 and x.strip() not in FIXED}

    mine = set().union(*(_skel(s["tts"]) for s in scenes)) if scenes else set()
    for k, prev in enumerate(recent_scripts(kind, date), 1):
        dup = mine & _skel(prev)
        if len(dup) >= 2:
            bad.append(f"직전 {k}번째 편과 문장 뼈대 {len(dup)}개 겹침 — 표현을 바꿀 것")
    return bad


def frames(kind: str, date: str) -> Path:
    """장면·큐마다 프레임을 뽑아 out/.../frames/ 에 저장. 말과 화면을 눈으로 대조하는 용도."""
    od = out_dir(kind, date)
    props = json.loads((od / "props.json").read_text(encoding="utf-8"))
    fd = od / "frames"
    fd.mkdir(exist_ok=True)
    for f in fd.glob("*.jpg"):
        f.unlink()
    n = 0
    for sc in props["scenes"]:
        for c in sc.get("cues") or []:
            if len(c["text"]) < 10:
                continue
            t = sc["start"] + c["start"] + min(1.6, (c["end"] - c["start"]) * 0.7)
            safe = re.sub(r"[^0-9A-Za-z가-힣]", "", c["text"])[:16]
            subprocess.run([str(FF), "-y", "-loglevel", "error", "-ss", f"{t:.1f}", "-i", str(od / "video.mp4"),
                            "-frames:v", "1", "-q:v", "5", "-vf", "scale=420:-1",
                            str(fd / f"{n:02d}_{sc['id']}_{safe}.jpg")], check=True)
            n += 1
    print(f"프레임 {n}장 → {fd}\n  각 파일 이름이 그때 나오는 말이다. 화면과 맞는지 눈으로 대조할 것.")
    return fd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["script", "frames", "all"])
    ap.add_argument("--kind", required=True, choices=["day", "kr", "us"])
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    rc = 0
    if a.cmd in ("script", "all"):
        bad = check_script(a.kind, a.date)
        print("대본 점검:", "통과" if not bad else f"{len(bad)}건")
        for x in bad:
            print("  ✗", x)
        rc = 1 if bad else 0
    if a.cmd in ("frames", "all"):
        frames(a.kind, a.date)
    sys.exit(rc)


if __name__ == "__main__":
    main()
