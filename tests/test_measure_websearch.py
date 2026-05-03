"""scripts/measure_websearch.py 집계 검증.

실행: ``pytest tests/test_measure_websearch.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import measure_websearch as m  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _row(date: str, scope: str, trigger: str, cached: bool = False, **extra) -> dict:
    base = {
        "date": date,
        "timestamp": f"{date}T09:30:00+09:00",
        "scope": scope,
        "code_or_market": extra.pop("code_or_market", "kr"),
        "trigger": trigger,
        "query": extra.pop("query", "test query"),
        "cached": cached,
    }
    base.update(extra)
    return base


@pytest.fixture
def synthetic_rows() -> list[dict]:
    # 7개 row, 3개 날짜, 3개 scope, 2개 trigger, cached 2개
    return [
        _row("2026-05-01", "stock", "manual", cached=False),
        _row("2026-05-01", "stock", "earnings_d7", cached=True),
        _row("2026-05-02", "economy_base", "manual", cached=False),
        _row("2026-05-02", "industry_base", "stale_in_industry_5dim", cached=False),
        _row("2026-05-02", "stock", "52w_break", cached=True),
        _row("2026-05-03", "stock_base", "stale_disclosures_empty", cached=False),
        _row("2026-05-03", "macro", "manual", cached=False),
    ]


@pytest.fixture
def jsonl_file(tmp_path: Path, synthetic_rows: list[dict]) -> Path:
    path = tmp_path / "log.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for row in synthetic_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# parse_log
# ---------------------------------------------------------------------------


def test_parse_log_reads_all_rows(jsonl_file: Path):
    rows, skipped = m.parse_log(jsonl_file)
    assert len(rows) == 7
    assert skipped == 0


def test_parse_log_skips_malformed(tmp_path: Path):
    path = tmp_path / "broken.jsonl"
    good = json.dumps(
        {
            "date": "2026-05-01",
            "timestamp": "2026-05-01T09:00:00+09:00",
            "scope": "stock",
            "code_or_market": "005930",
            "trigger": "manual",
            "query": "q",
            "cached": False,
        }
    )
    path.write_text(
        "\n".join([good, "{not json", json.dumps({"missing": "fields"}), "", good]) + "\n",
        encoding="utf-8",
    )
    rows, skipped = m.parse_log(path)
    assert len(rows) == 2
    assert skipped == 2  # invalid JSON + missing-field row (blank line is just skipped)


def test_parse_log_missing_file(tmp_path: Path):
    rows, skipped = m.parse_log(tmp_path / "nope.jsonl")
    assert rows == []
    assert skipped == 0


# ---------------------------------------------------------------------------
# filter_recent
# ---------------------------------------------------------------------------


def test_filter_recent_window_inclusive(synthetic_rows: list[dict]):
    # max date = 2026-05-03; days=2 → keep 05-02 and 05-03
    out = m.filter_recent(synthetic_rows, days=2)
    assert {r["date"] for r in out} == {"2026-05-02", "2026-05-03"}
    assert len(out) == 5


def test_filter_recent_full_window(synthetic_rows: list[dict]):
    out = m.filter_recent(synthetic_rows, days=7)
    assert len(out) == 7


def test_filter_recent_empty():
    assert m.filter_recent([], days=7) == []


# ---------------------------------------------------------------------------
# 집계
# ---------------------------------------------------------------------------


def test_aggregate_by_date(synthetic_rows: list[dict]):
    out = m.aggregate_by_date(synthetic_rows)
    assert out == {"2026-05-01": 2, "2026-05-02": 3, "2026-05-03": 2}
    assert list(out.keys()) == sorted(out.keys())  # 정렬 보장


def test_aggregate_by_scope(synthetic_rows: list[dict]):
    out = m.aggregate_by_field(synthetic_rows, "scope")
    assert out["stock"] == 3
    assert out["economy_base"] == 1
    assert out["industry_base"] == 1
    assert out["stock_base"] == 1
    assert out["macro"] == 1
    assert sum(out.values()) == 7


def test_aggregate_by_trigger(synthetic_rows: list[dict]):
    out = m.aggregate_by_field(synthetic_rows, "trigger")
    assert out["manual"] == 3
    assert out["earnings_d7"] == 1
    assert out["52w_break"] == 1
    assert sum(out.values()) == 7


def test_cached_ratio(synthetic_rows: list[dict]):
    # 2 of 7
    assert m.cached_ratio(synthetic_rows) == pytest.approx(2 / 7)


def test_cached_ratio_empty():
    assert m.cached_ratio([]) == 0.0


def test_avg_daily(synthetic_rows: list[dict]):
    assert m.avg_daily(synthetic_rows, days=7) == pytest.approx(1.0)
    assert m.avg_daily(synthetic_rows, days=1) == pytest.approx(7.0)
    assert m.avg_daily([], days=7) == 0.0
    assert m.avg_daily(synthetic_rows, days=0) == 0.0


def test_reduction_rate():
    # baseline 50, avg 25 → 50% 감축
    assert m.reduction_rate(25.0, 50.0) == pytest.approx(0.5)
    # baseline 17, avg 17 → 0%
    assert m.reduction_rate(17.0, 17.0) == pytest.approx(0.0)
    # baseline 17, avg 34 → -100% (baseline 초과)
    assert m.reduction_rate(34.0, 17.0) == pytest.approx(-1.0)
    assert m.reduction_rate(10.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# 리포트 / CLI
# ---------------------------------------------------------------------------


def test_format_report_contains_sections(synthetic_rows: list[dict]):
    out = m.format_report(synthetic_rows, days=7, by="scope", skipped=0, input_path=Path("x.jsonl"))
    assert "WebSearch 호출 집계" in out
    assert "일별 호출 수" in out
    assert "scope 별 분포" in out
    assert "Baseline 비교" in out
    assert "2026-05-01" in out
    assert "stock" in out


def test_main_smoke(jsonl_file: Path, capsys):
    rc = m.main(["--input", str(jsonl_file), "--days", "7", "--by", "trigger"])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "trigger 별 분포" in captured
    assert "manual" in captured
    assert "rows   : 7" in captured


def test_main_rejects_bad_days(tmp_path: Path, capsys):
    rc = m.main(["--input", str(tmp_path / "x.jsonl"), "--days", "0"])
    assert rc == 2
