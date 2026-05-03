"""WebSearch 호출 카운트 집계 스크립트.

LLM 이 stock/economy_base/industry_base/stock_base/macro 워크플로우에서
WebSearch 를 호출할 때마다 ``agent/_search_log.jsonl`` 에 1줄씩 append 하면,
이 스크립트가 일별/스코프별/트리거별 분포 + 캐시 비율 + baseline 감축률을 출력한다.

운영 시점은 stock skill v8.b — 그 이전엔 baseline (17~50회/일, 추정) 만 존재.

JSONL 1줄 schema (필드 전부 필수)::

    {
      "date":           "YYYY-MM-DD",                     // ISO 날짜
      "timestamp":      "YYYY-MM-DDTHH:MM:SS+09:00",      // ISO 8601
      "scope":          "stock" | "economy_base" | "industry_base" | "stock_base" | "macro",
      "code_or_market": "005930" | "kr" | "us" | "semiconductor" | "global",
      "trigger":        "manual" | "stale_disclosures_empty" | "stale_in_industry_5dim"
                        | "earnings_d7" | "52w_break" | ...,
      "query":          "<실제 WebSearch 쿼리 문자열>",
      "cached":         true | false                      // 같은 분 내 동일 query 재사용 여부
    }

사용 예::

    python scripts/measure_websearch.py                                  # default 7d, by=scope
    python scripts/measure_websearch.py --days 14 --by trigger
    python scripts/measure_websearch.py --input some/other/path.jsonl

외부 라이브러리 의존성 없음 — Python stdlib (argparse + json + collections + datetime) 만 사용.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

DEFAULT_INPUT = "agent/_search_log.jsonl"
DEFAULT_DAYS = 7
DEFAULT_BY = "scope"

#: stock skill 도입 전 추정 baseline (회/일). plan 문서 v8.b 기준.
BASELINE_LOW = 17
BASELINE_HIGH = 50

REQUIRED_FIELDS = ("date", "timestamp", "scope", "code_or_market", "trigger", "query", "cached")

VALID_SCOPES = {"stock", "economy_base", "industry_base", "stock_base", "macro"}


# ---------------------------------------------------------------------------
# 파싱
# ---------------------------------------------------------------------------


def parse_log(path: Path) -> tuple[list[dict[str, Any]], int]:
    """JSONL 파일을 읽어 row list + 스킵된 (malformed) 라인 수를 반환."""
    rows: list[dict[str, Any]] = []
    skipped = 0
    if not path.exists():
        return rows, skipped
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(obj, dict):
                skipped += 1
                continue
            if not all(k in obj for k in REQUIRED_FIELDS):
                skipped += 1
                continue
            rows.append(obj)
    return rows, skipped


def _row_date(row: dict[str, Any]) -> date | None:
    """row['date'] 를 ``date`` 로 파싱. 실패 시 None."""
    try:
        return datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
    except (ValueError, KeyError):
        return None


def filter_recent(rows: Iterable[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    """가장 최근 date 를 anchor 로 마지막 ``days`` 일 (inclusive) 의 row 만 남긴다.

    today 기반이 아니라 log 내 max(date) 기반 — 오프라인/지연 로그도 결정적으로 처리.
    """
    parsed: list[tuple[date, dict[str, Any]]] = []
    for row in rows:
        d = _row_date(row)
        if d is None:
            continue
        parsed.append((d, row))
    if not parsed:
        return []
    anchor = max(d for d, _ in parsed)
    cutoff = anchor - timedelta(days=days - 1)
    return [row for d, row in parsed if cutoff <= d <= anchor]


# ---------------------------------------------------------------------------
# 집계
# ---------------------------------------------------------------------------


def aggregate_by_date(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row["date"])] += 1
    return dict(sorted(counter.items()))


def aggregate_by_field(rows: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get(field, "<missing>"))] += 1
    return dict(counter.most_common())


def cached_ratio(rows: list[dict[str, Any]]) -> float:
    """cached=True 비율 (0.0 ~ 1.0). row 가 없으면 0.0."""
    if not rows:
        return 0.0
    hits = sum(1 for r in rows if bool(r.get("cached")))
    return hits / len(rows)


def avg_daily(rows: list[dict[str, Any]], days: int) -> float:
    """``days`` 윈도 기준 평균 호출 수 (총합 / days). days <= 0 이면 0.0."""
    if days <= 0:
        return 0.0
    return len(rows) / days


def reduction_rate(avg: float, baseline: float) -> float:
    """baseline 대비 감축률 (양수=감소, 음수=baseline 초과). baseline<=0 이면 0.0."""
    if baseline <= 0:
        return 0.0
    return (baseline - avg) / baseline


# ---------------------------------------------------------------------------
# 리포트 포매팅
# ---------------------------------------------------------------------------


def _format_table(title: str, mapping: dict[str, int], total: int) -> list[str]:
    if not mapping:
        return [f"## {title}", "  (empty)", ""]
    lines = [f"## {title}"]
    width = max(len(k) for k in mapping)
    for k, v in mapping.items():
        pct = (v / total * 100) if total else 0.0
        lines.append(f"  {k.ljust(width)}  {v:>4}  ({pct:5.1f}%)")
    lines.append("")
    return lines


def format_report(
    rows: list[dict[str, Any]],
    days: int,
    by: str,
    skipped: int,
    input_path: Path,
) -> str:
    by_date = aggregate_by_date(rows)
    by_field = aggregate_by_field(rows, by)
    total = len(rows)
    avg = avg_daily(rows, days)
    cached_pct = cached_ratio(rows) * 100
    red_low = reduction_rate(avg, BASELINE_LOW) * 100
    red_high = reduction_rate(avg, BASELINE_HIGH) * 100

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("WebSearch 호출 집계")
    lines.append("=" * 60)
    lines.append(f"input  : {input_path}")
    lines.append(f"window : last {days} day(s) (anchor = max(date) in log)")
    lines.append(f"rows   : {total}  (skipped malformed: {skipped})")
    lines.append(f"avg/day: {avg:.2f}")
    lines.append(f"cached : {cached_pct:.1f}%")
    lines.append("")
    lines.append("## Baseline 비교 (운영 전 추정 17~50회/일)")
    lines.append(f"  vs {BASELINE_LOW:>2}/day  →  reduction { red_low:+6.1f}%")
    lines.append(f"  vs {BASELINE_HIGH:>2}/day  →  reduction { red_high:+6.1f}%")
    lines.append("")
    lines.extend(_format_table("일별 호출 수", by_date, total))
    lines.extend(_format_table(f"{by} 별 분포", by_field, total))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="measure_websearch",
        description="WebSearch 호출 로그 (_search_log.jsonl) 집계.",
    )
    p.add_argument("--input", default=DEFAULT_INPUT, help=f"jsonl 경로 (default: {DEFAULT_INPUT})")
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"집계 윈도 (일, default: {DEFAULT_DAYS})",
    )
    p.add_argument(
        "--by",
        choices=("scope", "trigger"),
        default=DEFAULT_BY,
        help=f"분포 표 그룹키 (default: {DEFAULT_BY})",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.days <= 0:
        print("error: --days must be a positive integer", file=sys.stderr)
        return 2
    path = Path(args.input)
    rows, skipped = parse_log(path)
    if not path.exists():
        print(f"warn: {path} not found — empty report", file=sys.stderr)
    windowed = filter_recent(rows, args.days)
    print(format_report(windowed, args.days, args.by, skipped, path))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
