"""하루 실행기 — python run_day.py YYYYMMDD [--stage collect|compute|tts|render|review|all]
SPEC §3. 단계별로 따로 돌릴 수 있고, all은 순서대로 전부.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime

from _common import log


def _wait_for_us_close(d: str, margin_min: int = 35) -> None:
    """미국 정규장 마감(16:00 ET) + 여유 전이면 그때까지 기다린다.
    서머타임(EDT)엔 마감이 05:00 KST지만 11월~3월(EST)엔 06:00 KST라 05:40 실행이 장중이 된다."""
    from datetime import timedelta
    from collect_us import _et_offset
    now = datetime.now()
    if now.strftime("%Y%m%d") != d:
        return  # 과거 날짜 재실행이면 대기 없음
    off = _et_offset(now)                     # 13(EDT) / 14(EST)
    close_kst = now.replace(hour=(16 + off) % 24, minute=0, second=0, microsecond=0)
    if close_kst > now + timedelta(hours=12):
        close_kst -= timedelta(days=1)
    ready = close_kst + timedelta(minutes=margin_min)
    if now < ready:
        wait = (ready - now).total_seconds()
        log(d, "run", f"미국 마감 {close_kst:%H:%M} KST + {margin_min}분까지 {wait / 60:.0f}분 대기(EST 구간)")
        time.sleep(wait)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else datetime.now().strftime("%Y%m%d")
    stage = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--stage=")), "all")
    ed = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--edition=")), "kr")
    t0 = time.time()
    log(d, "run", f"시작 edition={ed} stage={stage}")
    from _common import DATA, load_json
    if ed == "us":
        # 아침 05:40 — 직전 미국 세션(월요일이면 금요일 세션 + 주간 일정)
        if stage in ("all", "collect"):
            _wait_for_us_close(d)
            import collect_us_kiwoom, collect_us, collect_krx
            asyncio.run(collect_us_kiwoom.main(d))
            kw = load_json(DATA / d / "raw" / "us_kiwoom.json") or {}
            q = (kw.get("index") or {}).get("QQQ") or {}
            if not q or q.get("missing") or not q.get("close"):
                log(d, "run", f"미국 휴장 또는 세션 데이터 없음(세션 {kw.get('session_et')}) → 아침편 건너뜀")
                return
            collect_us.main(d)
            collect_krx.main(d)          # 환율(전일 고시)
            import collect_us_index, collect_news
            collect_us_index.main(d)     # 공식 지수(야후 ^IXIC 등) — 헤드라인 숫자
            collect_news.main(d, "us")   # 마감 배경 헤드라인
        if stage in ("all", "compute", "krx"):
            import compute_us
            compute_us.compute_us(d)
    else:
        if stage == "intraday":
            # 14:00 장중 잠정 수급(코스피 전 종목 합산) → 마감 확정치와 비교해 '장중 대비 마감' 문장을 만든다
            import collect_kiwoom_sum
            asyncio.run(collect_kiwoom_sum.main(d, "kospi", "kiwoom_sum_1400.json"))
            log(d, "run", f"끝 {time.time() - t0:.0f}s")
            return
        if stage in ("all", "collect"):
            import collect_kiwoom, collect_flows, collect_krx, collect_us, collect_kiwoom_sum
            asyncio.run(collect_kiwoom.main(d))
            kw = load_json(DATA / d / "raw" / "kiwoom.json") or {}
            if not (kw.get("kospi") or {}).get("minutes"):
                log(d, "run", "국내 휴장(오늘 1분봉 없음) → 저녁편 건너뜀")
                return
            asyncio.run(collect_flows.main(d))
            asyncio.run(collect_kiwoom_sum.main(d, "kospi,kosdaq"))
            collect_krx.main(d)
            try:
                import collect_krx_naver
                collect_krx_naver.main(d)
            except Exception as e:
                log(d, "run", f"거래소 집계 수집 실패(무시): {e}")
            collect_us.main(d)
            import collect_us_index
            collect_us_index.main(d)     # 간밤 나스닥(방향 연결)
        if stage in ("all", "compute", "krx"):
            import collect_news
            if d.isdigit() and len(d) == 8:
                collect_news.main(d, "kr")   # 마감시황 기사는 15:35~17:00에 나오므로 18:00 제작 단계에서 수집
            else:
                log(d, "run", "접미사 날짜(샘플 판) — 뉴스 재수집 생략, 복사해 둔 raw/news_kr.json 사용")
            try:
                import collect_event
                asyncio.run(collect_event.main(d))   # data/events.json에 오늘 이슈가 있으면 종목 묶음 수집
            except Exception as e:
                log(d, "run", f"이슈 종목 수집 실패(무시): {e}")
            # 수급 브리핑(BRIEF_FORMAT_DESIGN §3): 유입 1위 업종의 대장주 + 최대 상승 종목(ka10059) → 그 업종·종목 이름으로 뉴스 한 번 더
            bs = {}
            try:
                import collect_brief
                bs = asyncio.run(collect_brief.main(d)) or {}   # 실패해도 {} — 예외를 내지 않는다
            except Exception as e:
                log(d, "run", f"브리핑 종목 수집 실패(무시): {e}")
            if bs.get("theme") and d.isdigit() and len(d) == 8:
                try:
                    names = [s.get("name") for s in (bs.get("stocks") or []) if s.get("name")][:2]
                    collect_news.main(d, "kr", extra=[f"{bs['theme']} 강세"] + names)
                except Exception as e:
                    log(d, "run", f"업종·종목 뉴스 추가 수집 실패(무시): {e}")
            elif bs.get("theme"):
                log(d, "run", "접미사 날짜(샘플 판) — 업종·종목 뉴스 추가 수집 생략")
            if stage == "krx":
                import collect_krx
                collect_krx.main(d)
            import compute
            compute.compute(d)
            try:
                import trends
                comp = load_json(DATA / d / "computed_kr.json") or {}
                ents = [m["theme"] for m in (comp.get("moves") or [])[:3]] + [x["name"] for x in (comp.get("stocks") or [])[:2]]
                trends.main(d, ents, [it["title"] for it in (comp.get("news_items") or [])])
            except Exception as e:
                log(d, "run", f"검색 키워드 수집 실패(무시): {e}")
    if stage in ("all", "compute", "krx", "polish") and "--no-polish" not in sys.argv:
        import polish
        polish.polish(d, ed)
    # 대본 확인 대기(JJ 2026-09-11): data/D/HOLD 가 있으면 자동 제작은 대본(compute)까지만. 확인 뒤 HOLD를 지우고 --stage=tts/render/review
    if stage in ("all", "krx") and (DATA / d / "HOLD").exists():
        log(d, "run", "대본 확인 대기(HOLD) — 음성·렌더·리뷰·게시 보류")
        log(d, "run", f"끝 {time.time() - t0:.0f}s")
        return
    if stage in ("all", "tts", "krx"):
        import tts
        asyncio.run(tts.main(d, ed))
    if stage in ("all", "render", "krx"):
        import render
        render.run(d, "all", ed)
    if stage in ("all", "review", "krx"):
        import review
        review.write(d, ed)
        if ed == "kr":                    # 썸네일도 같이 — JJ 2026-09-16 "이번 주는 내가 업로드 직접할게"
            import make_thumb_auto
            make_thumb_auto.main(d)
    if stage in ("all", "krx", "publish") or "--publish" in sys.argv:
        import publish
        mode = publish.config().get("mode", "confirm")
        if not publish.edition_enabled(ed):
            log(d, "run", f"{ed} 편은 게시하지 않음(개인 확인용)")
        elif mode == "auto" or "--publish" in sys.argv:
            # 제작 직후(all/krx): 유튜브만 올리고 publishAt으로 예약 공개. 게시 시각(publish 단계, 07:30/18:30): 틱톡·스레드 + 아직 안 올라간 유튜브.
            tg = publish.config().get("targets") or ["youtube", "tiktok", "threads"]
            if stage in ("all", "krx"):
                # 제작 직후: 유튜브만(예약 공개). 대상에 없으면 건너뛴다.
                if "youtube" in tg:
                    publish.publish(d, ed, go=True, targets=["youtube"])
                else:
                    log(d, "run", f"제작 완료 — 게시는 {publish.config()['publish_at'].get(ed)} 작업에서 ({', '.join(tg)})")
            else:
                publish.publish(d, ed, go=True)
        else:
            log(d, "run", f"게시 모드 confirm — review.html 확인 뒤 `publish.py {d} {ed} --go`")
    log(d, "run", f"끝 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
