"""데일리 Phase 2/5 (시장·포트 단위 분석) MCP 툴 contract 테스트.

대상:
- check_concentration  : 매매 집행 직전 25% 룰 + 예수금 검증.
- portfolio_correlation: Active 보유 종목 간 상관·effective_holdings.
- detect_portfolio_concentration: 25% 룰·섹터 쏠림 alert.
- rank_momentum        : 보유 종목 모멘텀 랭킹 + Z-score.
- detect_market_regime : 시장 레짐 (KOSPI ref_code 기반).

repos / analysis 의존을 monkeypatch 로 차단하고 MCP 래퍼의
응답 shape · 인자 전달 · 분기 동작만 검증한다.
DB 또는 외부 OHLCV fetch 가 살아있으면 contract 가 흐려지므로 모두 차단.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from server.mcp import server as mcp_module


# ---------------------------------------------------------------------------
# 공용 fixtures / helpers
# ---------------------------------------------------------------------------


def _ohlcv(n: int = 250, base: float = 100.0) -> pd.DataFrame:
    """한글 컬럼 합성 OHLCV. 길이 n, 가격 단조 증가."""
    close = np.linspace(base, base * 1.3, n)
    return pd.DataFrame(
        {
            "날짜": pd.date_range("2025-01-01", periods=n, freq="D"),
            "시가": close,
            "고가": close * 1.01,
            "저가": close * 0.99,
            "종가": close,
            "거래량": np.full(n, 1_000_000),
        }
    )


SAMPLE_KR_STOCK = {
    "code": "005930",
    "name": "삼성전자",
    "market": "kr",
    "currency": "KRW",
}

SAMPLE_US_STOCK = {
    "code": "AAPL",
    "name": "Apple",
    "market": "us",
    "currency": "USD",
}


# ===========================================================================
# check_concentration
# ===========================================================================


def _patch_compute_weights(monkeypatch, *, positions=(), cash=None, kr_total=None, us_total=None):
    """portfolio.compute_current_weights 결과 주입."""
    payload = {
        "positions": list(positions),
        "cash": dict(cash or {}),
        "kr_total_krw": Decimal(str(kr_total)) if kr_total is not None else Decimal(0),
        "us_total_usd": Decimal(str(us_total)) if us_total is not None else Decimal(0),
    }
    monkeypatch.setattr(
        mcp_module.portfolio, "compute_current_weights", lambda uid: payload
    )


def test_check_concentration_normal_returns_full_envelope(monkeypatch):
    """정상 호출 → {ok, new_weight_pct, market_total, cash_available, violations, notes} 6 키."""
    _patch_compute_weights(
        monkeypatch,
        positions=[],
        cash={"KRW": Decimal("10000000")},
        kr_total=10000000,
    )
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_KR_STOCK)

    out = mcp_module.check_concentration("005930", qty=10, price=78000)

    assert set(out.keys()) == {
        "ok", "new_weight_pct", "market_total", "cash_available", "violations", "notes",
    }
    assert out["ok"] is True
    assert out["violations"] == []
    assert isinstance(out["new_weight_pct"], float)
    assert isinstance(out["market_total"], float)
    assert isinstance(out["cash_available"], float)


def test_check_concentration_stock_not_found_returns_error_dict(monkeypatch):
    """종목 미존재 → {error: ...} 분기 (LLM 즉시 인지)."""
    _patch_compute_weights(monkeypatch, positions=[], cash={"KRW": Decimal("0")}, kr_total=0)
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: None)

    out = mcp_module.check_concentration("999999", qty=1, price=1000)

    assert "error" in out
    assert "999999" in out["error"]


def test_check_concentration_violation_25_pct_blocks_ok(monkeypatch):
    """25% 단일 상한 초과 신규 비중 → violations 추가 + ok=False."""
    # market_total = 1,000,000. 신규 매수 cost = 300,000 → 30% > 25%.
    _patch_compute_weights(
        monkeypatch,
        positions=[],
        cash={"KRW": Decimal("1000000")},
        kr_total=1000000,
    )
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_KR_STOCK)

    out = mcp_module.check_concentration("005930", qty=3, price=100000)

    assert out["ok"] is False
    assert len(out["violations"]) >= 1
    assert "25%" in out["violations"][0]
    assert out["new_weight_pct"] > 25


def test_check_concentration_existing_position_accumulates_weight(monkeypatch):
    """기존 cost_basis 와 신규 매수금 합산하여 비중 산정."""
    existing = {
        "code": "005930",
        "name": "삼성전자",
        "market": "kr",
        "currency": "KRW",
        "cost_basis": Decimal("200000"),
    }
    _patch_compute_weights(
        monkeypatch,
        positions=[existing],
        cash={"KRW": Decimal("800000")},
        kr_total=1000000,
    )
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_KR_STOCK)

    # 신규 cost = 100,000 → existing 200,000 + 100,000 = 300,000 / 1,000,000 = 30%
    out = mcp_module.check_concentration("005930", qty=1, price=100000)

    assert out["new_weight_pct"] == pytest.approx(30.0, abs=0.01)
    assert out["ok"] is False  # 25% 초과


def test_check_concentration_insufficient_cash_adds_note(monkeypatch):
    """예수금 부족 시 notes 에 메시지 추가 — 단 ok 자체는 violations 기준."""
    _patch_compute_weights(
        monkeypatch,
        positions=[],
        cash={"KRW": Decimal("50000")},  # 부족
        kr_total=1000000,
    )
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_KR_STOCK)

    out = mcp_module.check_concentration("005930", qty=1, price=100000)

    assert len(out["notes"]) >= 1
    assert "예수금" in out["notes"][0]


def test_check_concentration_us_stock_uses_us_total_and_usd_cash(monkeypatch):
    """US 종목 → market_total = us_total_usd, cash = USD 잔고."""
    _patch_compute_weights(
        monkeypatch,
        positions=[],
        cash={"KRW": Decimal("9999999"), "USD": Decimal("5000")},
        kr_total=9999999,
        us_total=5000,
    )
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_US_STOCK)

    out = mcp_module.check_concentration("AAPL", qty=1, price=200)

    assert out["market_total"] == 5000.0
    assert out["cash_available"] == 5000.0


def test_check_concentration_zero_market_total_returns_zero_pct(monkeypatch):
    """market_total 0 (포지션 없음 + 캐시 없음) → ZeroDivision 회피, new_weight_pct 0."""
    _patch_compute_weights(monkeypatch, positions=[], cash={}, kr_total=0)
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_KR_STOCK)

    out = mcp_module.check_concentration("005930", qty=1, price=100)

    assert out["new_weight_pct"] == 0.0


# ===========================================================================
# portfolio_correlation
# ===========================================================================


def _patch_active(monkeypatch, rows):
    monkeypatch.setattr(mcp_module.positions, "list_active", lambda uid: list(rows))


def test_portfolio_correlation_too_few_positions_returns_error(monkeypatch):
    """Active 종목 < 2 → {error: ...} (분석 의미 없음)."""
    _patch_active(monkeypatch, [])
    out = mcp_module.portfolio_correlation(days=60)
    assert "error" in out

    _patch_active(monkeypatch, [{"code": "005930", "market": "kr", "cost_basis": Decimal("100")}])
    out = mcp_module.portfolio_correlation(days=60)
    assert "error" in out


def test_portfolio_correlation_passes_days_through_and_calls_diversification(monkeypatch):
    """days 인자 + diversification_metrics 호출 + price_dict 종목수 일치 확인."""
    rows = [
        {"code": "005930", "market": "kr", "cost_basis": Decimal("100000")},
        {"code": "035720", "market": "kr", "cost_basis": Decimal("50000")},
    ]
    _patch_active(monkeypatch, rows)
    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", lambda code, days=400: _ohlcv(120))

    captured: dict = {}

    def fake_diversification(price_dict, weights=None):
        captured["codes"] = list(price_dict.keys())
        captured["weights"] = dict(weights or {})
        return {
            "avg_pairwise_corr": 0.5,
            "effective_holdings": 1.5,
            "most_correlated_pair": None,
            "diversification_score": 50,
            "codes": list(price_dict.keys()),
            "matrix": {},
        }

    monkeypatch.setattr(mcp_module, "diversification_metrics", fake_diversification)

    out = mcp_module.portfolio_correlation(days=90)

    assert set(captured["codes"]) == {"005930", "035720"}
    # weights 합계 = 1.0 (cost_basis 비례)
    assert captured["weights"]["005930"] == pytest.approx(100000 / 150000)
    assert captured["weights"]["035720"] == pytest.approx(50000 / 150000)
    assert "avg_pairwise_corr" in out
    assert "effective_holdings" in out


def test_portfolio_correlation_kr_and_us_both_use_fetch_ohlcv(monkeypatch):
    """#19 fix: KR/US 모두 _fetch_ohlcv 통일 호출. yfinance fallback (>100일 US) 가능."""
    rows = [
        {"code": "005930", "market": "kr", "cost_basis": Decimal("100")},
        {"code": "AAPL", "market": "us", "cost_basis": Decimal("100")},
    ]
    _patch_active(monkeypatch, rows)

    fetched_codes: list[str] = []

    def fake_fetch(code, days=400):
        fetched_codes.append(code)
        return _ohlcv(80)

    # 단일 _fetch_ohlcv 가 KR/US 둘 다 처리 (자동 분기). kis.fetch_us_daily 직접 호출 X.
    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", fake_fetch)
    # kis.fetch_us_daily 가 직접 호출되지 않음을 보장 — 호출되면 RuntimeError
    def _should_not_be_called(*a, **kw):
        raise RuntimeError("kis.fetch_us_daily 직접 호출 — _fetch_ohlcv 우회 (#19 위반)")
    monkeypatch.setattr(mcp_module.kis, "fetch_us_daily", _should_not_be_called)
    monkeypatch.setattr(
        mcp_module, "diversification_metrics", lambda pd_, weights=None: {"ok": True}
    )

    mcp_module.portfolio_correlation(days=60)

    # 두 종목 모두 _fetch_ohlcv 경로
    assert "005930" in fetched_codes
    assert "AAPL" in fetched_codes


