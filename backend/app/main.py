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

# Tauri/Vite 프론트엔드(localhost:5173, 개발 시) origin만 허용.
# 프로덕션 Tauri 빌드는 tauri:// origin이라 별도 처리 필요 (Week 2에서 조정).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)
app.include_router(holdings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
