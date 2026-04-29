"""
FastAPI 앱 진입점.
- 라이프사이클: DB 풀 open/close
- 라우터 등록
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import (
    backtest,
    daily_reports,
    economy,
    industries,
    portfolio,
    regime,
    score_weights,
    skills,
    stocks,
    trades,
    weekly_reviews,
)
from server.config import settings
from server.db import close_pool, open_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    open_pool()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(
    title="stock-manager",
    version="0.1.0",
    description="Personal stock portfolio & analysis server",
    lifespan=lifespan,
)

_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# 운영: ALLOWED_ORIGINS env (콤마 분리) + Vercel preview 와일드카드
_extra_origins = [
    o.strip() for o in (settings.allowed_origins or "").split(",") if o.strip()
]
# Vercel preview 도메인: <project>-<hash>-<scope>.vercel.app
# settings.allowed_origin_regex 가 있으면 그걸 우선 사용 (예: ^https://stockclaude.*\.vercel\.app$)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_origin_regex=settings.allowed_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


app.include_router(stocks.router)
app.include_router(trades.router)
app.include_router(portfolio.router)
app.include_router(daily_reports.router)
app.include_router(industries.router)
app.include_router(economy.router)
app.include_router(regime.router)
app.include_router(score_weights.router)
app.include_router(backtest.router)
app.include_router(skills.router)
app.include_router(weekly_reviews.router)
