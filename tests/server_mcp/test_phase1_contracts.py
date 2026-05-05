"""Phase 1 MCP 툴 응답 contract 테스트.

LLM 이 list_trades / get_portfolio_summary / reconcile_actions 의 응답 shape 를
신뢰할 수 있도록 empty / single / many 케이스에서 일관된 키 + 타입을 반환하는지 검증.

repos 레이어는 monkeypatch 로 가짜 데이터 주입 — DB 없이 MCP 래퍼만 검증.

⚠️ 주의: list_trades 만 bare list[dict] 반환 (다른 Phase 1 툴은 dict).
빈 결과 [] 가 LLM 에 "툴 실패" 로 오인되지 않도록 contract 명확히 해두고,
shape 변경 (예: dict 로 wrap) 시 본 테스트가 깨져 변경을 강제 인지하게 한다.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from server.mcp import server as mcp_module


SAMPLE_TRADE_ROW: dict = {
    "id": 1,
    "code": "005930",
    "name": "삼성전자",
    "market": "kr",
    "side": "buy",
    "qty": Decimal("10"),
    "price": Decimal("78000"),
    "executed_at": datetime(2026, 5, 5, 9, 30, 0),
    "trigger_note": "test",
    "realized_pnl": None,
    "fees": Decimal("0"),
    "created_at": datetime(2026, 5, 5, 9, 30, 1),
}

REQUIRED_TRADE_KEYS = {
    "id", "code", "name", "market", "side", "qty", "price",
    "executed_at", "trigger_note", "realized_pnl", "fees", "created_at",
}


def _patch_trades(monkeypatch, rows):
    monkeypatch.setattr(
        mcp_module.trades,
        "list_by_user",
        lambda uid, code=None, limit=20: list(rows),
    )


# ---------------------------------------------------------------------------
# list_trades — shape contract
# ---------------------------------------------------------------------------


def test_list_trades_empty_returns_empty_list(monkeypatch):
    """no trades → [] (not None, not error dict). Phase 1 BLOCKING #5/#6 의도와 일치."""
    _patch_trades(monkeypatch, [])
    out = mcp_module.list_trades()
    assert out == []
    assert isinstance(out, list)


def test_list_trades_single_has_all_required_keys(monkeypatch):
    """single trade → 모든 key 가 응답에 포함 (LLM이 누락 키로 인해 헷갈림 방지)."""
    _patch_trades(monkeypatch, [SAMPLE_TRADE_ROW])
    out = mcp_module.list_trades()
    assert len(out) == 1
    assert REQUIRED_TRADE_KEYS.issubset(out[0].keys())


def test_list_trades_decimal_converted_to_float(monkeypatch):
    """qty/price/fees Decimal → JSON-safe float (LLM 이 Decimal 객체 처리 못함)."""
    _patch_trades(monkeypatch, [SAMPLE_TRADE_ROW])
    out = mcp_module.list_trades()
    assert isinstance(out[0]["qty"], float)
    assert isinstance(out[0]["price"], float)
    assert isinstance(out[0]["fees"], float)
    assert out[0]["qty"] == 10.0
    assert out[0]["price"] == 78000.0


def test_list_trades_datetime_converted_to_isoformat(monkeypatch):
    """executed_at datetime → ISO 문자열."""
    _patch_trades(monkeypatch, [SAMPLE_TRADE_ROW])
    out = mcp_module.list_trades()
    assert out[0]["executed_at"] == "2026-05-05T09:30:00"
    assert isinstance(out[0]["executed_at"], str)


def test_list_trades_null_pnl_preserved_as_none(monkeypatch):
    """realized_pnl None → None 그대로 (LLM 이 missing 키로 오인 X)."""
    _patch_trades(monkeypatch, [SAMPLE_TRADE_ROW])
    out = mcp_module.list_trades()
    assert "realized_pnl" in out[0]
    assert out[0]["realized_pnl"] is None


