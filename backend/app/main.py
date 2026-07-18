"""
Vitality Nexus 로컬 백엔드 — FastAPI, localhost:8787.

Tauri 프론트엔드가 이 포트를 폴링한다. 외부에 노출하지 않는다
(스펙: "HTTP (localhost only)").
"""
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes.holdings import router as holdings_router
from .routes.portfolio import router as portfolio_router

# 프론트(WebView)에서 발생한 에러를 받아 파일로 남기는 진단 로그.
# WebView 화면이 멈춰도 원인을 파일에서 읽을 수 있게 하기 위함.
_CLIENTLOG = Path(__file__).resolve().parent.parent / "data" / "clientlog.txt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Vitality Nexus Backend", version="0.1.0", lifespan=lifespan)

# CORS: 개발(Vite localhost:5173)과 배포(Tauri WebView) origin을 모두 허용.
# 배포 앱의 WebView origin은 플랫폼마다 다르다:
#   Windows: http://tauri.localhost, macOS/Linux: tauri://localhost
# 이 백엔드는 127.0.0.1에만 바인딩되어 외부 네트워크에 노출되지 않고
# 쿠키/자격증명도 쓰지 않으므로, origin 전체 허용(*)이 안전하다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)
app.include_router(holdings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/clientlog")
async def clientlog(request: Request) -> dict[str, str]:
    """프론트(WebView) 진단 로그 수신 — sendBeacon으로 오는 텍스트를 파일에 append."""
    try:
        body = (await request.body()).decode("utf-8", errors="replace")
        _CLIENTLOG.parent.mkdir(parents=True, exist_ok=True)
        with _CLIENTLOG.open("a", encoding="utf-8") as f:
            f.write(f"[{int(time.time())}] {body}\n")
    except Exception:
        pass
    return {"ok": "1"}
