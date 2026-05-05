"""데일리 Phase 7 (저장 단계) MCP 툴 contract 테스트.

대상:
- save_daily_report — 종목별 일일 보고서 저장 (v7 결론 정량 인자 포함)
- save_portfolio_summary — 포트폴리오 일일 종합 스냅샷 저장 (v11)

핵심 contract:
- verdict 빈 문자열·공백만 → None 으로 normalize (CHECK constraint 회피, server.py:706)
- 인자가 repos 레이어에 정확히 전달되는지 capture 검증
- 잘못된 date 형식 → ValueError
- 카운트(action/stock/risk)는 None / [] 모두 0

repos.stock_daily.upsert_content / repos.portfolio_snapshots.save 를 monkeypatch.
"""
from __future__ import annotations

import pytest

from server.mcp import server as mcp_module


# ---------------------------------------------------------------------------
# save_daily_report
# ---------------------------------------------------------------------------


def _patch_upsert(monkeypatch) -> dict:
    """upsert_content 호출 인자를 captured dict 로 수집."""
    captured: dict = {}

    def fake_upsert(uid, code, d, content, verdict=None, **kwargs):
        captured["uid"] = uid
        captured["code"] = code
        captured["date"] = d
        captured["content"] = content
        captured["verdict"] = verdict
        captured["kwargs"] = kwargs

    monkeypatch.setattr(mcp_module.stock_daily, "upsert_content", fake_upsert)
    return captured


def test_save_daily_report_returns_ok_envelope(monkeypatch):
    """정상 호출 → {ok, code, date, verdict, chars} 5 키 응답."""
    _patch_upsert(monkeypatch)
    out = mcp_module.save_daily_report("005930", "2026-05-05", "강한매수", "본문 마크다운")
    assert out["ok"] is True
    assert out["code"] == "005930"
    assert out["date"] == "2026-05-05"
    assert out["verdict"] == "강한매수"
    assert out["chars"] == len("본문 마크다운")


def test_save_daily_report_chars_matches_content_length(monkeypatch):
    """chars 가 content 길이와 정확히 일치 (멀티바이트 포함)."""
    _patch_upsert(monkeypatch)
    content = "삼성전자 매수 우세 — 외국인 순매수 + 5일선 회복"
    out = mcp_module.save_daily_report("005930", "2026-05-05", "매수우세", content)
    assert out["chars"] == len(content)


def test_save_daily_report_empty_verdict_normalized_to_none(monkeypatch):
    """verdict 빈 문자열 → None (CHECK constraint 위반 회피, server.py:706 룰)."""
    captured = _patch_upsert(monkeypatch)
    out = mcp_module.save_daily_report("005930", "2026-05-05", "", "본문")
    # 응답 verdict 도 None
    assert out["verdict"] is None
    # repos 에 None 으로 전달
    assert captured["verdict"] is None


def test_save_daily_report_whitespace_verdict_normalized_to_none_in_repos(monkeypatch):
    """verdict 공백만 → repos 에는 None 으로 전달 (CHECK constraint 회피).

    ⚠️ 응답 envelope 의 'verdict' 필드는 strip 결과(빈 문자열)를 그대로 노출 — 즉,
       응답 verdict 와 repos 에 저장되는 값이 불일치 (server.py:706-714).
       응답은 빈 문자열, DB 는 None. CHECK constraint 회피만 되면 의도상 OK 하나
       LLM 이 응답을 다시 읽어 verdict 를 검증할 때 잠재적 혼란.
    """
    captured = _patch_upsert(monkeypatch)
    out = mcp_module.save_daily_report("005930", "2026-05-05", "   ", "본문")
    # repos 호출 시 verdict 는 None (CHECK 회피 — 핵심 contract)
    assert captured["verdict"] is None
    # 응답 verdict 는 strip 결과 빈 문자열 (현 구현 동작 보존; 변경 시 이 테스트 깨져 인지)
    assert out["verdict"] == ""


def test_save_daily_report_none_verdict_passed_through(monkeypatch):
    """verdict 인자가 명시 None 이면 그대로 None 으로 처리 (`v or None`)."""
    captured = _patch_upsert(monkeypatch)
    # verdict 는 positional 4번째라 None 직접 전달
    out = mcp_module.save_daily_report("005930", "2026-05-05", None, "본문")  # type: ignore[arg-type]
    assert out["verdict"] is None
    assert captured["verdict"] is None


def test_save_daily_report_invalid_date_raises(monkeypatch):
    """ISO 형식 아닌 date → ValueError (silent fail X)."""
    _patch_upsert(monkeypatch)
    with pytest.raises(ValueError):
        mcp_module.save_daily_report("005930", "2026/05/05", "강한매수", "본문")


def test_save_daily_report_passes_args_to_repos(monkeypatch):
    """code/date/content/verdict 가 repos.upsert_content 에 정확히 전달."""
    captured = _patch_upsert(monkeypatch)
    mcp_module.save_daily_report("AAPL", "2026-05-05", "매수우세", "Apple 본문")
    from datetime import date as date_cls

    assert captured["code"] == "AAPL"
    assert captured["date"] == date_cls(2026, 5, 5)
    assert captured["content"] == "Apple 본문"
    assert captured["verdict"] == "매수우세"
    assert captured["uid"] is not None  # settings.stock_user_id fallback


