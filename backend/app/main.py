"""
Vitality Nexus 로컬 백엔드 — FastAPI, localhost:8787.

Tauri 프론트엔드가 이 포트를 폴링한다. 외부에 노출하지 않는다
(스펙: "HTTP (localhost only)").
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes.holdings import router as holdings_router
from .routes.portfolio import router as portfolio_router


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
