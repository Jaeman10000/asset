"""플랫폼 인증 1회 설정 — python auth.py youtube | tiktok | threads | status
비밀값(클라이언트 ID/시크릿·토큰)은 전부 Windows 자격 증명 관리자(app.keychain)에만 저장한다.
JJ가 직접 실행하고 브라우저에서 동의 버튼을 누른다. 이 파일은 코드를 받아 토큰으로 바꾸는 일만 한다.

준비물(각 플랫폼 개발자 콘솔에서 JJ가 만든다 — README '게시 자동화' 절):
  youtube : Google Cloud OAuth 클라이언트(데스크톱 앱) → client_id / client_secret
  tiktok  : TikTok for Developers 앱(Content Posting API, Login Kit) → client_key / client_secret, Redirect URI 등록
  threads : Meta 앱(Threads API) → app_id / app_secret, Redirect URI 등록
"""
from __future__ import annotations

import http.server
import json
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta

import httpx

from _common import DATA, log  # noqa: F401
from app.keychain import get_api_key, set_api_key  # noqa: E402

AUTH_DIR = DATA / "auth"
AUTH_DIR.mkdir(parents=True, exist_ok=True)


def _ask(prompt: str) -> str:
    return input(prompt).strip()


def _need(exchange: str, key: str, label: str) -> str:
    v = get_api_key(exchange, key)
    if not v:
        v = _ask(f"{label} 붙여넣고 엔터: ")
        set_api_key(exchange, key, v)
    return v


def _meta(name: str, **kw) -> None:
    p = AUTH_DIR / f"{name}.json"
    cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    cur.update(kw)
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")


# ── YouTube (Google OAuth 2.0, 데스크톱 앱 + 루프백) ──
YT_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def youtube() -> None:
    cid = _need("youtube", "client_id", "Google OAuth 클라이언트 ID")
    csec = _need("youtube", "client_secret", "Google OAuth 클라이언트 시크릿")
    port = 8765
    redirect = f"http://localhost:{port}/"
    state = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": YT_SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state})
    code_box: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and q.get("code"):
                code_box["code"] = q["code"][0]
                body = "<h2>밤낮장 — YouTube 연결 완료. 이 창을 닫으세요.</h2>"
            else:
                body = "<h2>코드를 받지 못했습니다. 터미널을 확인하세요.</h2>"
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, *a):  # 조용히
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("브라우저가 열립니다. Google 계정(유튜브 채널 소유 계정)으로 로그인하고 허용을 누르세요.\n" + url, flush=True)
    (AUTH_DIR / "youtube_auth_url.txt").write_text(url, encoding="utf-8")
    webbrowser.open(url)
    for _ in range(1800):          # 최대 15분 대기
        if code_box:
            break
        time.sleep(0.5)
    srv.shutdown()
    code = code_box.get("code")
    if not code:
        try:
            code = _ask("브라우저가 안 열리면 주소창의 code= 값을 붙여넣으세요: ")
        except EOFError:
            raise SystemExit("15분 안에 허용이 눌리지 않았습니다. 다시 실행하세요.")
    r = httpx.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": cid, "client_secret": csec,
                                                               "redirect_uri": redirect, "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    tok = r.json()
    if not tok.get("refresh_token"):
        raise SystemExit("refresh_token이 없습니다. Google 계정 > 보안 > 서드파티 액세스에서 이 앱을 제거하고 다시 실행하세요.")
    set_api_key("youtube", "refresh_token", tok["refresh_token"])
    ch = httpx.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                   headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30).json()
    item = (ch.get("items") or [{}])[0]
    _meta("youtube", channel_id=item.get("id"), channel_title=(item.get("snippet") or {}).get("title"), connected_at=datetime.now().isoformat(timespec="seconds"))
    print(f"연결 완료: 채널 '{(item.get('snippet') or {}).get('title')}' ({item.get('id')})")


# ── TikTok (Login Kit v2, 수동 리다이렉트 붙여넣기) ──
TT_SCOPES = "user.info.basic,video.publish,video.upload"