def test_portfolio_correlation_skips_empty_dataframe(monkeypatch):
    """fetch 결과가 빈 df 면 해당 종목 skip — 예외 없이 진행."""
    rows = [
        {"code": "AAA", "market": "kr", "cost_basis": Decimal("100")},
        {"code": "BBB", "market": "kr", "cost_basis": Decimal("100")},
    ]
    _patch_active(monkeypatch, rows)

    def fake_fetch(code, days=400):
        # AAA 는 빈, BBB 는 정상
        return pd.DataFrame() if code == "AAA" else _ohlcv(60)

    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", fake_fetch)

    captured: dict = {}

    def fake_div(price_dict, weights=None):
        captured["codes"] = list(price_dict.keys())
        return {"ok": True}

    monkeypatch.setattr(mcp_module, "diversification_metrics", fake_div)

    mcp_module.portfolio_correlation(days=60)

    assert "AAA" not in captured["codes"]
    assert "BBB" in captured["codes"]


# ===========================================================================
# detect_portfolio_concentration
# ===========================================================================


def test_detect_portfolio_concentration_empty_positions_returns_zero_alerts(monkeypatch):
    """빈 포트 → alerts=[] + count=0. LLM 명확."""
    _patch_active(monkeypatch, [])
    monkeypatch.setattr(mcp_module.cash, "get_all", lambda uid: {})
    monkeypatch.setattr(
        mcp_module, "detect_concentration_alerts",
        lambda positions_data, cash_data, threshold_pct=25.0: [],
    )

    out = mcp_module.detect_portfolio_concentration()

    assert set(out.keys()) == {"alerts", "count"}
    assert out["alerts"] == []
    assert out["count"] == 0


