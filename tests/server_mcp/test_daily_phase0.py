"""데일리 Phase 0 (스코프 일괄 로드) MCP 툴 contract 테스트.

대상: list_daily_positions
- BLOCKING #1: 모든 daily 시작 시 호출.
- Active + Pending 분리, all_codes 일괄, counts 메타 확인.

repos.positions.list_daily_scope 를 monkeypatch.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from server.mcp import server as mcp_module


SAMPLE_ACTIVE = {
    "code": "005930",
    "name": "삼성전자",
    "market": "kr",
    "status": "Active",
    "qty": Decimal("10"),
    "avg_price": Decimal("78000"),
    "cost_basis": Decimal("780000"),
    "currency": "KRW",
    "created_at": datetime(2026, 1, 1, 9, 0, 0),
}

SAMPLE_PENDING = {
    "code": "AAPL",
    "name": "Apple",
    "market": "us",
    "status": "Pending",
    "qty": Decimal("0"),
    "avg_price": None,
    "cost_basis": Decimal("0"),
    "currency": "USD",
    "created_at": datetime(2026, 4, 30, 22, 0, 0),
}


def _patch(monkeypatch, rows):
    monkeypatch.setattr(
        mcp_module.positions, "list_daily_scope", lambda uid: list(rows)
    )


def test_empty_returns_all_keys_with_zero_counts(monkeypatch):
    """빈 결과여도 active/pending/all_codes/counts 4 키 모두 존재 (LLM 키 누락 오인 X)."""
    _patch(monkeypatch, [])
    out = mcp_module.list_daily_positions()
    assert set(out.keys()) == {"active", "pending", "all_codes", "counts"}
    assert out["active"] == []
    assert out["pending"] == []
    assert out["all_codes"] == []
    assert out["counts"] == {"active": 0, "pending": 0, "total": 0}


def test_active_only(monkeypatch):
    _patch(monkeypatch, [SAMPLE_ACTIVE])
    out = mcp_module.list_daily_positions()
    assert len(out["active"]) == 1
    assert out["pending"] == []
    assert out["all_codes"] == ["005930"]
    assert out["counts"] == {"active": 1, "pending": 0, "total": 1}


def test_pending_only(monkeypatch):
    _patch(monkeypatch, [SAMPLE_PENDING])
    out = mcp_module.list_daily_positions()
    assert out["active"] == []
    assert len(out["pending"]) == 1
    assert out["all_codes"] == ["AAPL"]
    assert out["counts"] == {"active": 0, "pending": 1, "total": 1}


def test_mixed_active_then_pending_in_all_codes(monkeypatch):
    """all_codes 순서 = Active 먼저 → Pending. 정렬 보존."""
    rows = [SAMPLE_ACTIVE, SAMPLE_PENDING]
    _patch(monkeypatch, rows)
    out = mcp_module.list_daily_positions()
    assert out["all_codes"] == ["005930", "AAPL"]
    assert out["counts"] == {"active": 1, "pending": 1, "total": 2}


def test_decimal_serialized_to_float(monkeypatch):
    """qty/avg_price/cost_basis Decimal → float."""
    _patch(monkeypatch, [SAMPLE_ACTIVE])
    out = mcp_module.list_daily_positions()
    pos = out["active"][0]
    assert isinstance(pos["qty"], float)
    assert isinstance(pos["avg_price"], float)
    assert pos["qty"] == 10.0
    assert pos["avg_price"] == 78000.0


def test_pending_with_none_avg_price_preserved(monkeypatch):
    """Pending 종목은 avg_price NULL — None 그대로 보존 (LLM이 missing으로 오인 X)."""
    _patch(monkeypatch, [SAMPLE_PENDING])
    out = mcp_module.list_daily_positions()
    assert out["pending"][0]["avg_price"] is None
    assert "avg_price" in out["pending"][0]


def test_close_status_excluded(monkeypatch):
    """Close 상태는 daily 스코프 제외. repos 가 이미 필터하지만 MCP 안전망 검증."""
    closed = {**SAMPLE_ACTIVE, "code": "035720", "status": "Close"}
    _patch(monkeypatch, [SAMPLE_ACTIVE, closed])
    out = mcp_module.list_daily_positions()
    assert len(out["active"]) == 1
    assert out["all_codes"] == ["005930"]  # closed 제외
