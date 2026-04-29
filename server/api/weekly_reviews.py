"""/weekly-reviews 라우터 — 주간 회고 목록·단건·rolling context."""

from __future__ import annotations

from datetime import date as date_cls, datetime
from zoneinfo import ZoneInfo
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from server.api.deps import require_api_key
from server.repos import weekly_reviews as wr
from server.schemas.weekly_review import (
    WeeklyContextLatest,
    WeeklyContextOut,
    WeeklyReviewListItem,
    WeeklyReviewListOut,
    WeeklyReviewOut,
    WeeklyRollingStats,
)

router = APIRouter(
    prefix="/weekly-reviews",
    tags=["weekly-reviews"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=WeeklyReviewListOut)
def list_weekly_reviews(limit: int = 12) -> WeeklyReviewListOut:
    rows = wr.list_reviews(limit=limit)
    items = [
        WeeklyReviewListItem(
            week_start=r["week_start"],
            week_end=r["week_end"],
            trade_count=r.get("trade_count") or 0,
            realized_pnl_kr=r.get("realized_pnl_kr"),
            realized_pnl_us=r.get("realized_pnl_us"),
            unrealized_pnl_kr=r.get("unrealized_pnl_kr"),
            unrealized_pnl_us=r.get("unrealized_pnl_us"),
            headline=r.get("headline"),
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return WeeklyReviewListOut(reviews=items, count=len(items))


@router.get("/latest", response_model=WeeklyReviewOut | None)
def get_latest_weekly_review() -> WeeklyReviewOut | None:
    rows = wr.list_reviews(limit=1)
    if not rows:
        return None
    full = wr.get_review(rows[0]["week_start"])
    if full is None:
        return None
    return _to_full_out(full)


@router.get("/context", response_model=WeeklyContextOut)
def get_weekly_context(weeks: int = 4) -> WeeklyContextOut:
    """`get_weekly_context` MCP 툴과 동일 로직 — rolling rule_win_rates + carryover."""
    rows = wr.list_reviews(limit=max(weeks, 1))
    if not rows:
        return WeeklyContextOut(
            latest_review=None,
            rolling_stats=WeeklyRollingStats(weeks_count=0),
            carryover_actions=[],
        )

    latest_meta = rows[0]
    latest_full = wr.get_review(latest_meta["week_start"])

    # pending_actions (latest)
    pending_actions: list[dict[str, Any]] = []
    if latest_full:
        for a in (latest_full.get("next_week_actions") or []):
            status = a.get("status", "")
            if status not in ("pending", "conditional"):
                continue
            exp = a.get("expires_at")
            if exp:
                try:
                    exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                    if exp_dt > datetime.now(ZoneInfo("UTC")):
                        pending_actions.append(a)
                except Exception:
                    pending_actions.append(a)
            else:
                pending_actions.append(a)

    # rolling stats
    rule_wins: dict[str, dict[str, Any]] = {}
    total_realized_kr = 0.0
    total_trades = 0
    full_reviews: list[dict[str, Any]] = []

    for meta in rows[:weeks]:
        full = wr.get_review(meta["week_start"])
        if not full:
            continue
        full_reviews.append(full)

        rk = full.get("realized_pnl_kr")
        if rk is not None:
            total_realized_kr += float(rk)

        tc = full.get("trade_count")
        if tc:
            total_trades += int(tc)

        wr_dict = full.get("win_rate") or {}
        for rule, stats in wr_dict.items():
            if not isinstance(stats, dict):
                continue
            agg = rule_wins.setdefault(rule, {"tries": 0, "wins": 0})
            agg["tries"] += int(stats.get("tries", 0) or 0)
            agg["wins"] += int(stats.get("wins", 0) or 0)

    for _rule, agg in rule_wins.items():
        agg["pct"] = round(agg["wins"] / agg["tries"] * 100, 1) if agg["tries"] > 0 else 0.0

    # carryover (전 주 conditional)
    carryover: list[dict[str, Any]] = []
    now_utc = datetime.now(ZoneInfo("UTC"))
    for full in full_reviews[1:]:
        for a in (full.get("next_week_actions") or []):
            status = a.get("status", "")
            if status not in ("pending", "conditional"):
                continue
            exp = a.get("expires_at")
            if not exp:
                continue
            try:
                exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                if exp_dt > now_utc:
                    carryover.append({**a, "from_week": str(full.get("week_start"))})
            except Exception:
                continue

    latest_section: WeeklyContextLatest | None = None
    if latest_full is not None:
        latest_section = WeeklyContextLatest(
            week_start=latest_full.get("week_start"),
            week_end=latest_full.get("week_end"),
            headline=latest_full.get("headline"),
            highlights=latest_full.get("highlights") or [],
            pending_actions=pending_actions,
        )

    return WeeklyContextOut(
        latest_review=latest_section,
        rolling_stats=WeeklyRollingStats(
            weeks_count=len(full_reviews),
            rule_win_rates=rule_wins,
            total_realized_pnl_kr=round(total_realized_kr, 2),
            avg_weekly_pnl_kr=round(total_realized_kr / max(len(full_reviews), 1), 2),
            trade_count_total=total_trades,
        ),
        carryover_actions=carryover,
    )


@router.get("/{week_start}", response_model=WeeklyReviewOut)
def get_weekly_review(week_start: date_cls) -> WeeklyReviewOut:
    full = wr.get_review(week_start)
    if full is None:
        raise HTTPException(status_code=404, detail=f"weekly_review not found: {week_start}")
    return _to_full_out(full)


def _to_full_out(row: dict[str, Any]) -> WeeklyReviewOut:
    return WeeklyReviewOut(
        week_start=row["week_start"],
        week_end=row["week_end"],
        trade_count=row.get("trade_count") or 0,
        realized_pnl_kr=row.get("realized_pnl_kr"),
        realized_pnl_us=row.get("realized_pnl_us"),
        unrealized_pnl_kr=row.get("unrealized_pnl_kr"),
        unrealized_pnl_us=row.get("unrealized_pnl_us"),
        win_rate=row.get("win_rate") or {},
        rule_evaluations=row.get("rule_evaluations") or [],
        highlights=row.get("highlights") or [],
        next_week_actions=row.get("next_week_actions") or [],
        headline=row.get("headline"),
        content=row.get("content"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
