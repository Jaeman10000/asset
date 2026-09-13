"""제작 직후 review — out/D/ed/review.html: 올릴 것 전부를 한 페이지에(복사 버튼 포함).
유튜브 제목·설명·태그, 스레드 본문, 카드·영상 미리보기, 대본, 경고. 같은 내용을 txt로도 옆에 둔다.
승인 기록은 metrics/review_log.csv."""
from __future__ import annotations

import html
import sys
from datetime import datetime

from _common import DATA, ROOT, computed_path, load_json, log, out_dir


def _texts(comp: dict, ed: str) -> dict:
    try:
        import publish
        return publish.texts(comp, ed)
    except Exception as e:  # 게시 모듈이 없어도 review는 나와야 한다
        log(comp.get("date", "?"), "review", f"문안 생성 실패(캡션으로 대체): {e}")
        return {"title": "", "description": comp.get("caption", ""), "tags": [], "threads": comp.get("caption", "")}


def write(d: str, ed: str = "kr") -> None:
    comp = load_json(computed_path(d, ed)) or {}
    od = out_dir(d, ed)
    t = _texts(comp, ed)
    tags = ", ".join(t.get("tags") or [])
    # 복사용 txt (한글 파일명 없이)
    for name, body in (("youtube_title.txt", t.get("title", "")), ("youtube_description.txt", t.get("description", "")),
                       ("youtube_tags.txt", tags), ("threads.txt", t.get("threads", "")), ("threads_reply.txt", t.get("threads_reply", ""))):
        (od / name).write_text(body, encoding="utf-8")

    def box(label: str, key: str, body: str, rows: int = 3, note: str = "") -> str:
        return (f'<section><div class="h"><h2>{label}</h2><button onclick="cp(\'{key}\',this)">복사</button>'
                f'{f"<small>{html.escape(note)}</small>" if note else ""}</div>'
                f'<textarea id="{key}" rows="{rows}" readonly>{html.escape(body)}</textarea></section>')

    rows = "".join(f"<tr><td>{s['id']}</td><td>{s.get('sec', '')}s</td><td>{html.escape(s['tts'])}</td></tr>" for s in comp.get("scenes", []))
    warn = "".join(f"<li>{html.escape(w)}</li>" for w in comp.get("warnings", [])) or "<li>없음</li>"
    src = ", ".join(f"{k}: {v}" for k, v in (comp.get("sources") or {}).items() if v)
    up_at = (comp.get("upload_times") or {}).get(ed, "")
    page = f"""<!doctype html><meta charset="utf-8"><title>{d} 업로드</title>
<style>
body{{font-family:Pretendard,'Noto Sans KR',sans-serif;background:#111;color:#eee;margin:0;padding:24px 28px;max-width:1500px}}
.g{{display:grid;grid-template-columns:1fr 380px;gap:32px;align-items:start}}
h1{{font-size:22px;margin:0 0 6px}} h1 small{{color:#8e8e93;font-weight:400;font-size:14px;margin-left:12px}}
h2{{font-size:15px;margin:0;color:#8e8e93;letter-spacing:.02em}} .h{{display:flex;align-items:center;gap:12px;margin:22px 0 8px}}
.h small{{color:#666;font-size:12px}}
button{{background:#FF5A4E;color:#fff;border:0;border-radius:8px;padding:6px 14px;font-size:13px;cursor:pointer}} button.ok{{background:#2fbf71}}
textarea{{width:100%;box-sizing:border-box;background:#1a1a1c;color:#f2f2f0;border:1px solid #2a2a2e;border-radius:10px;padding:12px;font:14px/1.55 inherit;resize:vertical}}
img,video{{width:100%;background:#161618;border-radius:12px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td{{padding:6px 8px;border-bottom:1px solid #2a2a2e;vertical-align:top}}
.w li{{color:#e2b24b}} details{{margin-top:22px}} summary{{cursor:pointer;color:#8e8e93;font-size:14px}}
.step{{background:#1a1a1c;border-radius:12px;padding:14px 18px;font-size:13px;color:#bbb;line-height:1.7;margin-top:18px}}
.step b{{color:#f2f2f0}}
</style>
<h1>{comp.get('brand', '')} · {comp.get('date_label', d)} {'국내장' if ed == 'kr' else '미국장'} 마감
<small>제작 {comp.get('generated_at', '')} · {comp.get('total_sec', '?')}초 · {comp.get('voice', '')}{' · 게시 ' + up_at if up_at else ''}</small></h1>
<div class="g"><div>
{box("유튜브 제목", "yt_title", t.get("title", ""), 1, f"{len(t.get('title', ''))}자 / 100")}
{box("유튜브 설명", "yt_desc", t.get("description", ""), 12)}
{box("유튜브 태그", "yt_tags", tags, 2, "쉼표로 구분 · '태그' 칸에 그대로 붙여넣기")}
{box("스레드 본문", "th_body", t.get("threads", ""), 12, f"{len(t.get('threads', ''))}자 / 500 · 카드 먼저, 영상 두 번째")}
{box("스레드 첫 답글", "th_reply", t.get("threads_reply", ""), 3, "{YT}를 올린 쇼츠 링크로 바꿔서")}
<div class="step"><b>올리는 순서</b><br>
① 유튜브: video.mp4 업로드 → 제목·설명·태그 붙여넣기 → 카테고리 <b>뉴스/정치</b> → 아동용 아님 → 합성 콘텐츠 <b>예</b> → 공개(또는 예약 {up_at})<br>
② 스레드: <b>card.png 먼저</b>, video.mp4 두 번째로 첨부 → 본문 붙여넣기 → 게시 → 첫 답글에 유튜브 링크</div>
<details><summary>대본 (장면·TTS)</summary><table>{rows}</table></details>
<details><summary>경고 · 출처</summary><ul class="w">{warn}</ul><small style="color:#8e8e93">{html.escape(src)}</small></details>
</div>
<div><h2>카드 1080×1350 — card.png</h2><img src="card.png" style="margin-top:8px">
<h2 style="margin-top:22px">영상 — video.mp4</h2><video src="video.mp4" controls style="margin-top:8px"></video>
<div class="step">파일 위치<br><b>{html.escape(str(od))}</b><br>txt로도 저장됨: youtube_title · youtube_description · youtube_tags · threads</div></div></div>
<script>
function cp(id,btn){{const el=document.getElementById(id);navigator.clipboard.writeText(el.value).then(()=>{{btn.textContent='복사됨';btn.classList.add('ok');setTimeout(()=>{{btn.textContent='복사';btn.classList.remove('ok')}},1500)}})}}
</script>"""
    (od / "review.html").write_text(page, encoding="utf-8")
    (ROOT / "metrics").mkdir(exist_ok=True)
    log(d, "review", f"{od / 'review.html'} (+ youtube_title/description/tags, threads .txt)")


if __name__ == "__main__":
    write(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d"), sys.argv[2] if len(sys.argv) > 2 else "kr")
