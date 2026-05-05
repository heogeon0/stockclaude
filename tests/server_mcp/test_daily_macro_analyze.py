"""데일리 매크로 + analyze_position MCP 툴 contract 테스트.

대상 4개 (server.mcp.server):
  1. get_macro_indicators_us       — FRED API 래퍼 (default 10종 series)
  2. get_macro_indicators_kr       — ECOS API 래퍼 (default 8종 stat_code)
  3. get_economic_calendar         — Finnhub 경제 캘린더 (DataFrame → list[dict])
  4. analyze_position              — ⚠️ 데일리 Phase 3 핵심. 12 카테고리 통합 1콜.

핵심 invariant:
  - macro 함수는 외부 scraper 모킹으로 시그니처/default·인자 전달/_json_safe 정규화 검증.
  - analyze_position 은 의존성이 깊으므로 각 source 를 얕게 모킹 + 12 카테고리 키 + 재제안 금지 가드만.

라운드 2026-05 폐기 invariant (재제안 금지):
  analyze_position 응답에 `scoring`, `cell`, `is_stale` 키가 **없어야** 한다.
  (주석: per-stock-analysis.md / server/mcp/CLAUDE.md §합성 점수 회피)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd
import pytest

from server.mcp import server as mcp_module


# =============================================================================
# get_macro_indicators_us  (FRED)
# =============================================================================


def test_get_macro_indicators_us_empty_response_returns_dict(monkeypatch):
    """외부 API 빈 응답 → dict shape 유지 (LLM 이 None/error 로 오인 X)."""
    import server.scrapers.fred as fred_mod
    monkeypatch.setattr(fred_mod, "fetch_macro_indicators", lambda series_ids=None: {})
    out = mcp_module.get_macro_indicators_us()
    assert isinstance(out, dict)
    assert out == {}


def test_get_macro_indicators_us_passes_default_when_none(monkeypatch):
    """series_ids=None 호출 시 scraper 에 그대로 None 전달 (scraper 가 default 적용)."""
    captured: dict = {}

    def fake(series_ids=None):
        captured["series_ids"] = series_ids
        return {}

    import server.scrapers.fred as fred_mod
    monkeypatch.setattr(fred_mod, "fetch_macro_indicators", fake)
    mcp_module.get_macro_indicators_us()
    assert captured["series_ids"] is None


def test_get_macro_indicators_us_passes_explicit_series(monkeypatch):
    """명시 series_ids 가 scraper 에 그대로 전달."""
    captured: dict = {}

    def fake(series_ids=None):
        captured["series_ids"] = series_ids
        return {}

    import server.scrapers.fred as fred_mod
    monkeypatch.setattr(fred_mod, "fetch_macro_indicators", fake)
    mcp_module.get_macro_indicators_us(series_ids=["DFF", "VIXCLS"])
    assert captured["series_ids"] == ["DFF", "VIXCLS"]


def test_get_macro_indicators_us_filters_to_three_keys(monkeypatch):
    """raw scraper 가 series 등 추가 키를 줘도 응답은 최신값/날짜/YoY변화 3 키만."""
    raw = {
        "DFF": {
            "최신값": 5.33,
            "날짜": pd.Timestamp("2026-05-01"),
            "YoY변화": -0.42,
            # MCP 래퍼가 제외해야 하는 raw pd.Series 추가 키
            "series": pd.Series([5.0, 5.33], index=pd.to_datetime(["2026-04-01", "2026-05-01"])),
        },
    }
    import server.scrapers.fred as fred_mod
    monkeypatch.setattr(fred_mod, "fetch_macro_indicators", lambda series_ids=None: raw)
    out = mcp_module.get_macro_indicators_us(series_ids=["DFF"])
    assert set(out["DFF"].keys()) == {"최신값", "날짜", "YoY변화"}
    # _json_safe 거쳐 Timestamp → isoformat 문자열로 정규화
    assert isinstance(out["DFF"]["날짜"], str)
    assert out["DFF"]["최신값"] == 5.33
    assert out["DFF"]["YoY변화"] == -0.42


def test_get_macro_indicators_us_propagates_error_per_series(monkeypatch):
    """series 단위 error 는 응답에서 동일 키로 전달 — LLM 이 부분 실패 인지 가능."""
    raw = {
        "DFF": {"최신값": 5.33, "날짜": pd.Timestamp("2026-05-01"), "YoY변화": None},
        "BAD": {"error": "no data"},
    }
    import server.scrapers.fred as fred_mod
    monkeypatch.setattr(fred_mod, "fetch_macro_indicators", lambda series_ids=None: raw)
    out = mcp_module.get_macro_indicators_us()
    assert out["BAD"] == {"error": "no data"}
    assert "최신값" in out["DFF"]


# =============================================================================
# get_macro_indicators_kr  (ECOS)
# =============================================================================


def test_get_macro_indicators_kr_empty_response_returns_dict(monkeypatch):
    import server.scrapers.ecos as ecos_mod
    monkeypatch.setattr(ecos_mod, "fetch_kr_macro_indicators", lambda stat_codes=None: {})
    out = mcp_module.get_macro_indicators_kr()
    assert isinstance(out, dict)
    assert out == {}


def test_get_macro_indicators_kr_passes_default_when_none(monkeypatch):
    captured: dict = {}

    def fake(stat_codes=None):
        captured["stat_codes"] = stat_codes
        return {}

    import server.scrapers.ecos as ecos_mod
    monkeypatch.setattr(ecos_mod, "fetch_kr_macro_indicators", fake)
    mcp_module.get_macro_indicators_kr()
    assert captured["stat_codes"] is None


def test_get_macro_indicators_kr_passes_explicit_codes(monkeypatch):
    captured: dict = {}

    def fake(stat_codes=None):
        captured["stat_codes"] = stat_codes
        return {}

    import server.scrapers.ecos as ecos_mod
    monkeypatch.setattr(ecos_mod, "fetch_kr_macro_indicators", fake)
    mcp_module.get_macro_indicators_kr(stat_codes=["722Y001"])
    assert captured["stat_codes"] == ["722Y001"]


def test_get_macro_indicators_kr_passthrough_shape(monkeypatch):
    """ECOS scraper 결과 shape 가 _json_safe 만 거쳐 그대로 반환."""
    raw = {
        "722Y001": {
            "이름": "한국은행 기준금리",
            "최신값": 3.25,
            "단위": "%",
            "날짜": "202605",
            "YoY변화": -0.25,
            "cycle": "M",
            "출처": "ECOS",
        },
    }
    import server.scrapers.ecos as ecos_mod
    monkeypatch.setattr(ecos_mod, "fetch_kr_macro_indicators", lambda stat_codes=None: raw)
    out = mcp_module.get_macro_indicators_kr()
    assert out["722Y001"]["이름"] == "한국은행 기준금리"
    assert out["722Y001"]["출처"] == "ECOS"
    assert out["722Y001"]["최신값"] == 3.25


# =============================================================================
# get_economic_calendar  (Finnhub)
# =============================================================================


def test_get_economic_calendar_empty_returns_empty_list(monkeypatch):
    """빈 결과 → [] (None / error dict 가 아닌 일관된 list shape)."""
    import server.scrapers.finnhub as fh_mod
    monkeypatch.setattr(
        fh_mod, "fetch_economic_calendar",
        lambda start=None, end=None, country="US": pd.DataFrame(),
    )
    out = mcp_module.get_economic_calendar()
    assert out == []
    assert isinstance(out, list)


def test_get_economic_calendar_passes_args(monkeypatch):
    """start/end/country 인자가 scraper 에 그대로 전달."""
    captured: dict = {}

    def fake(start=None, end=None, country="US"):
        captured["start"] = start
        captured["end"] = end
        captured["country"] = country
        return pd.DataFrame()

    import server.scrapers.finnhub as fh_mod
    monkeypatch.setattr(fh_mod, "fetch_economic_calendar", fake)
    mcp_module.get_economic_calendar(start="2026-05-01", end="2026-05-15", country="KR")
    assert captured["start"] == "2026-05-01"
    assert captured["end"] == "2026-05-15"
    assert captured["country"] == "KR"


def test_get_economic_calendar_returns_list_of_records(monkeypatch):
    """DataFrame → list[dict] 변환 + _json_safe 정규화 (Timestamp → str)."""
    df = pd.DataFrame([
        {
            "시각": pd.Timestamp("2026-05-07 13:30:00", tz="UTC"),
            "국가": "US",
            "이벤트": "CPI YoY",
            "중요도": 3,
            "예측": 3.1,
            "실제": None,
            "이전": 3.5,
        }
    ])
    import server.scrapers.finnhub as fh_mod
    monkeypatch.setattr(
        fh_mod, "fetch_economic_calendar",
        lambda start=None, end=None, country="US": df,
    )
    out = mcp_module.get_economic_calendar()
    assert isinstance(out, list)
    assert len(out) == 1
    row = out[0]
    assert row["국가"] == "US"
    assert row["이벤트"] == "CPI YoY"
    # _json_safe 가 Timestamp 를 isoformat 으로 변환
    assert isinstance(row["시각"], str)


# =============================================================================
# analyze_position  (smoke + 재제안 금지 invariant)
# =============================================================================
# 이 함수는 12 카테고리 통합 1콜. 의존성이 매우 깊어 (repos·analysis·scrapers)
# 카테고리별 세밀한 검증은 별도 라운드. 본 파일은 다음만 검증한다:
#   1) 종목 미존재 → error 분기
#   2) 12 카테고리 키 모두 존재 (success path)
#   3) 재제안 금지 키 (scoring / cell / is_stale) 가 응답 최상위에 없다 — 회귀 가드
#   4) include_base 토글 동작


SAMPLE_STOCK_KR = {
    "code": "005930",
    "name": "삼성전자",
    "market": "kr",
    "currency": "KRW",
    "industry_code": "I010",
}


def _build_ohlcv_df(n: int = 250) -> pd.DataFrame:
    """compute_all 가 동작할 만큼 충분한 행수의 한글 컬럼 OHLCV."""
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    base = 70000 + pd.Series(range(n)) * 30
    return pd.DataFrame({
        "날짜": idx,
        "시가": base.values,
        "고가": (base + 500).values,
        "저가": (base - 500).values,
        "종가": (base + 100).values,
        "거래량": [1_000_000 + i * 10 for i in range(n)],
    })


def _patch_analyze_position_dependencies(monkeypatch):
    """analyze_position 내부 의존성을 얕게 모킹.

    - stocks.get_stock → KR sample
    - stock_base / stock_daily / positions / watch_levels → 빈/None
    - _fetch_ohlcv → synthetic OHLCV
    - kis.fetch_current_price → 가격 dict
    - dart.fetch_financials / summarize_financials → minimal
    - naver.fetch_investor → empty df (analyze_investor_flow 에 빈 입력)
    - dart.fetch_disclosures / fetch_major_shareholders_exec → empty df
    - dart.fetch_next_earnings_date → 빈 dict
    - analyst.list_recent / get_consensus → 빈 list / None
    - economy.get_base / industries.get_industry → None
    """
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: SAMPLE_STOCK_KR)
    monkeypatch.setattr(mcp_module.stock_base, "get_base", lambda code: None)
    monkeypatch.setattr(mcp_module.stock_daily, "get_latest", lambda uid, code: None)
    monkeypatch.setattr(mcp_module.positions, "get_position", lambda uid, code: None)
    monkeypatch.setattr(mcp_module.watch_levels, "list_by_code", lambda uid, code: [])

    # OHLCV: KIS/네이버 어느 경로든 결국 _fetch_ohlcv 가 책임 — 한 번에 패치.
    monkeypatch.setattr(mcp_module, "_fetch_ohlcv", lambda code, days=400: _build_ohlcv_df())

    # 시장 상태 → 정규장 (kis.fetch_current_price 호출 경로)
    monkeypatch.setattr(mcp_module, "_kr_market_state", lambda: "regular")
    monkeypatch.setattr(
        mcp_module.kis, "fetch_current_price",
        lambda code: {"price": 78000.0, "change_pct": 0.5, "volume": 1_000_000},
    )
    # naver fallback 도 안전망
    from server.scrapers import naver as naver_mod
    monkeypatch.setattr(
        naver_mod, "fetch_realtime_price",
        lambda code: {"price": 78000.0, "change_pct": 0.5, "volume": 1_000_000},
    )

    # financials (KR=DART)
    fake_summary = {
        "PER": 12.5, "PBR": 1.1, "EPS": 6000, "BPS": 70000,
        "ROE": 9.5, "ROA": 5.2, "영업이익률": 12.0, "순이익률": 8.5,
        "부채비율": 50.0,
        "매출_YoY": 5.0, "영업이익_YoY": 7.0, "순이익_YoY": 6.0,
    }
    monkeypatch.setattr(mcp_module.dart, "fetch_financials", lambda code, years=3: {})
    monkeypatch.setattr(mcp_module.dart, "summarize_financials", lambda fin: fake_summary)

    # flow (naver investor)
    monkeypatch.setattr(
        mcp_module.naver, "fetch_investor",
        lambda code, pages=2: pd.DataFrame(),
    )

    # events
    monkeypatch.setattr(
        mcp_module.dart, "fetch_next_earnings_date",
        lambda code: {},
    )
    # disclosures / insider
    monkeypatch.setattr(
        mcp_module.dart, "fetch_disclosures",
        lambda code, days=14: pd.DataFrame(),
    )
    monkeypatch.setattr(
        mcp_module.dart, "fetch_major_shareholders_exec",
        lambda code: pd.DataFrame(),
    )

    # consensus
    monkeypatch.setattr(mcp_module.analyst, "list_recent", lambda code, days=30: [])
    monkeypatch.setattr(mcp_module.analyst, "get_consensus", lambda code: None)

    # base 본문 3층 (include_base=True 시)
    from server.repos import economy as economy_mod, industries as industries_mod
    monkeypatch.setattr(economy_mod, "get_base", lambda market: None)
    monkeypatch.setattr(industries_mod, "get_industry", lambda code: None)


def test_analyze_position_unknown_code_returns_error(monkeypatch):
    """종목 미존재 → error 분기 (LLM 이 누락 카테고리로 오인 X)."""
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: None)
    out = mcp_module.analyze_position("NOSUCH")
    assert "error" in out
    assert "NOSUCH" in out["error"]


def test_analyze_position_returns_all_12_categories(monkeypatch):
    """include_base=True 의 12 카테고리 키가 모두 응답에 포함."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=True)

    expected_categories = {
        "base", "context", "realtime", "indicators", "signals",
        "financials", "flow", "volatility", "events",
        "consensus", "disclosures", "insider_trades",
    }
    missing = expected_categories - set(out.keys())
    assert not missing, f"누락된 카테고리: {missing}"


