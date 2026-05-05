"""server.repos.portfolio_snapshots.reconcile timezone (KST) 테스트.

GitHub Issue #13 — 이전엔 reconcile 만 UTC datetime.now(timezone.utc) 사용 →
다른 모든 코드(events.py / indicators.py / SQL AT TIME ZONE 'Asia/Seoul') 와 어긋남.
fix 후: KST(`ZoneInfo("Asia/Seoul")`) 통일.

본 테스트는 naive expires_at 가 KST 로 해석돼 정상 expired 분기되는지 검증.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from server.repos import portfolio_snapshots as ps_module


KST = ZoneInfo("Asia/Seoul")
USER_ID = uuid4()


# ---------------------------------------------------------------------------
# 헬퍼 — get_conn 모킹 (trades fetch + action_plan UPDATE)
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def execute(self, sql: str, params=None):
        # SELECT 만 row 반환, UPDATE 는 무시
        if "SELECT" in sql.upper():
            return _FakeCursor(self._rows)
        return _FakeCursor([])


@contextmanager
def _fake_get_conn(trades_rows: list[dict] | None = None):
    """get_conn 컨텍스트 매니저 모킹."""
    yield _FakeConn(trades_rows or [])


def _patch_reconcile(monkeypatch, snapshot, trades_rows=None):
    """ps_module.get + get_conn 모킹."""
    monkeypatch.setattr(ps_module, "get", lambda uid, d: snapshot)
    monkeypatch.setattr(
        ps_module, "get_conn",
        lambda: _fake_get_conn(trades_rows=trades_rows),
    )


# ---------------------------------------------------------------------------
# KST 동작 검증 (#13 핵심)
# ---------------------------------------------------------------------------


def test_reconcile_naive_expires_at_treated_as_kst(monkeypatch):
    """naive expires_at 이 KST 로 해석되는지 — UTC 해석이면 결과 다름.

    시나리오:
    - now = 2026-05-05 11:00 KST (= 02:00 UTC)
    - action expires_at = "2026-05-05T10:00:00" (naive)
    - 매칭 trade 없음 (체결 매칭 실패 → expires 분기 진입)

    KST 해석: 10:00 KST < 11:00 KST → expired ✅
    UTC 해석 (옛 동작): 10:00 UTC > 02:00 UTC → not expired ❌
    """
    snapshot = {
        "action_plan": [
            {
                "code": "005930", "action": "buy",
                "status": "pending",
                "expires_at": "2026-05-05T10:00:00",  # naive
            }
        ]
    }
    _patch_reconcile(monkeypatch, snapshot, trades_rows=[])

    fixed_now = datetime(2026, 5, 5, 11, 0, 0, tzinfo=KST)
    fake_dt = MagicMock(wraps=datetime)
    fake_dt.now.return_value = fixed_now
    fake_dt.fromisoformat = datetime.fromisoformat

    with patch.object(ps_module, "datetime", fake_dt):
        result = ps_module.reconcile(USER_ID, date(2026, 5, 5))

    assert result["updated"] == 1
    # snapshot 의 action 이 expired 로 변경됐는지
    assert snapshot["action_plan"][0]["status"] == "expired"


def test_reconcile_aware_expires_at_kst_compared_correctly(monkeypatch):
    """tz-aware KST expires_at — now KST 와 직접 비교."""
    snapshot = {
        "action_plan": [
            {
                "code": "005930", "action": "buy",
                "status": "pending",
                "expires_at": "2026-05-05T10:00:00+09:00",  # tz-aware KST
            }
        ]
    }
    _patch_reconcile(monkeypatch, snapshot, trades_rows=[])

    fixed_now = datetime(2026, 5, 5, 11, 0, 0, tzinfo=KST)
    fake_dt = MagicMock(wraps=datetime)
    fake_dt.now.return_value = fixed_now
    fake_dt.fromisoformat = datetime.fromisoformat

    with patch.object(ps_module, "datetime", fake_dt):
        result = ps_module.reconcile(USER_ID, date(2026, 5, 5))

    assert result["updated"] == 1
    assert snapshot["action_plan"][0]["status"] == "expired"


def test_reconcile_future_expires_not_expired(monkeypatch):
    """expires_at 이 미래 → not expired."""
    snapshot = {
        "action_plan": [
            {
                "code": "005930", "action": "buy",
                "status": "pending",
                "expires_at": "2026-05-05T15:00:00",  # naive, 미래
            }
        ]
    }
    _patch_reconcile(monkeypatch, snapshot, trades_rows=[])

    fixed_now = datetime(2026, 5, 5, 11, 0, 0, tzinfo=KST)  # 만료 4시간 전
    fake_dt = MagicMock(wraps=datetime)
    fake_dt.now.return_value = fixed_now
    fake_dt.fromisoformat = datetime.fromisoformat

    with patch.object(ps_module, "datetime", fake_dt):
        result = ps_module.reconcile(USER_ID, date(2026, 5, 5))

    assert result["updated"] == 0
    assert snapshot["action_plan"][0]["status"] == "pending"


def test_reconcile_now_is_kst_aware(monkeypatch):
    """datetime.now(tz=KST) 호출 — UTC 호출 회귀 가드."""
    # action 1건 필요 (빈 actions 면 early return → datetime.now 미호출)
    snapshot = {
        "action_plan": [
            {"code": "005930", "action": "buy", "status": "pending"},  # expires_at 없음
        ]
    }
    _patch_reconcile(monkeypatch, snapshot, trades_rows=[])

    captured = {}

    class CapturingDT:
        @staticmethod
        def now(tz=None):
            captured["tz"] = tz
            return datetime(2026, 5, 5, 11, 0, tzinfo=tz)

        @staticmethod
        def fromisoformat(s):
            return datetime.fromisoformat(s)

    with patch.object(ps_module, "datetime", CapturingDT):
        ps_module.reconcile(USER_ID, date(2026, 5, 5))

    # tz 인자가 KST 인지 확인 (UTC 가 아님)
    assert captured["tz"] is ps_module._KST
    assert captured["tz"].key == "Asia/Seoul"