def test_detect_portfolio_concentration_returns_alerts_with_count(monkeypatch):
    """alerts 가 있으면 count 가 길이와 일치."""
    _patch_active(monkeypatch, [
        {"code": "005930", "name": "삼성전자", "market": "kr", "cost_basis": Decimal("400000")}
    ])
    monkeypatch.setattr(mcp_module.cash, "get_all", lambda uid: {"KRW": Decimal("100000")})

    fake_alerts = [
        {"code": "005930", "name": "삼성전자", "weight_pct": 80.0,
         "threshold": 25.0, "severity": "critical"}
    ]
    monkeypatch.setattr(
        mcp_module, "detect_concentration_alerts",
        lambda positions_data, cash_data, threshold_pct=25.0: fake_alerts,
    )

    out = mcp_module.detect_portfolio_concentration()
    assert out["count"] == 1
    assert out["alerts"][0]["code"] == "005930"
    assert out["alerts"][0]["severity"] == "critical"


def test_detect_portfolio_concentration_passes_row_safe_dicts_to_analysis(monkeypatch):
    """positions 는 _row_safe 통과 (Decimal → float) 후 analysis 로 전달."""
    _patch_active(monkeypatch, [
        {"code": "005930", "name": "삼성전자", "market": "kr",
         "cost_basis": Decimal("100000"), "qty": Decimal("10")}
    ])
    monkeypatch.setattr(mcp_module.cash, "get_all", lambda uid: {"KRW": Decimal("50000")})

    captured: dict = {}

    def fake_alerts(positions_data, cash_data, threshold_pct=25.0):
        captured["positions"] = positions_data
        captured["cash"] = cash_data
        return []

    monkeypatch.setattr(mcp_module, "detect_concentration_alerts", fake_alerts)

    mcp_module.detect_portfolio_concentration()

    # _row_safe 로 Decimal → float 변환 확인
    assert isinstance(captured["positions"][0]["cost_basis"], float)
    assert captured["positions"][0]["cost_basis"] == 100000.0
    # cash 값도 float
    assert isinstance(captured["cash"]["KRW"], float)


