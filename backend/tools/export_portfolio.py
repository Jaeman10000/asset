"""포트폴리오 내보내기 — 더블클릭 한 번으로 보유 현황을 텍스트로 저장한다.

왜: 매수할 때마다 엑셀에 종목·수량·평단을 손으로 옮겨 적는 게 번거롭다는 요구.
    이 exe를 누르면 한국주식·미국주식·암호화폐 전부를 긁어와 파일로 떨구고
    메모장으로 열어준다.

내보내는 것 (문서 폴더\\VitalityNexus\\):
    포트폴리오_YYYY-MM-DD_HHMM.txt   사람이 읽는 표 — 메모장으로 자동으로 열림
    포트폴리오_YYYY-MM-DD_HHMM.csv   엑셀에 그대로 붙여넣는 용도(엑셀 정리가 원래 목적)

데이터 출처 우선순위:
    ① 이미 켜져 있는 앱의 백엔드(127.0.0.1:8787) — 가장 빠르고 캐시가 데워져 있다
    ② 앱이 꺼져 있으면 키움/업비트/빗썸을 직접 호출 — 앱 없이도 단독 실행된다
"""
from __future__ import annotations

import asyncio
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# PyInstaller 번들이 아니라 소스로 돌릴 때 backend 패키지를 찾게 한다
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 환경변수로 덮어쓸 수 있게 — 앱이 꺼진 폴백 경로를 검증할 때 죽은 포트로 돌린다
BACKEND_URL = os.environ.get(
    "VITALITY_BACKEND_URL", "http://127.0.0.1:8787/portfolio/snapshot"
)
KST = timezone(timedelta(hours=9))