def tiktok() -> None:
    ck = _need("tiktok", "client_key", "TikTok Client Key")
    csec = _need("tiktok", "client_secret", "TikTok Client Secret")
    redirect = get_api_key("tiktok", "redirect_uri") or _ask("TikTok 앱에 등록한 Redirect URI(https://…) 붙여넣기: ")
    set_api_key("tiktok", "redirect_uri", redirect)
    state = secrets.token_urlsafe(12)
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": ck, "scope": TT_SCOPES, "response_type": "code", "redirect_uri": redirect, "state": state})
    print("브라우저에서 TikTok에 로그인하고 허용을 누르면 Redirect URI로 이동합니다. 그 주소창 전체를 복사해 붙여넣으세요.\n" + url)
    webbrowser.open(url)
    back = _ask("리다이렉트된 주소 전체: ")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
    code = q.get("code", [""])[0]
    if not code:
        raise SystemExit("code가 없습니다.")
    r = httpx.post("https://open.tiktokapis.com/v2/oauth/token/", data={"client_key": ck, "client_secret": csec, "code": code,
                                                                       "grant_type": "authorization_code", "redirect_uri": redirect},
                   headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    tok = r.json()
    if "access_token" not in tok:
        raise SystemExit(f"토큰 실패: {tok}")
    _save_tiktok_token(tok)
    print(f"연결 완료: open_id {tok.get('open_id')} (access 24h, refresh 365d — 자동 갱신)")


def _save_tiktok_token(tok: dict) -> None:
    now = datetime.now()
    set_api_key("tiktok", "access_token", tok["access_token"])
    if tok.get("refresh_token"):
        set_api_key("tiktok", "refresh_token", tok["refresh_token"])
    _meta("tiktok", open_id=tok.get("open_id"), access_expires=(now + timedelta(seconds=int(tok.get("expires_in", 86400)) - 300)).isoformat(timespec="seconds"),
          refresh_expires=(now + timedelta(seconds=int(tok.get("refresh_expires_in", 31536000)))).isoformat(timespec="seconds"),
          connected_at=now.isoformat(timespec="seconds"))


def tiktok_access_token() -> str:
    """유효한 access_token(만료 전이면 그대로, 아니면 refresh)."""
    meta = json.loads((AUTH_DIR / "tiktok.json").read_text(encoding="utf-8")) if (AUTH_DIR / "tiktok.json").exists() else {}
    if meta.get("access_expires") and datetime.fromisoformat(meta["access_expires"]) > datetime.now():
        return get_api_key("tiktok", "access_token") or ""
    r = httpx.post("https://open.tiktokapis.com/v2/oauth/token/", data={"client_key": get_api_key("tiktok", "client_key"), "client_secret": get_api_key("tiktok", "client_secret"),
                                                                       "grant_type": "refresh_token", "refresh_token": get_api_key("tiktok", "refresh_token")},
                   headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    tok = r.json()
    if "access_token" not in tok:
        raise RuntimeError(f"TikTok 토큰 갱신 실패: {tok}")
    _save_tiktok_token(tok)
    return tok["access_token"]


# ── Threads (Meta, 장기 토큰 60일 + 자동 갱신) ──
TH_SCOPES = "threads_basic,threads_content_publish"


def threads() -> None:
    aid = _need("threads", "app_id", "Threads 앱 ID")
    asec = _need("threads", "app_secret", "Threads 앱 시크릿")
    redirect = get_api_key("threads", "redirect_uri") or _ask("Meta 앱에 등록한 Redirect URI(https://…) 붙여넣기: ")
    set_api_key("threads", "redirect_uri", redirect)
    url = "https://threads.net/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": aid, "redirect_uri": redirect, "scope": TH_SCOPES, "response_type": "code", "state": secrets.token_urlsafe(8)})
    print("브라우저에서 Threads 계정으로 허용을 누르면 Redirect URI로 이동합니다. 그 주소창 전체를 복사해 붙여넣으세요.\n" + url)
    webbrowser.open(url)
    back = _ask("리다이렉트된 주소 전체: ")
    code = urllib.parse.parse_qs(urllib.parse.urlparse(back).query).get("code", [""])[0].split("#")[0]
    if not code:
        raise SystemExit("code가 없습니다.")
    r = httpx.post("https://graph.threads.net/oauth/access_token", data={"client_id": aid, "client_secret": asec, "grant_type": "authorization_code",
                                                                        "redirect_uri": redirect, "code": code}, timeout=30)
    short = r.json()
    if "access_token" not in short:
        raise SystemExit(f"단기 토큰 실패: {short}")
    r = httpx.get("https://graph.threads.net/access_token", params={"grant_type": "th_exchange_token", "client_secret": asec, "access_token": short["access_token"]}, timeout=30)
    long_ = r.json()
    if "access_token" not in long_:
        raise SystemExit(f"장기 토큰 실패: {long_}")
    _save_threads_token(long_, user_id=str(short.get("user_id")))
    me = httpx.get("https://graph.threads.net/v1.0/me", params={"fields": "id,username", "access_token": long_["access_token"]}, timeout=30).json()
    _meta("threads", username=me.get("username"))
    print(f"연결 완료: @{me.get('username')} (토큰 60일, 실행 때마다 자동 갱신)")


def _save_threads_token(tok: dict, user_id: str | None = None) -> None:
    set_api_key("threads", "access_token", tok["access_token"])
    kw = {"access_expires": (datetime.now() + timedelta(seconds=int(tok.get("expires_in", 5184000)))).isoformat(timespec="seconds")}
    if user_id:
        kw["user_id"] = user_id
    _meta("threads", **kw)


def threads_access_token() -> str:
    """장기 토큰. 만료 7일 전부터 갱신(24시간 지난 토큰만 갱신 가능)."""
    meta = json.loads((AUTH_DIR / "threads.json").read_text(encoding="utf-8")) if (AUTH_DIR / "threads.json").exists() else {}
    tok = get_api_key("threads", "access_token") or ""
    exp = meta.get("access_expires")
    if tok and exp and datetime.fromisoformat(exp) - datetime.now() < timedelta(days=7):
        r = httpx.get("https://graph.threads.net/refresh_access_token", params={"grant_type": "th_refresh_token", "access_token": tok}, timeout=30).json()
        if "access_token" in r:
            _save_threads_token(r)
            tok = r["access_token"]
    return tok


def status() -> None:
    for name, keys in (("youtube", ("client_id", "refresh_token")), ("tiktok", ("client_key", "refresh_token")), ("threads", ("app_id", "access_token"))):
        ok = all(get_api_key(name, k) for k in keys)
        p = AUTH_DIR / f"{name}.json"
        meta = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        print(f"{name:8s} {'연결됨' if ok else '미연결'}  {json.dumps({k: v for k, v in meta.items() if 'expires' in k or k in ('channel_title', 'username', 'open_id')}, ensure_ascii=False)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"youtube": youtube, "tiktok": tiktok, "threads": threads, "status": status}[cmd]()