def test_analyze_position_meta_keys_present(monkeypatch):
    """meta: code/name/market + categories_succeeded/total + coverage_pct."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=True)
    assert out["code"] == "005930"
    assert out["name"] == "삼성전자"
    assert out["market"] == "kr"
    assert "categories_succeeded" in out
    assert out["categories_total"] == 12  # include_base=True
    assert "coverage_pct" in out


# ---------------------------------------------------------------------------
# 응답 size 가드 (#23) — disclosures + insider_trades rows cap
# ---------------------------------------------------------------------------


def test_truncate_rows_under_limit_unchanged():
    """rows 개수 ≤ max_rows 면 truncated=False, 원본 그대로."""
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    out = mcp_module._truncate_rows(rows, max_rows=20)
    assert out["rows"] == rows
    assert out["count"] == 3
    assert out["truncated"] is False
    assert "total_count" not in out  # truncated 시만 포함


def test_truncate_rows_over_limit_caps_with_metadata():
    """rows 다대량 → cap + total_count + truncated=True."""
    rows = [{"i": i} for i in range(50)]
    out = mcp_module._truncate_rows(rows, max_rows=20)
    assert len(out["rows"]) == 20
    assert out["rows"][0] == {"i": 0}        # 최근(앞)부터 보존
    assert out["count"] == 20
    assert out["total_count"] == 50
    assert out["truncated"] is True


def test_truncate_rows_empty_safe():
    out = mcp_module._truncate_rows([], max_rows=20)
    assert out == {"rows": [], "count": 0, "truncated": False}


def test_analyze_position_insider_truncates_when_over_limit(monkeypatch):
    """insider_trades 90일 raw rows 다대량 (예: GS 147KB 사례) → cap + total_count 메타."""
    _patch_analyze_position_dependencies(monkeypatch)

    # finnhub.fetch_insider_trading 가 50개 row 반환 (max=20 초과)
    import pandas as pd
    big_rows = pd.DataFrame([
        {"날짜": f"2026-04-{(i % 30) + 1:02d}", "인물": f"insider_{i}",
         "유형": "매수" if i % 2 else "매도", "주식수": 100, "가격": 500.0}
        for i in range(50)
    ])
    from server.scrapers import finnhub as fh
    monkeypatch.setattr(fh, "fetch_insider_trading", lambda code, days=90: big_rows)
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: {
        "code": "GS", "name": "Goldman Sachs", "market": "us", "industry_code": "us-financials",
    })

    out = mcp_module.analyze_position("GS", include_base=False)
    insider = out["insider_trades"]
    assert insider["truncated"] is True
    assert insider["count"] == 20         # cap 적용
    assert insider["total_count"] == 50   # 원본 보존
    assert len(insider["rows"]) == 20
    # summary_90d 는 전체 50건 기반 (US 매수/매도 카운트)
    assert insider["summary_90d"]["buy_count"] + insider["summary_90d"]["sell_count"] == 50


def test_analyze_position_disclosures_truncates_when_over_limit(monkeypatch):
    """disclosures 14일 raw rows 다대량 (Big-tech 8-K 폭증 대비) → cap."""
    _patch_analyze_position_dependencies(monkeypatch)

    import pandas as pd
    big_disc = pd.DataFrame([
        {"date": f"2026-05-{(i % 14) + 1:02d}", "type": "8-K", "title": f"filing_{i}",
         "url": f"https://example/{i}"}
        for i in range(35)
    ])
    from server.scrapers import edgar
    monkeypatch.setattr(edgar, "fetch_disclosures", lambda code, days=14: big_disc)
    monkeypatch.setattr(mcp_module.stocks, "get_stock", lambda code: {
        "code": "GOOGL", "name": "Alphabet", "market": "us", "industry_code": "us-internet",
    })

    out = mcp_module.analyze_position("GOOGL", include_base=False)
    disc = out["disclosures"]
    assert disc["truncated"] is True
    assert disc["count"] == 20
    assert disc["total_count"] == 35
    assert len(disc["rows"]) == 20
    assert isinstance(out["coverage_pct"], (int, float))
    assert "errors" in out


def test_analyze_position_no_scoring_key_invariant(monkeypatch):
    """⚠️ 재제안 금지 — scoring 합성 점수 키 부재."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=True)
    assert "scoring" not in out, "scoring 합성 점수는 라운드 2026-05 폐기 — 재제안 금지"