def _init_console() -> None:
    """윈도우 콘솔을 UTF-8로. 안 하면 한글 안내문에서 프로그램이 죽는다.

    실측: 더블클릭하면 콘솔 코드페이지가 cp949라 '—' 하나에
    UnicodeEncodeError가 나고, 그걸 잡으려던 except 절의 input()마저
    EOFError로 터져 창이 그냥 닫혔다.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # type: ignore[attr-defined]
            ctypes.windll.kernel32.SetConsoleCP(65001)  # type: ignore[attr-defined]
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def _pause(msg: str = "\n  엔터를 누르면 닫힙니다…") -> None:
    """더블클릭 실행이면 창이 바로 닫히지 않게 붙잡는다.
    파이프로 돌릴 땐 stdin이 없으니 EOFError를 무시한다."""
    try:
        input(msg)
    except (EOFError, KeyboardInterrupt):
        pass


# ── 데이터 가져오기 ──────────────────────────────────────────────

def _from_running_app() -> dict[str, Any] | None:
    """앱이 켜져 있으면 그 백엔드에서 받는다. 없으면 None."""
    try:
        import httpx

        r = httpx.get(BACKEND_URL, timeout=60.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _use_app_data_dir() -> None:
    """앱과 같은 데이터 폴더를 보게 한다.

    Tauri는 앱을 띄울 때 VITALITY_DATA_DIR로 app_data_dir을 넣어준다. 이 exe는
    단독 실행이라 그 값이 없고, 그러면 paths.data_dir()이 동결 빌드 폴백인
    %APPDATA%\\vitality-nexus 로 떨어져 보유종목(holdings.json)을 못 찾는다.
    실제 앱 폴더를 먼저 찾아 넣어준다.
    """
    if os.environ.get("VITALITY_DATA_DIR"):
        return
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return
    candidates = [Path(appdata) / "com.jj.vitality-nexus", Path(appdata) / "vitality-nexus"]
    for d in candidates:
        if (d / "holdings.json").exists():
            os.environ["VITALITY_DATA_DIR"] = str(d)
            return
    for d in candidates:
        if d.is_dir():
            os.environ["VITALITY_DATA_DIR"] = str(d)
            return


def _from_apis() -> dict[str, Any] | None:
    """앱이 꺼져 있을 때 — 키움/거래소를 직접 호출한다."""
    _use_app_data_dir()
    try:
        # 라우트가 쓰는 것과 같은 빌더 — 앱과 같은 숫자가 나온다
        from app.db import init_db
        from app.routes.portfolio import _build_snapshot
    except Exception as exc:  # noqa: BLE001
        print(f"  백엔드 모듈을 불러오지 못했습니다: {exc}")
        return None
    try:
        # 스냅샷 빌더가 결과를 DB에 적는다. 평소엔 앱 lifespan이 테이블을 만들지만
        # 단독 실행엔 그게 없어서 'no such table: snapshots'로 죽었다(실측).
        init_db()
        snap = asyncio.run(_build_snapshot())
        return snap.model_dump() if hasattr(snap, "model_dump") else dict(snap)
    except Exception as exc:  # noqa: BLE001
        print(f"  조회 실패: {exc}")
        return None


# ── 서식 ────────────────────────────────────────────────────────

def _won(v: float) -> str:
    return f"{round(v):,}"


def _num(v: float) -> str:
    """수량 — 주식은 정수, 코인은 소수점이 의미 있으므로 살린다."""
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.8f}".rstrip("0").rstrip(".")


def _price(v: float, cur: str) -> str:
    if cur == "USD":
        return f"${v:,.2f}"
    if abs(v) < 100:  # 코인 소액 단가
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{round(v):,}"


_GROUPS = [
    ("한국 주식", lambda p: p.get("assetType") == "stock" and p.get("region") == "KR"),
    ("미국 주식", lambda p: p.get("assetType") == "stock" and p.get("region") == "US"),
    ("암호화폐", lambda p: p.get("assetType") == "crypto"),
]

_COLS = ["종목", "코드", "수량", "평단", "현재가", "평가금액(원)", "매수금액(원)", "평가손익(원)", "수익률"]
_W = [30, 10, 13, 13, 13, 16, 16, 15, 9]


def _w(text: str) -> int:
    """한글·전각은 한 글자가 두 칸을 먹는다."""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def _clip(text: str, width: int) -> str:
    """표시 폭 기준으로 자른다.

    안 자르면 긴 이름 한 줄 때문에 그 행의 이후 컬럼이 전부 오른쪽으로 밀린다
    (실측: '미국 초단기 국채 아이셰어즈 ETF').
    """
    if _w(text) <= width:
        return text
    out = ""
    for ch in text:
        if _w(out) + _w(ch) > width - 1:
            break
        out += ch
    return out + "…"


def _row_cells(p: dict[str, Any]) -> list[str]:
    cur = p.get("currency", "KRW")
    pnl = p.get("value", 0) - p.get("cost", 0)
    return [
        str(p.get("name", "")),
        str(p.get("symbol", "")),
        _num(p.get("qty", 0)),
        _price(p.get("avg", 0), cur),
        _price(p.get("price", 0), cur),
        _won(p.get("value", 0)),
        _won(p.get("cost", 0)),
        ("+" if pnl >= 0 else "−") + _won(abs(pnl)),
        f"{p.get('ret', 0):+.2f}%",
    ]


def _pad(cells: list[str]) -> str:
    """한글은 폭이 2배라 len()으로 맞추면 표가 어긋난다 — 실제 표시 폭으로 채우고,
    넘치는 칸은 잘라서 이후 컬럼이 밀리지 않게 한다."""
    out = []
    for cell, width in zip(cells, _W):
        cell = _clip(cell, width - 1)
        out.append(cell + " " * max(1, width - _w(cell)))
    return "".join(out).rstrip()


def render_text(snap: dict[str, Any]) -> str:
    now = datetime.now(KST)
    positions = snap.get("positions") or []
    totals = snap.get("totals") or {}
    lines: list[str] = []
    lines.append("=" * 132)
    lines.append(f"  VITALITY NEXUS — 포트폴리오  ({now:%Y-%m-%d %H:%M} KST)")
    lines.append("=" * 132)
    lines.append("")

    for title, match in _GROUPS:
        rows = [p for p in positions if match(p)]
        if not rows:
            continue
        rows.sort(key=lambda p: -p.get("value", 0))
        val = sum(p.get("value", 0) for p in rows)
        cost = sum(p.get("cost", 0) for p in rows)
        pnl = val - cost
        rate = (pnl / cost * 100) if cost else 0.0

        lines.append(f"[{title}]  {len(rows)}종목")
        lines.append("-" * 132)
        lines.append(_pad(_COLS))
        lines.append("-" * 132)
        for p in rows:
            lines.append(_pad(_row_cells(p)))
        lines.append("-" * 132)
        lines.append(
            _pad(["소계", "", "", "", "", _won(val), _won(cost),
                  ("+" if pnl >= 0 else "−") + _won(abs(pnl)), f"{rate:+.2f}%"])
        )
        lines.append("")

    t = totals.get("total") or {}
    if t:
        lines.append("=" * 132)
        lines.append(
            f"  총 평가금액 {_won(t.get('value', 0))}원"
            f"   |   매수금액 {_won(t.get('cost', 0))}원"
            f"   |   손익 {'+' if t.get('pnl', 0) >= 0 else '−'}{_won(abs(t.get('pnl', 0)))}원"
            f" ({t.get('pnlPct', 0):+.2f}%)"
        )
        # 키 이름은 schemas.Totals 그대로 — kr / us / crypto
        for title, key in (("한국 주식", "kr"), ("미국 주식", "us"), ("암호화폐", "crypto")):
            b = totals.get(key)
            if b and b.get("value"):
                share = b["value"] / t["value"] * 100 if t.get("value") else 0
                lines.append(
                    f"    {title:<10} {_won(b['value']):>16}원  ({share:4.1f}%)   {b.get('pnlPct', 0):+.2f}%"
                )
        lines.append("=" * 132)

    lines.append("")
    lines.append("· 환율·현재가는 조회 시점 기준이며, 평가금액은 원화 환산값입니다.")
    lines.append("· 미국 주식의 수익률은 증권사가 주는 값(수수료 반영, 달러 기준)이고,")
    lines.append("  평가손익(원)은 원화 환산 평가금액 − 매수금액입니다. 등락이 근소한 종목은")
    lines.append("  둘의 부호가 다를 수 있습니다 — 달러로는 손실인데 환율 덕에 원화로는 이익인 경우.")
    return "\n".join(lines)


def write_csv(path: Path, snap: dict[str, Any]) -> None:
    """엑셀용 — 한글 깨짐 방지로 UTF-8 BOM."""
    positions = snap.get("positions") or []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["구분", "종목", "코드", "수량", "평단", "현재가", "통화",
                    "평가금액(원)", "매수금액(원)", "평가손익(원)", "수익률(%)"])
        for title, match in _GROUPS:
            rows = sorted((p for p in positions if match(p)), key=lambda p: -p.get("value", 0))
            for p in rows:
                w.writerow([
                    title, p.get("name", ""), p.get("symbol", ""),
                    p.get("qty", 0), p.get("avg", 0), p.get("price", 0), p.get("currency", ""),
                    round(p.get("value", 0)), round(p.get("cost", 0)),
                    round(p.get("value", 0) - p.get("cost", 0)), round(p.get("ret", 0), 2),
                ])


# ── 저장 위치 ───────────────────────────────────────────────────

def out_dir() -> Path:
    """문서\\VitalityNexus. 문서 폴더를 못 찾으면 exe 옆에 만든다."""
    env = os.environ.get("VITALITY_EXPORT_DIR")
    if env:
        d = Path(env)
    else:
        home = Path.home()
        docs = home / "Documents"
        if not docs.is_dir():
            docs = home / "문서"
        d = (docs if docs.is_dir() else Path(sys.argv[0]).resolve().parent) / "VitalityNexus"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main() -> int:
    _init_console()
    print("VITALITY NEXUS — 포트폴리오 내보내기")
    print()
    print("  앱 백엔드 확인 중…")
    snap = _from_running_app()
    if snap:
        print("  앱에서 받았습니다.")
    else:
        print("  앱이 꺼져 있어 증권사/거래소에 직접 조회합니다 (30초 정도 걸립니다)…")
        snap = _from_apis()

    if not snap or not snap.get("positions"):
        print()
        print("  보유 종목을 가져오지 못했습니다.")
        print("  앱을 켠 상태에서 다시 실행하거나, API 키 설정을 확인하세요.")
        _pause()
        return 1

    stamp = datetime.now(KST).strftime("%Y-%m-%d_%H%M")
    d = out_dir()
    txt = d / f"포트폴리오_{stamp}.txt"
    csv_path = d / f"포트폴리오_{stamp}.csv"

    # 메모장이 확실히 읽도록 CRLF + UTF-8 BOM
    txt.write_text(render_text(snap), encoding="utf-8-sig", newline="\r\n")
    write_csv(csv_path, snap)

    print()
    print(f"  저장 완료 — {d}")
    print(f"    {txt.name}   (메모장)")
    print(f"    {csv_path.name}   (엑셀)")

    try:
        os.startfile(txt)  # type: ignore[attr-defined]  # Windows 전용
    except Exception:
        print("  (메모장을 자동으로 열지 못했습니다 — 위 폴더에서 직접 열어주세요)")
        _pause()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        # 더블클릭 실행이라 창이 바로 닫히면 원인을 볼 수 없다
        _init_console()
        print(f"\n  예상치 못한 오류: {exc}")
        _pause()
        sys.exit(1)