def test_list_trades_passes_args_to_repos(monkeypatch):
    """code / limit 인자가 repos 에 정확히 전달되는지 확인."""
    captured: dict = {}

    def fake_list(uid, code=None, limit=20):
        captured["uid"] = uid
        captured["code"] = code
        captured["limit"] = limit
        return []

    monkeypatch.setattr(mcp_module.trades, "list_by_user", fake_list)
    mcp_module.list_trades(code="005930", limit=50)
    assert captured["code"] == "005930"
    assert captured["limit"] == 50
    # uid 는 settings.stock_user_id (단일 유저 fallback). 값 확인보다 호출됐다는 것만.
    assert captured["uid"] is not None


def test_list_trades_many_preserves_order(monkeypatch):
    """repos 가 ORDER BY executed_at DESC 보장 — MCP 래퍼는 순서 그대로 전달."""
    rows = [
        {**SAMPLE_TRADE_ROW, "id": 3, "executed_at": datetime(2026, 5, 5, 14)},
        {**SAMPLE_TRADE_ROW, "id": 2, "executed_at": datetime(2026, 5, 5, 11)},
        {**SAMPLE_TRADE_ROW, "id": 1, "executed_at": datetime(2026, 5, 5, 9)},
    ]
    _patch_trades(monkeypatch, rows)
    out = mcp_module.list_trades()
    assert [r["id"] for r in out] == [3, 2, 1]


# ---------------------------------------------------------------------------
# get_portfolio_summary — discriminated union
# ---------------------------------------------------------------------------


def test_get_portfolio_summary_not_found_returns_explicit_false(monkeypatch):
    """없는 날짜 → {found: False, date: ...} — LLM 이 명시적 False 로 분기."""
    monkeypatch.setattr(mcp_module.portfolio_snapshots, "get", lambda uid, d: None)
    out = mcp_module.get_portfolio_summary("2026-05-05")
    assert out == {"found": False, "date": "2026-05-05"}


def test_get_portfolio_summary_found_wraps_snapshot(monkeypatch):
    """있으면 {found: True, snapshot: {...}} — LLM 이 snapshot 키로 본문 접근."""
    from datetime import date as date_cls
    fake_row = {
        "date": date_cls(2026, 5, 5),
        "headline": "오늘은 매도 우세",
        "summary_content": "마크다운 본문",
        "saved_at": datetime(2026, 5, 5, 16, 0, 0),
    }
    monkeypatch.setattr(mcp_module.portfolio_snapshots, "get", lambda uid, d: fake_row)
    out = mcp_module.get_portfolio_summary("2026-05-05")
    assert out["found"] is True
    assert "snapshot" in out
    assert out["snapshot"]["headline"] == "오늘은 매도 우세"
    # date / saved_at 직렬화 확인
    assert out["snapshot"]["date"] == "2026-05-05"
    assert out["snapshot"]["saved_at"] == "2026-05-05T16:00:00"


def test_get_portfolio_summary_invalid_date_raises():
    """ISO 형식 아닌 입력은 ValueError — Claude 가 즉시 인지하도록 silent fail X."""
    with pytest.raises(ValueError):
        mcp_module.get_portfolio_summary("2026/05/05")


# ---------------------------------------------------------------------------
# reconcile_actions — pass-through
# ---------------------------------------------------------------------------


def test_reconcile_actions_returns_repo_dict(monkeypatch):
    """repos 결과를 그대로 반환 (래퍼는 date 파싱만)."""
    fake_result = {"updated": 2, "total_actions": 5, "matched_trade_ids": [10, 11]}
    monkeypatch.setattr(
        mcp_module.portfolio_snapshots, "reconcile", lambda uid, d: fake_result
    )
    out = mcp_module.reconcile_actions("2026-05-05")
    assert out == fake_result


def test_reconcile_actions_invalid_date_raises():
    with pytest.raises(ValueError):
        mcp_module.reconcile_actions("yesterday")
