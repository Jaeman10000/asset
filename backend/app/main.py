"""
Vitality Nexus 로컬 백엔드 — FastAPI, localhost:8787.

Tauri 프론트엔드가 이 포트를 폴링한다. 외부에 노출하지 않는다
(스펙: "HTTP (localhost only)").
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .paths import data_path
from .routes.holdings import router as holdings_router
from .routes.portfolio import router as portfolio_router

# 프론트(WebView)에서 발생한 에러를 받아 파일로 남기는 진단 로그.
# WebView 화면이 멈춰도 원인을 파일에서 읽을 수 있게 하기 위함.
_CLIENTLOG = data_path("clientlog.txt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 자금 흐름 아카이브 — 테이블 준비 + 장 마감 후 자동 수집 스케줄러 기동.
    # (앱이 꺼져 있던 날짜도 다음 실행 때 자동 보충된다 — ka10059가 100일치를 주므로)
    from .services import flow_collector, flow_store

    flow_store.init_flow_db()
    # 디스크의 JSON이 원본 — 인덱스에 빠진 날짜가 있으면 채운다(백업 복원·수동 복사 대비)
    flow_store.reconcile()
    flow_collector.start_scheduler()
    yield


app = FastAPI(title="Vitality Nexus Backend", version="0.1.0", lifespan=lifespan)

# CORS: 우리 프론트(개발 Vite / 배포 Tauri WebView) origin만 화이트리스트.
#
# ⚠️ 이전엔 allow_origins=["*"] 였는데, 백엔드가 127.0.0.1:8787에 떠 있는 동안
# 사용자가 아무 웹사이트만 방문해도 그 페이지의 JS가 GET /portfolio/snapshot 으로
# 전체 보유종목·평단·평가액을 읽고 PUT /holdings 로 조작할 수 있었다(보안 리뷰 지적).
# 와일드카드는 크로스오리진 '읽기'를 허용하므로, 우리 앱 origin으로 좁힌다.
# (배포 WebView origin: Windows=http://tauri.localhost, macOS/Linux=tauri://localhost)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",  # 앱이 8787을 잡고 있을 때 쓰는 예비 dev 포트
    "http://127.0.0.1:5174",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
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