# ===========================================================================
# rank_momentum
# ===========================================================================


def test_rank_momentum_empty_codes_returns_empty_list(monkeypatch):
    """codes=[] (또는 미지정 + active 0) → []. LLM 명확."""
    _patch_active(monkeypatch, [])
    out = mcp_module.rank_momentum(codes=[])
    assert out == []

    out2 = mcp_module.rank_momentum(codes=None, market="kr")
    assert out2 == []


def test_rank_momentum_codes_arg_drives_iteration(monkeypatch):
    """명시한 codes 만 iterate — active 의존 안 함."""
    _patch_active(monkeypatch, [{"code": "999999", "market": "kr"}])  # 무시되어야

    calls: list = []

    def fake_fetch(code, days=400):
        calls.append(code)
        return _ohlcv(120)

    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", fake_fetch)
    # short df 분기 — len < 60 미만이면 skip 되니, momentum_score 도 모킹
    monkeypatch.setattr(
        mcp_module, "momentum_score",
        lambda df: {"점수": 70.0, "등급": "A", "세부": {}},
    )
    # compute_all 은 그대로 통과시키되 빈 변환은 피하도록 인풋 그대로 반환
    import server.analysis.indicators as _ind
    monkeypatch.setattr(_ind, "compute_all", lambda df: df)

    out = mcp_module.rank_momentum(codes=["AAA", "BBB"], market="kr")

    assert sorted(calls) == ["AAA", "BBB"]
    # 결과 row 의 code 도 반영
    assert {r["code"] for r in out} == {"AAA", "BBB"}


