"""테스트 공통 픽스처.

analysis/ 등 순수함수 테스트에서 재사용하는 합성 OHLCV DataFrame 생성기.
한글 컬럼 컨벤션(`날짜/시가/고가/저가/종가/거래량`)을 따른다.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest


def _trading_dates(n: int, end: date | None = None) -> pd.DatetimeIndex:
    """KST 거래일 가정의 단순 일자 시퀀스 (주말 무시 — 테스트용 합성)."""
    end = end or date(2026, 5, 1)
    return pd.DatetimeIndex([end - timedelta(days=n - 1 - i) for i in range(n)])


def _ohlcv_frame(close: np.ndarray, high_mult: float = 1.01, low_mult: float = 0.99) -> pd.DataFrame:
    """종가 시퀀스로 한글 컬럼 OHLCV DataFrame 합성."""
    n = len(close)
    return pd.DataFrame(
        {
            "날짜": _trading_dates(n),
            "시가": close,
            "고가": close * high_mult,
            "저가": close * low_mult,
            "종가": close,
            "거래량": np.full(n, 1_000_000),
        }
    )


@pytest.fixture
def constant_ohlcv() -> pd.DataFrame:
    """가격 변동 0인 60행 OHLCV — 변동성 0, 베타 정의 안됨, 낙폭 0."""
    return _ohlcv_frame(np.full(60, 100.0))


@pytest.fixture
def drawdown_ohlcv() -> pd.DataFrame:
    """알려진 peak/trough를 가진 5행 OHLCV (peak=110, trough=90, max_dd=-18.18%)."""
    return _ohlcv_frame(np.array([100.0, 110.0, 95.0, 90.0, 95.0]))


@pytest.fixture
def linear_ramp_ohlcv() -> pd.DataFrame:
    """252영업일 동안 100→130 선형 상승 (12개월 +30%) — dual_momentum용."""
    close = np.linspace(100.0, 130.0, 252)
    return _ohlcv_frame(close)


@pytest.fixture
def benchmark_flat_ohlcv() -> pd.DataFrame:
    """252영업일 동안 100→110 선형 상승 (벤치 +10%) — 비교 기준."""
    close = np.linspace(100.0, 110.0, 252)
    return _ohlcv_frame(close)


@pytest.fixture
def benchmark_decline_ohlcv() -> pd.DataFrame:
    """252영업일 동안 100→102 약상승 (벤치 +2%, 무위험 3.5% 미만) — 절대만 양수 케이스용."""
    close = np.linspace(100.0, 102.0, 252)
    return _ohlcv_frame(close)


@pytest.fixture
def declining_ohlcv() -> pd.DataFrame:
    """252영업일 동안 100→90 선형 하락 (-10%) — 절대 모멘텀 음수 케이스."""
    close = np.linspace(100.0, 90.0, 252)
    return _ohlcv_frame(close)


@pytest.fixture
def beta_pair_ohlcv() -> tuple[pd.DataFrame, pd.DataFrame]:
    """벤치 = 100~199 선형, 종목 = 벤치 일간수익률을 정확히 2배로 따라감 → beta≈2.0.

    선형 시퀀스의 일간 수익률은 매일 다르지만, 비율이 일정하면 cov/var = 2.
    """
    bench_close = np.linspace(100.0, 199.0, 60)
    bench_returns = np.diff(bench_close) / bench_close[:-1]
    stock_close = np.empty(60)
    stock_close[0] = 100.0
    for i, r in enumerate(bench_returns):
        stock_close[i + 1] = stock_close[i] * (1 + 2 * r)
    return _ohlcv_frame(stock_close), _ohlcv_frame(bench_close)
