"""server.mcp.server 의 _row_safe / _json_safe 헬퍼 테스트.

Phase 1 MCP 툴(list_trades / get_portfolio_summary / reconcile_actions / get_weekly_context)이
모두 이 헬퍼를 거쳐 응답을 만든다. 헬퍼가 깨지면 LLM이 응답 shape 를 신뢰 못함.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest

from server.mcp.server import _json_safe, _row_safe


# ---------------------------------------------------------------------------
# _row_safe — 1단계 dict 평탄화
# ---------------------------------------------------------------------------


def test_row_safe_none_returns_none():
    assert _row_safe(None) is None


def test_row_safe_decimal_to_float():
    out = _row_safe({"price": Decimal("78000.50")})
    assert isinstance(out["price"], float)
    assert out["price"] == 78000.50


def test_row_safe_datetime_to_isoformat():
    out = _row_safe({"executed_at": datetime(2026, 5, 5, 14, 30, 0)})
    assert out["executed_at"] == "2026-05-05T14:30:00"
    assert isinstance(out["executed_at"], str)


def test_row_safe_date_to_isoformat():
    out = _row_safe({"trade_date": date(2026, 5, 5)})
    assert out["trade_date"] == "2026-05-05"


def test_row_safe_keeps_primitive_types():
    out = _row_safe({"qty": 100, "side": "buy", "active": True, "rate": 1.5})
    assert out == {"qty": 100, "side": "buy", "active": True, "rate": 1.5}


def test_row_safe_preserves_none_field():
    """trades.realized_pnl 처럼 NULL 가능 컬럼은 None 그대로 유지 (LLM이 missing 으로 오인 X)."""
    out = _row_safe({"realized_pnl": None, "trigger_note": None})
    assert out == {"realized_pnl": None, "trigger_note": None}


# ---------------------------------------------------------------------------
# _json_safe — 재귀 + numpy + NaN/Inf
# ---------------------------------------------------------------------------


def test_json_safe_numpy_int_to_python_int():
    out = _json_safe(np.int64(42))
    assert out == 42
    assert isinstance(out, int)


def test_json_safe_numpy_float_to_python_float():
    out = _json_safe(np.float64(3.14))
    assert out == pytest.approx(3.14)
    assert isinstance(out, float)


def test_json_safe_nan_to_none():
    """JSON 표준은 NaN 미지원. None 으로 정규화해 LLM 응답 깨지는 걸 막음."""
    assert _json_safe(np.float64("nan")) is None
    assert _json_safe(float("nan")) is None


def test_json_safe_inf_to_none():
    assert _json_safe(float("inf")) is None
    assert _json_safe(float("-inf")) is None


def test_json_safe_numpy_array_to_list():
    out = _json_safe(np.array([1, 2, 3]))
    assert out == [1, 2, 3]
    assert all(isinstance(x, int) for x in out)


def test_json_safe_decimal_to_float():
    out = _json_safe(Decimal("99.99"))
    assert out == 99.99
    assert isinstance(out, float)


def test_json_safe_nested_dict_recurse():
    """중첩 dict 안의 Decimal/datetime 도 모두 변환."""
    inp = {
        "outer": {
            "decimal": Decimal("1.5"),
            "list": [Decimal("2.5"), 3, "str"],
            "nested": {"date": date(2026, 5, 5)},
        }
    }
    out = _json_safe(inp)
    assert out == {
        "outer": {
            "decimal": 1.5,
            "list": [2.5, 3, "str"],
            "nested": {"date": "2026-05-05"},
        }
    }


def test_json_safe_numpy_bool():
    """numpy bool 은 Python bool 로 (`is True/False` 비교 깨지는 걸 방지)."""
    assert _json_safe(np.bool_(True)) is True
    assert _json_safe(np.bool_(False)) is False


def test_json_safe_str_passthrough():
    assert _json_safe("hello") == "hello"
    assert _json_safe("") == ""


def test_json_safe_empty_collections():
    """빈 list/dict 보존 (LLM 이 empty vs missing 구분)."""
    assert _json_safe([]) == []
    assert _json_safe({}) == {}