def test_rank_momentum_zscore_and_rank_added_when_two_or_more_valid(monkeypatch):
    """valid 결과 ≥ 2 → 각 row 에 z_score + rank 추가, 점수 내림차순."""
    _patch_active(monkeypatch, [])

    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", lambda code, days=400: _ohlcv(120))

    import server.analysis.indicators as _ind
    monkeypatch.setattr(_ind, "compute_all", lambda df: df)

    score_map = {"AAA": 80.0, "BBB": 50.0, "CCC": 65.0}
    monkeypatch.setattr(
        mcp_module, "momentum_score",
        lambda df: {"점수": score_map.get(getattr(df, "_code", "AAA"), 50.0), "등급": "B", "세부": {}},
    )
    # df 에 code 메타를 못 박아두기 어려우니 호출 순서 기반 mock 으로 교체
    iters = iter(["AAA", "BBB", "CCC"])

    def fake_score(df):
        c = next(iters)
        return {"점수": score_map[c], "등급": "B", "세부": {}}

    monkeypatch.setattr(mcp_module, "momentum_score", fake_score)

    out = mcp_module.rank_momentum(codes=["AAA", "BBB", "CCC"], market="kr")

    valid = [r for r in out if "score" in r and isinstance(r["score"], (int, float))]
    assert len(valid) == 3
    # 모두 z_score 와 rank 부여
    for r in valid:
        assert "z_score" in r
        assert "rank" in r
    # 점수 내림차순 (rank 1 = 최고)
    ranked = sorted(valid, key=lambda r: r["rank"])
    assert ranked[0]["score"] == 80.0
    assert ranked[-1]["score"] == 50.0


def test_rank_momentum_short_ohlcv_skipped(monkeypatch):
    """OHLCV 60행 미만 → 결과에서 skip (시그니처상 60 미만이면 continue)."""
    _patch_active(monkeypatch, [])
    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", lambda code, days=400: _ohlcv(30))

    out = mcp_module.rank_momentum(codes=["AAA"], market="kr")

    # 결과 1개 미만 — z_score 분기 안 들어감, AAA 자체가 skip 되어 빈 리스트
    assert out == []


# ===========================================================================
# detect_market_regime
# ===========================================================================


def test_detect_market_regime_default_reference_is_kospi_proxy(monkeypatch):
    """기본 reference_code = '005930' (삼성전자, KOSPI 대용)."""
    captured: dict = {}

    def fake_fetch(code, days=400):
        captured["code"] = code
        captured["days"] = days
        return _ohlcv(300)

    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(
        mcp_module, "kospi_regime",
        lambda df: {"국면": "상승장", "모멘텀_가동": True, "통과_조건수": "3/4"},
    )

    out = mcp_module.detect_market_regime()

    assert captured["code"] == "005930"
    assert captured["days"] == 350
    assert out["reference"] == "005930"
    assert out["국면"] == "상승장"


def test_detect_market_regime_custom_reference_code(monkeypatch):
    """reference_code 인자가 fetch 에 그대로 전달."""
    captured: dict = {}

    def fake_fetch(code, days=400):
        captured["code"] = code
        return _ohlcv(300)

    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(
        mcp_module, "kospi_regime",
        lambda df: {"국면": "강한 상승장", "모멘텀_가동": True},
    )

    out = mcp_module.detect_market_regime(reference_code="069500")

    assert captured["code"] == "069500"
    assert out["reference"] == "069500"


def test_detect_market_regime_short_data_returns_error(monkeypatch):
    """OHLCV < 210 → {error: '데이터 부족', rows: N} 분기."""
    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", lambda code, days=400: _ohlcv(50))

    out = mcp_module.detect_market_regime()

    assert "error" in out
    assert "rows" in out
    assert out["rows"] == 50


def test_detect_market_regime_fetch_failure_returns_error(monkeypatch):
    """OHLCV fetch 예외 → {error: 'ref OHLCV 실패: ...'} (LLM 즉시 인지)."""
    def boom(code, days=400):
        raise RuntimeError("KIS down")

    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", boom)

    out = mcp_module.detect_market_regime()

    assert "error" in out
    assert "OHLCV" in out["error"] or "KIS" in out["error"]


def test_detect_market_regime_merges_kospi_regime_keys(monkeypatch):
    """kospi_regime 결과 키들이 응답에 spread 되어 reference 와 같은 레벨에 노출."""
    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", lambda code, days=400: _ohlcv(300))
    monkeypatch.setattr(
        mcp_module, "kospi_regime",
        lambda df: {"국면": "전환기", "모멘텀_가동": False, "체크": {"a": True}},
    )

    out = mcp_module.detect_market_regime()

    # reference + kospi_regime 키들이 동일 레벨
    assert "reference" in out
    assert "국면" in out
    assert "모멘텀_가동" in out
    assert "체크" in out