def test_analyze_position_no_cell_key_invariant(monkeypatch):
    """⚠️ 재제안 금지 — 12셀 매트릭스 cell 키 부재."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=True)
    assert "cell" not in out, "12셀 매트릭스 cell 은 라운드 2026-05 폐기 — 재제안 금지"


def test_analyze_position_no_is_stale_key_invariant(monkeypatch):
    """⚠️ 재제안 금지 — is_stale 자체 판정은 check_base_freshness 단일 진입점."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=True)
    assert "is_stale" not in out, (
        "is_stale 자체 판정은 check_base_freshness 단일 진입점 — analyze_position 응답에서 제거됨"
    )


def test_analyze_position_financials_score_removed(monkeypatch):
    """financials.score 도 노출 X — raw ratios + growth 만."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=True)
    fin = out.get("financials")
    if isinstance(fin, dict) and "error" not in fin:
        assert "score" not in fin, "financials.score 는 응답에 노출 X (per-stock-analysis 가이드)"


def test_analyze_position_include_base_false_drops_base_and_changes_total(monkeypatch):
    """include_base=False → base 카테고리 제외 + categories_total 11."""
    _patch_analyze_position_dependencies(monkeypatch)
    out = mcp_module.analyze_position("005930", include_base=False)
    # base 키가 없거나 (분모 11) 빈 dict 처럼 비활성. 현 구현은 분기 자체를 건너뜀.
    assert "base" not in out, "include_base=False 일 때 base 카테고리는 응답에서 제외"
    assert out["categories_total"] == 11
