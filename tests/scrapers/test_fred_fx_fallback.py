"""server.scrapers.fred.fetch_fx_rate fallback 체인 테스트.

GitHub Issue #22 — FRED 단일 의존 → 1회 에러로 BLOCKING 위반 위험.
신정책: FRED 실패 시 yfinance KRW=X fallback.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from server.scrapers import fred as fred_module


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트마다 _FX_CACHE 초기화 (캐시 hit 가 fallback 분기 가려짐 방지)."""
    fred_module._FX_CACHE.clear()
    yield
    fred_module._FX_CACHE.clear()


# ---------------------------------------------------------------------------
# 1차 FRED 정상 — fallback 미발동
# ---------------------------------------------------------------------------


def test_fred_success_returns_fred_source():
    fred_response = {
        "pair": "DEXKOUS",
        "환율": 1380.5,
        "기준일": "2026-05-04",
        "source": "FRED",
    }
    with patch.object(fred_module, "_try_fred_fx", return_value=fred_response):
        with patch.object(fred_module, "_try_yfinance_fx_krw_usd") as yf_mock:
            out = fred_module.fetch_fx_rate("DEXKOUS")
            assert out["환율"] == 1380.5
            assert out["source"] == "FRED"
            yf_mock.assert_not_called()  # fallback 미발동


# ---------------------------------------------------------------------------
# 1차 FRED 실패 → 2차 yfinance fallback
# ---------------------------------------------------------------------------


def test_fred_fail_dexkous_falls_back_to_yfinance():
    fred_fail = {"pair": "DEXKOUS", "환율": None, "source": "FRED", "error": "Internal Server Error"}
    yf_success = {
        "pair": "DEXKOUS",
        "환율": 1379.0,
        "기준일": "2026-05-04",
        "source": "yfinance",
    }
    with patch.object(fred_module, "_try_fred_fx", return_value=fred_fail):
        with patch.object(fred_module, "_try_yfinance_fx_krw_usd", return_value=yf_success):
            out = fred_module.fetch_fx_rate("DEXKOUS")
            assert out["환율"] == 1379.0
            assert out["source"] == "yfinance"  # 2차 source 명시


def test_fred_and_yfinance_both_fail_returns_none_with_metadata():
    fred_fail = {"pair": "DEXKOUS", "환율": None, "source": "FRED", "error": "FRED down"}
    yf_fail = {"pair": "DEXKOUS", "환율": None, "source": "yfinance", "error": "yfinance down"}
    with patch.object(fred_module, "_try_fred_fx", return_value=fred_fail):
        with patch.object(fred_module, "_try_yfinance_fx_krw_usd", return_value=yf_fail):
            out = fred_module.fetch_fx_rate("DEXKOUS")
            assert out["환율"] is None
            assert "error" in out
            assert out["fallback_attempted"] == ["FRED", "yfinance"]


def test_non_dexkous_pair_does_not_fallback_to_yfinance():
    """yfinance KRW=X 는 DEXKOUS 만 매핑 — 다른 pair 는 yfinance 시도 안 함."""
    fred_fail = {"pair": "DEXJPUS", "환율": None, "source": "FRED", "error": "down"}
    with patch.object(fred_module, "_try_fred_fx", return_value=fred_fail):
        with patch.object(fred_module, "_try_yfinance_fx_krw_usd") as yf_mock:
            out = fred_module.fetch_fx_rate("DEXJPUS")
            assert out["환율"] is None
            assert out["fallback_attempted"] == ["FRED"]  # FRED 만 시도
            yf_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 캐시 동작 (1일 TTL)
# ---------------------------------------------------------------------------


def test_cache_hit_skips_both_calls():
    """동일 cache_key 재호출 시 FRED·yfinance 둘 다 미발동."""
    cached = {"pair": "DEXKOUS", "환율": 1380.5, "source": "FRED", "기준일": "2026-05-04"}
    fred_module._FX_CACHE["DEXKOUS:latest"] = (datetime.now().timestamp(), cached)

    with patch.object(fred_module, "_try_fred_fx") as fred_mock:
        with patch.object(fred_module, "_try_yfinance_fx_krw_usd") as yf_mock:
            out = fred_module.fetch_fx_rate("DEXKOUS")
            assert out == cached
            fred_mock.assert_not_called()
            yf_mock.assert_not_called()


# ---------------------------------------------------------------------------
# _try_yfinance_fx_krw_usd 단독 (yfinance_client 모킹)
# ---------------------------------------------------------------------------


def test_yfinance_fx_returns_close_with_korean_columns():
    """yfinance_client.fetch_ohlcv 가 한글 컬럼 DataFrame 반환 → 종가 추출."""
    fake_df = pd.DataFrame({
        "날짜": [pd.Timestamp("2026-05-03"), pd.Timestamp("2026-05-04")],
        "시가": [1378.0, 1379.0],
        "고가": [1382.0, 1381.0],
        "저가": [1376.0, 1377.0],
        "종가": [1380.0, 1379.5],
        "거래량": [0, 0],
    })
    with patch("server.scrapers.yfinance_client.fetch_ohlcv", return_value=fake_df):
        out = fred_module._try_yfinance_fx_krw_usd(date=None)
        assert out["환율"] == 1379.5  # 마지막 종가
        assert out["source"] == "yfinance"
        assert out["기준일"] == "2026-05-04"


def test_yfinance_fx_empty_response_returns_none():
    with patch("server.scrapers.yfinance_client.fetch_ohlcv", return_value=pd.DataFrame()):
        out = fred_module._try_yfinance_fx_krw_usd(date=None)
        assert out["환율"] is None
        assert out["source"] == "yfinance"


def test_yfinance_fx_exception_handled():
    """yfinance 예외 시 None + error 반환 (raise X)."""
    with patch("server.scrapers.yfinance_client.fetch_ohlcv", side_effect=Exception("net err")):
        out = fred_module._try_yfinance_fx_krw_usd(date=None)
        assert out["환율"] is None
        assert "net err" in out["error"]
