"""데일리 BLOCKING + Phase 1 보조 MCP 툴 contract 테스트.

대상 4개 (모두 daily 시작 시 BLOCKING 으로 호출):
  1. check_base_freshness          — economy/industries/stocks 3계층 만기 일괄 판정
  2. get_pending_base_revisions    — 미처리 base revision 큐 (count >= 3 → ⚠️)
  3. get_weekly_context            — 최근 N주 회고 컨텍스트 + 룰 win-rate
  4. get_weekly_strategy           — 이번 주 사용자 전략 (None 가능)

repos / DB 는 monkeypatch 로 주입 — DB 없이 MCP 래퍼 contract 만 검증.

⚠️ 주의: get_pending_base_revisions 는 함수 안에서 lazy import 되는 server.db.get_conn 을
직접 사용 → monkeypatch 시 server.db.get_conn 자체를 fake context manager 로 교체.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal

import pytest

from server.mcp import server as mcp_module


# ============================================================================
# check_base_freshness
# ============================================================================
# repos: economy.get_base / positions.list_daily_scope / stock_base.get_base
#        / stocks.get_stock / industries.get_industry
# 만기: economy=1일, industry=7일, stock=30일.
# missing → is_stale=True + missing=True + trigger=슬래시 명령.
# all_fresh=True 시 summary.all_fresh==True.


def _patch_freshness(
    monkeypatch,
    *,
    economy_kr=None,
    economy_us=None,
    scope=(),
    stock_bases=None,
    stock_meta=None,
    industries_map=None,
):
    """check_base_freshness 가 호출하는 5개 repos 함수를 일괄 모킹."""
    economies = {"kr": economy_kr, "us": economy_us}
    monkeypatch.setattr(
        mcp_module.economy, "get_base", lambda market: economies.get(market)
    )
    monkeypatch.setattr(
        mcp_module.positions, "list_daily_scope", lambda uid: list(scope)
    )
    monkeypatch.setattr(
        mcp_module.stock_base,
        "get_base",
        lambda code: (stock_bases or {}).get(code),
    )
    monkeypatch.setattr(
        mcp_module.stocks, "get_stock", lambda code: (stock_meta or {}).get(code)
    )
    monkeypatch.setattr(
        mcp_module.industries,
        "get_industry",
        lambda ind: (industries_map or {}).get(ind),
    )


def test_freshness_all_missing_returns_full_keys(monkeypatch):
    """완전 빈 DB → economy 두 시장 모두 missing, industries/stocks 비어있어도 키 보존."""
    _patch_freshness(monkeypatch)
    out = mcp_module.check_base_freshness()
    # 최상위 키 5개 (auto_refresh_log 는 auto_refresh=True 시만)
    assert set(out.keys()) == {"today", "economy", "industries", "stocks", "summary"}
    assert "auto_refresh_log" not in out
    # economy 는 항상 kr/us 2개
    markets = {e["market"] for e in out["economy"]}
    assert markets == {"kr", "us"}
    for e in out["economy"]:
        assert e["missing"] is True
        assert e["is_stale"] is True
        assert e["age_days"] is None
        assert e["expiry_days"] == 1  # EXP_ECONOMY
        assert e["trigger"] == f"/base-economy --{e['market']}"


def test_freshness_economy_fresh_today_not_stale(monkeypatch):
    """오늘 갱신된 economy/base → is_stale=False, trigger=None."""
    today = date_cls.today()
    fresh_row = {"updated_at": datetime(today.year, today.month, today.day, 9, 0, 0)}
    _patch_freshness(monkeypatch, economy_kr=fresh_row, economy_us=fresh_row)
    out = mcp_module.check_base_freshness()
    for e in out["economy"]:
        assert e["missing"] is False
        assert e["is_stale"] is False
        assert e["trigger"] is None
        assert e["age_days"] == 0


def test_freshness_economy_stale_after_1day(monkeypatch):
    """economy 만기 1일 — age_days=1 이면 is_stale=True (>= EXP_ECONOMY)."""
    yesterday = date_cls.today() - timedelta(days=1)
    stale_row = {
        "updated_at": datetime(yesterday.year, yesterday.month, yesterday.day, 9, 0, 0)
    }
    _patch_freshness(monkeypatch, economy_kr=stale_row, economy_us=stale_row)
    out = mcp_module.check_base_freshness()
    for e in out["economy"]:
        assert e["age_days"] == 1
        assert e["is_stale"] is True
        assert e["trigger"] == f"/base-economy --{e['market']}"


def test_freshness_stock_missing_appends_with_trigger(monkeypatch):
    """포지션 종목인데 stock_base 가 DB 에 없으면 missing=True + /base-stock {name} 트리거."""
    today = date_cls.today()
    fresh_econ = {"updated_at": datetime(today.year, today.month, today.day)}
    scope = [{"code": "005930", "name": "삼성전자"}]
    _patch_freshness(
        monkeypatch,
        economy_kr=fresh_econ,
        economy_us=fresh_econ,
        scope=scope,
        stock_bases={},  # 없음
        stock_meta={"005930": {"industry_code": None, "market": "kr"}},
    )
    out = mcp_module.check_base_freshness()
    assert len(out["stocks"]) == 1
    s = out["stocks"][0]
    assert s["code"] == "005930"
    assert s["missing"] is True
    assert s["is_stale"] is True
    assert s["expiry_days"] == 30  # EXP_STOCK
    assert s["trigger"] == "/base-stock 삼성전자"


def test_freshness_stock_fresh_within_30days(monkeypatch):
    """30일 이내 갱신된 stock_base → is_stale=False."""
    today = date_cls.today()
    fresh_econ = {"updated_at": datetime(today.year, today.month, today.day)}
    five_days_ago = today - timedelta(days=5)
    fresh_sb = {"updated_at": datetime(five_days_ago.year, five_days_ago.month, five_days_ago.day, 0, 0)}
    scope = [{"code": "005930", "name": "삼성전자"}]
    _patch_freshness(
        monkeypatch,
        economy_kr=fresh_econ,
        economy_us=fresh_econ,
        scope=scope,
        stock_bases={"005930": fresh_sb},
        stock_meta={"005930": {"industry_code": None, "market": "kr"}},
    )
    out = mcp_module.check_base_freshness()
    s = out["stocks"][0]
    assert s["age_days"] == 5
    assert s["is_stale"] is False
    assert s["missing"] is False
    assert s["trigger"] is None


def test_freshness_stock_stale_at_30days(monkeypatch):
    """정확히 30일 = is_stale True (>= 비교)."""
    today = date_cls.today()
    fresh_econ = {"updated_at": datetime(today.year, today.month, today.day)}
    thirty_ago = today - timedelta(days=30)
    stale_sb = {"updated_at": datetime(thirty_ago.year, thirty_ago.month, thirty_ago.day)}
    scope = [{"code": "005930", "name": "삼성전자"}]
    _patch_freshness(
        monkeypatch,
        economy_kr=fresh_econ,
        economy_us=fresh_econ,
        scope=scope,
        stock_bases={"005930": stale_sb},
        stock_meta={"005930": {"industry_code": None, "market": "kr"}},
    )
    out = mcp_module.check_base_freshness()
    s = out["stocks"][0]
    assert s["age_days"] == 30
    assert s["is_stale"] is True
    assert s["trigger"] == "/base-stock 삼성전자"


def test_freshness_industry_dedup_per_industry(monkeypatch):
    """같은 산업 종목 2개 → industries 항목은 1개 (seen_inds set)."""
    today = date_cls.today()
    fresh_econ = {"updated_at": datetime(today.year, today.month, today.day)}
    fresh_sb = {"updated_at": datetime(today.year, today.month, today.day)}
    scope = [
        {"code": "005930", "name": "삼성전자"},
        {"code": "000660", "name": "SK하이닉스"},
    ]
    stock_meta = {
        "005930": {"industry_code": "G45", "market": "kr"},
        "000660": {"industry_code": "G45", "market": "kr"},
    }
    industries_map = {
        "G45": {
            "name": "반도체",
            "updated_at": datetime(today.year, today.month, today.day),
        }
    }
    _patch_freshness(
        monkeypatch,
        economy_kr=fresh_econ,
        economy_us=fresh_econ,
        scope=scope,
        stock_bases={"005930": fresh_sb, "000660": fresh_sb},
        stock_meta=stock_meta,
        industries_map=industries_map,
    )
    out = mcp_module.check_base_freshness()
    # 종목 2개 → industries dedup → 1개
    assert len(out["stocks"]) == 2
    assert len(out["industries"]) == 1
    assert out["industries"][0]["code"] == "G45"
    assert out["industries"][0]["expiry_days"] == 7  # EXP_INDUSTRY


def test_freshness_industry_missing_trigger(monkeypatch):
    """industry_code 가 stock 에 있지만 industries 테이블에 row 없음 → missing + 슬래시 명령."""
    today = date_cls.today()
    fresh_econ = {"updated_at": datetime(today.year, today.month, today.day)}
    fresh_sb = {"updated_at": datetime(today.year, today.month, today.day)}
    scope = [{"code": "005930", "name": "삼성전자"}]
    _patch_freshness(
        monkeypatch,
        economy_kr=fresh_econ,
        economy_us=fresh_econ,
        scope=scope,
        stock_bases={"005930": fresh_sb},
        stock_meta={"005930": {"industry_code": "G45", "market": "kr"}},
        industries_map={},  # 비어있음
    )
    out = mcp_module.check_base_freshness()
    assert len(out["industries"]) == 1
    ind = out["industries"][0]
    assert ind["missing"] is True
    assert ind["is_stale"] is True
    assert ind["trigger"] == "/base-industry G45"


def test_freshness_summary_all_fresh_true(monkeypatch):
    """economy/stock/industry 모두 fresh → summary.all_fresh=True, total_stale=0."""
    today = date_cls.today()
    fresh = {"updated_at": datetime(today.year, today.month, today.day)}
    scope = [{"code": "005930", "name": "삼성전자"}]
    _patch_freshness(
        monkeypatch,
        economy_kr=fresh,
        economy_us=fresh,
        scope=scope,
        stock_bases={"005930": fresh},
        stock_meta={"005930": {"industry_code": "G45", "market": "kr"}},
        industries_map={"G45": {"name": "반도체", "updated_at": fresh["updated_at"]}},
    )
    out = mcp_module.check_base_freshness()
    summary = out["summary"]
    assert summary["all_fresh"] is True
    assert summary["total_stale"] == 0
    assert summary["total_missing"] == 0
    assert summary["auto_triggers"] == []
    assert summary["needs_refresh"] == []


def test_freshness_summary_aggregates_triggers(monkeypatch):
    """stale 항목들의 trigger 가 unique 정렬되어 auto_triggers 에 모임."""
    _patch_freshness(monkeypatch)  # 모두 missing
    out = mcp_module.check_base_freshness()
    triggers = out["summary"]["auto_triggers"]
    # economy kr/us 둘 다 missing → 2개
    assert "/base-economy --kr" in triggers
    assert "/base-economy --us" in triggers
    # 정렬 보장 (sorted set)
    assert triggers == sorted(triggers)
    assert out["summary"]["total_stale"] >= 2
    assert out["summary"]["total_missing"] >= 2
    assert out["summary"]["all_fresh"] is False


def test_freshness_today_iso_format(monkeypatch):
    """today 는 YYYY-MM-DD ISO 문자열."""
    _patch_freshness(monkeypatch)
    out = mcp_module.check_base_freshness()
    today = date_cls.today().isoformat()
    assert out["today"] == today
    assert isinstance(out["today"], str)


# ============================================================================
# get_pending_base_revisions
# ============================================================================
# server.db.get_conn 을 직접 사용 (lazy import) → server.db.get_conn 패치.


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params=()):
        self.last_sql = sql
        self.last_params = params
        return _FakeCursor(self._rows)


def _patch_get_conn(monkeypatch, rows):
    """server.db.get_conn 을 fake context manager 로 교체.

    get_pending_base_revisions 는 'from server.db import get_conn' lazy import 라
    server.db.get_conn 자체를 패치하면 호출 시점에 새 함수를 가져온다.
    """
    import server.db

    @contextmanager
    def fake_conn():
        yield _FakeConn(rows)

    monkeypatch.setattr(server.db, "get_conn", fake_conn)


def test_pending_revisions_empty_returns_zero_count(monkeypatch):
    """빈 DB → {pending: [], count: 0} (LLM 이 명확히 0 인지)."""
    _patch_get_conn(monkeypatch, [])
    out = mcp_module.get_pending_base_revisions()
    assert out == {"pending": [], "count": 0}
    assert isinstance(out["pending"], list)
    assert isinstance(out["count"], int)


def test_pending_revisions_filters_pending_user_review_status(monkeypatch):
    """status='pending_user_review' 인 revision 만 큐에 들어감."""
    rows = [
        {
            "week_start": date_cls(2026, 4, 27),
            "phase3_log": {
                "proposed_revisions": [
                    {"status": "pending_user_review", "code": "005930", "field": "narrative"},
                    {"status": "applied", "code": "000660", "field": "narrative"},
                    {"status": "rejected", "code": "AAPL", "field": "risks"},
                ]
            },
        }
    ]
    _patch_get_conn(monkeypatch, rows)
    out = mcp_module.get_pending_base_revisions()
    assert out["count"] == 1
    assert out["pending"][0]["code"] == "005930"
    assert out["pending"][0]["status"] == "pending_user_review"


def test_pending_revisions_attaches_week_start_iso(monkeypatch):
    """각 pending 항목에 source 회고의 week_start (ISO str) 가 부착됨."""
    rows = [
        {
            "week_start": date_cls(2026, 4, 27),
            "phase3_log": {
                "proposed_revisions": [
                    {"status": "pending_user_review", "code": "005930"}
                ]
            },
        }
    ]
    _patch_get_conn(monkeypatch, rows)
    out = mcp_module.get_pending_base_revisions()
    assert out["pending"][0]["week_start"] == "2026-04-27"


def test_pending_revisions_skips_non_dict_phase3_log(monkeypatch):
    """phase3_log 가 dict 아니면 (예: 잘못 적재된 list/str) 스킵 — silent fail X."""
    rows = [
        {"week_start": date_cls(2026, 4, 27), "phase3_log": "garbage"},
        {"week_start": date_cls(2026, 4, 20), "phase3_log": ["x"]},
    ]
    _patch_get_conn(monkeypatch, rows)
    out = mcp_module.get_pending_base_revisions()
    assert out == {"pending": [], "count": 0}


def test_pending_revisions_count_threshold_3_signaled(monkeypatch):
    """count >= 3 시그널 — 단일 회고에 3건 누적되면 정확히 count=3 반환."""
    rows = [
        {
            "week_start": date_cls(2026, 4, 27),
            "phase3_log": {
                "proposed_revisions": [
                    {"status": "pending_user_review", "code": "005930"},
                    {"status": "pending_user_review", "code": "000660"},
                    {"status": "pending_user_review", "code": "035720"},
                ]
            },
        }
    ]
    _patch_get_conn(monkeypatch, rows)
    out = mcp_module.get_pending_base_revisions()
    assert out["count"] == 3
    assert len(out["pending"]) == 3
    # daily Phase 1 BLOCKING 가드 (count >= 3 → ⚠️) 가 명확히 트리거 가능
    assert out["count"] >= 3


def test_pending_revisions_aggregates_across_multiple_weeks(monkeypatch):
    """여러 주의 회고에서 pending 누적 — 각 항목 week_start 분리 보존."""
    rows = [
        {
            "week_start": date_cls(2026, 4, 27),
            "phase3_log": {
                "proposed_revisions": [
                    {"status": "pending_user_review", "code": "005930"}
                ]
            },
        },
        {
            "week_start": date_cls(2026, 4, 20),
            "phase3_log": {
                "proposed_revisions": [
                    {"status": "pending_user_review", "code": "000660"}
                ]
            },
        },
    ]
    _patch_get_conn(monkeypatch, rows)
    out = mcp_module.get_pending_base_revisions()
    assert out["count"] == 2
    weeks = sorted({p["week_start"] for p in out["pending"]})
    assert weeks == ["2026-04-20", "2026-04-27"]


def test_pending_revisions_handles_missing_proposed_revisions_key(monkeypatch):
    """phase3_log 에 proposed_revisions 키가 아예 없으면 빈 결과로 안전 동작."""
    rows = [
        {"week_start": date_cls(2026, 4, 27), "phase3_log": {"other_key": "x"}}
    ]
    _patch_get_conn(monkeypatch, rows)
    out = mcp_module.get_pending_base_revisions()
    assert out == {"pending": [], "count": 0}


# ============================================================================
# get_weekly_strategy
# ============================================================================
# repos.weekly_strategy.{get_current, get_by_week} 모킹.


def test_weekly_strategy_no_arg_uses_get_current(monkeypatch):
    """week_start=None → get_current() 호출. 결과 dict 가 _row_safe 통과."""
    fake_row = {
        "id": 1,
        "week_start": date_cls(2026, 5, 4),
        "market_outlook": "중립",
        "focus_themes": ["반도체"],
        "carry_over": False,
        "created_at": datetime(2026, 5, 4, 9, 0, 0),
    }
    monkeypatch.setattr(
        mcp_module, "settings", mcp_module.settings
    )  # no-op (안전망)
    from server.repos import weekly_strategy as ws

    monkeypatch.setattr(ws, "get_current", lambda: fake_row)
    out = mcp_module.get_weekly_strategy()
    assert out is not None
    assert out["week_start"] == "2026-05-04"
    assert out["market_outlook"] == "중립"
    # datetime → ISO 문자열
    assert out["created_at"] == "2026-05-04T09:00:00"


def test_weekly_strategy_no_arg_returns_none_when_no_row(monkeypatch):
    """get_current() 가 None → MCP 도 None 그대로 (LLM '전략 미작성' 분기)."""
    from server.repos import weekly_strategy as ws

    monkeypatch.setattr(ws, "get_current", lambda: None)
    out = mcp_module.get_weekly_strategy()
    assert out is None


def test_weekly_strategy_explicit_week_calls_get_by_week(monkeypatch):
    """week_start='YYYY-MM-DD' → get_by_week(date) 호출 + carry_over=False 부착."""
    captured: dict = {}
    fake_row = {
        "id": 9,
        "week_start": date_cls(2026, 4, 27),
        "market_outlook": "약세",
    }
    from server.repos import weekly_strategy as ws

    def fake_by_week(d):
        captured["week"] = d
        return fake_row

    monkeypatch.setattr(ws, "get_by_week", fake_by_week)
    out = mcp_module.get_weekly_strategy("2026-04-27")
    assert captured["week"] == date_cls(2026, 4, 27)
    assert out is not None
    assert out["week_start"] == "2026-04-27"
    assert out["carry_over"] is False


def test_weekly_strategy_explicit_week_returns_none(monkeypatch):
    """존재하지 않는 주 → None."""
    from server.repos import weekly_strategy as ws

    monkeypatch.setattr(ws, "get_by_week", lambda d: None)
    out = mcp_module.get_weekly_strategy("2026-04-27")
    assert out is None


def test_weekly_strategy_invalid_iso_raises():
    """잘못된 ISO 형식 → ValueError (silent fail X)."""
    with pytest.raises(ValueError):
        mcp_module.get_weekly_strategy("2026/04/27")


# ============================================================================
# get_weekly_context
# ============================================================================
# repos.weekly_reviews.{list_reviews, get_review} 모킹. 내부 로직 깊으니 minimal contract.


def test_weekly_context_empty_returns_skeleton(monkeypatch):
    """list_reviews 빈 결과 → 최소 키 (latest_review/rolling_stats/carryover_actions) 보존."""
    from server.repos import weekly_reviews as wr

    monkeypatch.setattr(wr, "list_reviews", lambda limit=12: [])
    out = mcp_module.get_weekly_context()
    assert set(out.keys()) == {"latest_review", "rolling_stats", "carryover_actions"}
    assert out["latest_review"] is None
    assert out["carryover_actions"] == []
    rs = out["rolling_stats"]
    assert rs["weeks_count"] == 0
    assert rs["rule_win_rates"] == {}
    assert rs["total_realized_pnl_kr"] == 0
    assert rs["trade_count_total"] == 0


def test_weekly_context_passes_weeks_arg_to_list_reviews(monkeypatch):
    """weeks 인자가 list_reviews(limit=...) 에 전달."""
    captured: dict = {}
    from server.repos import weekly_reviews as wr

    def fake_list(limit=12):
        captured["limit"] = limit
        return []

    monkeypatch.setattr(wr, "list_reviews", fake_list)
    mcp_module.get_weekly_context(weeks=8)
    # max(weeks, 1) 적용
    assert captured["limit"] == 8


def test_weekly_context_with_one_review_aggregates_stats(monkeypatch):
    """단일 review → rolling_stats.weeks_count=1, total_realized 합산, rule_win_rates 집계."""
    from server.repos import weekly_reviews as wr

    list_row = {"week_start": date_cls(2026, 4, 27), "headline": "OK"}
    full_row = {
        "week_start": date_cls(2026, 4, 27),
        "week_end": date_cls(2026, 5, 3),
        "headline": "OK",
        "highlights": ["a"],
        "next_week_actions": [],
        "realized_pnl_kr": Decimal("123.45"),
        "trade_count": 5,
        "win_rate": {
            "BB_squeeze": {"tries": 4, "wins": 2, "pct": 50.0},
            "RSI_div": {"tries": 2, "wins": 0, "pct": 0.0},
        },
    }
    monkeypatch.setattr(wr, "list_reviews", lambda limit=12: [list_row])
    monkeypatch.setattr(wr, "get_review", lambda ws: full_row)
    out = mcp_module.get_weekly_context(weeks=4)
    rs = out["rolling_stats"]
    assert rs["weeks_count"] == 1
    assert rs["total_realized_pnl_kr"] == 123.45
    assert rs["trade_count_total"] == 5
    assert "BB_squeeze" in rs["rule_win_rates"]
    bb = rs["rule_win_rates"]["BB_squeeze"]
    assert bb["tries"] == 4
    assert bb["wins"] == 2
    assert bb["pct"] == 50.0
    # latest_review shape
    lr = out["latest_review"]
    assert lr is not None
    assert lr["week_start"] == "2026-04-27"
    assert lr["headline"] == "OK"
