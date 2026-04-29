"""
Yahoo Finance (yfinance) 어댑터 — US 종목 OHLCV + 시총 batch fetch.

Finnhub 무료 plan 의 /stock/candle 미제공 한계를 보완. yfinance 는 비공식 API 지만
rate limit 관대 + 일괄 fetch 가능.

KR 의 naver.fetch_daily 와 동등한 역할. 컬럼명을 한글로 정규화해서 indicators.compute_all
호환성 유지.
"""
from __future__ import annotations

import time
from typing import Any

import pandas as pd
import yfinance as yf


_LAST_CALL: float = 0.0
_MIN_INTERVAL = 0.05  # yfinance 자체 throttle. 보수적.


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.time() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.time()


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance OHLCV → KR 한글 컬럼 (naver.fetch_daily 와 동일 스키마)."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    rename = {
        "Open": "시가", "High": "고가", "Low": "저가",
        "Close": "종가", "Volume": "거래량",
    }
    out = out.rename(columns=rename)
    out = out.reset_index().rename(columns={"Date": "날짜", "Datetime": "날짜"})
    keep = [c for c in ["날짜", "시가", "고가", "저가", "종가", "거래량"] if c in out.columns]
    return out[keep]


def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    단일 ticker OHLCV.

    period: '1y' / '6mo' / '3mo' / '1mo' / '5d' (yfinance 표준).
    interval: '1d' / '1h' / '1wk'.

    반환: DataFrame [날짜, 시가, 고가, 저가, 종가, 거래량] (KR 호환).
    """
    _throttle()
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval, auto_adjust=False)
        return _normalize_ohlcv(df)
    except Exception:
        return pd.DataFrame()


def fetch_ohlcv_batch(
    tickers: list[str], period: str = "1y", interval: str = "1d"
) -> dict[str, pd.DataFrame]:
    """
    여러 ticker OHLCV 일괄 fetch (yfinance 의 download() 사용 — 단일 HTTP request).

    반환: {ticker: DataFrame} — 실패한 ticker 는 빈 DataFrame.
    """
    if not tickers:
        return {}
    _throttle()
    try:
        # yfinance multi-ticker download → MultiIndex columns (level 0 = field, level 1 = ticker)
        # group_by="ticker" 로 (ticker, field) 순서로 변경.
        raw = yf.download(
            tickers=" ".join(tickers),
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception:
        return {t: pd.DataFrame() for t in tickers}

    out: dict[str, pd.DataFrame] = {}
    if len(tickers) == 1:
        out[tickers[0]] = _normalize_ohlcv(raw)
        return out

    for t in tickers:
        try:
            sub = raw[t]
            out[t] = _normalize_ohlcv(sub)
        except Exception:
            out[t] = pd.DataFrame()
    return out


def fetch_market_cap(ticker: str) -> float | None:
    """
    단일 ticker 시총 (USD).

    yfinance fast_info 는 attr 접근 시 snake_case (`market_cap`),
    dict 접근 시 camelCase (`marketCap`) 라 attr 접근으로 통일.
    """
    _throttle()
    try:
        info = yf.Ticker(ticker).fast_info
        cap = getattr(info, "market_cap", None)
        return float(cap) if cap else None
    except Exception:
        return None


def fetch_market_cap_batch(tickers: list[str]) -> dict[str, float | None]:
    """
    여러 ticker 시총 일괄 fetch.

    yfinance 의 fast_info 는 ticker 별 호출이지만 lazy + 캐시 적용. 100~200 종목 fetch ~30~60초.
    """
    out: dict[str, float | None] = {}
    for t in tickers:
        out[t] = fetch_market_cap(t)
    return out