def test_save_daily_report_v7_quant_fields_forwarded(monkeypatch):
    """v7 신규 결론 정량 인자 6개 모두 repos.upsert_content kwargs 로 전달."""
    captured = _patch_upsert(monkeypatch)
    mcp_module.save_daily_report(
        "005930",
        "2026-05-05",
        "강한매수",
        "본문",
        size_pct=15,
        stop_method="ATR",
        stop_value=1.5,
        override_dimensions=["earnings_d7", "macro_shift"],
        key_factors=["외국인 순매수", "5일선 회복"],
        referenced_rules=["rule.kr.momentum.001"],
    )
    kw = captured["kwargs"]
    assert kw["size_pct"] == 15
    assert kw["stop_method"] == "ATR"
    assert kw["stop_value"] == 1.5
    assert kw["override_dimensions"] == ["earnings_d7", "macro_shift"]
    assert kw["key_factors"] == ["외국인 순매수", "5일선 회복"]
    assert kw["referenced_rules"] == ["rule.kr.momentum.001"]


def test_save_daily_report_v7_defaults_none(monkeypatch):
    """v7 인자 미지정 → 모두 None 으로 repos 에 전달 (기존 값 유지 의도)."""
    captured = _patch_upsert(monkeypatch)
    mcp_module.save_daily_report("005930", "2026-05-05", "중립", "본문")
    kw = captured["kwargs"]
    assert kw["size_pct"] is None
    assert kw["stop_method"] is None
    assert kw["stop_value"] is None
    assert kw["override_dimensions"] is None
    assert kw["key_factors"] is None
    assert kw["referenced_rules"] is None


def test_save_daily_report_empty_content_chars_zero(monkeypatch):
    """빈 content 도 정상 처리 — chars=0."""
    _patch_upsert(monkeypatch)
    out = mcp_module.save_daily_report("005930", "2026-05-05", "중립", "")
    assert out["ok"] is True
    assert out["chars"] == 0


# ---------------------------------------------------------------------------
# save_portfolio_summary
# ---------------------------------------------------------------------------


def _patch_save(monkeypatch) -> dict:
    """portfolio_snapshots.save 호출 인자를 captured dict 로 수집."""
    captured: dict = {}

    def fake_save(uid, d, **kwargs):
        captured["uid"] = uid
        captured["date"] = d
        captured["kwargs"] = kwargs

    monkeypatch.setattr(mcp_module.portfolio_snapshots, "save", fake_save)
    return captured


def test_save_portfolio_summary_returns_ok_envelope(monkeypatch):
    """정상 호출 → {ok, date, action_count, stock_count, risk_count} 5 키 응답."""
    _patch_save(monkeypatch)
    out = mcp_module.save_portfolio_summary(
        "2026-05-05",
        per_stock_summary=[{"code": "005930"}, {"code": "AAPL"}],
        risk_flags=[{"type": "concentration"}],
        action_plan=[{"priority": 1, "code": "005930", "action": "buy"}],
        headline="오늘은 매수 우세",
        summary_content="본문 마크다운",
    )
    assert out["ok"] is True
    assert out["date"] == "2026-05-05"
    assert out["stock_count"] == 2
    assert out["risk_count"] == 1
    assert out["action_count"] == 1


def test_save_portfolio_summary_none_lists_count_zero(monkeypatch):
    """None 리스트 인자 → 카운트 0 (len(None or []) 패턴)."""
    _patch_save(monkeypatch)
    out = mcp_module.save_portfolio_summary(
        "2026-05-05",
        per_stock_summary=None,
        risk_flags=None,
        action_plan=None,
    )
    assert out["stock_count"] == 0
    assert out["risk_count"] == 0
    assert out["action_count"] == 0


def test_save_portfolio_summary_empty_lists_count_zero(monkeypatch):
    """빈 리스트 → 카운트 0."""
    _patch_save(monkeypatch)
    out = mcp_module.save_portfolio_summary(
        "2026-05-05",
        per_stock_summary=[],
        risk_flags=[],
        action_plan=[],
    )
    assert out["stock_count"] == 0
    assert out["risk_count"] == 0
    assert out["action_count"] == 0


def test_save_portfolio_summary_invalid_date_raises(monkeypatch):
    """ISO 형식 아닌 date → ValueError."""
    _patch_save(monkeypatch)
    with pytest.raises(ValueError):
        mcp_module.save_portfolio_summary("2026/05/05")


def test_save_portfolio_summary_passes_all_args_to_repos(monkeypatch):
    """모든 인자가 repos.portfolio_snapshots.save 에 정확히 전달."""
    captured = _patch_save(monkeypatch)
    per_stock = [{"code": "005930", "verdict": "강한매수"}]
    risks = [{"type": "concentration", "level": "warn"}]
    actions = [{"priority": 1, "code": "005930", "action": "buy"}]
    mcp_module.save_portfolio_summary(
        "2026-05-05",
        per_stock_summary=per_stock,
        risk_flags=risks,
        action_plan=actions,
        headline="헤드라인",
        summary_content="본문",
    )
    from datetime import date as date_cls

    assert captured["date"] == date_cls(2026, 5, 5)
    assert captured["uid"] is not None
    kw = captured["kwargs"]
    assert kw["per_stock_summary"] == per_stock
    assert kw["risk_flags"] == risks
    assert kw["action_plan"] == actions
    assert kw["headline"] == "헤드라인"
    assert kw["summary_content"] == "본문"


def test_save_portfolio_summary_minimal_args_defaults(monkeypatch):
    """date 만 넘겨도 정상 동작 — 모든 선택 인자 None default."""
    captured = _patch_save(monkeypatch)
    out = mcp_module.save_portfolio_summary("2026-05-05")
    assert out["ok"] is True
    assert out["stock_count"] == 0
    assert out["risk_count"] == 0
    assert out["action_count"] == 0
    kw = captured["kwargs"]
    assert kw["per_stock_summary"] is None
    assert kw["risk_flags"] is None
    assert kw["action_plan"] is None
    assert kw["headline"] is None
    assert kw["summary_content"] is None
