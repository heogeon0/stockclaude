"""
애널 컨센서스 추이 분석.
repos.analyst.list_recent() 결과를 입력으로 rating momentum·beat history 산출.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean, pstdev


def _to_dt(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except ValueError:
        return None


def target_price_trend(reports: list[dict], days_current: int = 30, days_prev: int = 60) -> dict:
    """
    최근 N일 평균 목표가 vs 이전 N일 평균 비교.
    reports: analyst.list_recent() 결과 (published_at DESC).
    """
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
    now = datetime.now(tz=KST)
    current_cut = now - timedelta(days=days_current)
    prev_cut = now - timedelta(days=days_prev)

    current_targets = []
    prev_targets = []
    for r in reports:
        pub = _to_dt(r.get("published_at"))
        tgt = r.get("target_price")
        if pub is None or tgt is None:
            continue
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=KST)
        tgt_f = float(tgt)
        if pub > current_cut:
            current_targets.append(tgt_f)
        elif pub > prev_cut:
            prev_targets.append(tgt_f)

    curr_avg = mean(current_targets) if current_targets else None
    prev_avg = mean(prev_targets) if prev_targets else None

    if curr_avg and prev_avg and prev_avg > 0:
        momentum_pct = round((curr_avg - prev_avg) / prev_avg * 100, 2)
        if momentum_pct > 5:
            direction = "strongly_up"
        elif momentum_pct > 0:
            direction = "up"
        elif momentum_pct > -5:
            direction = "down"
        else:
            direction = "strongly_down"
    else:
        momentum_pct = None
        direction = "unknown"

    return {
        "current_avg": round(curr_avg, 2) if curr_avg else None,
        "prev_avg": round(prev_avg, 2) if prev_avg else None,
        "count_current": len(current_targets),
        "count_prev": len(prev_targets),
        "momentum_pct": momentum_pct,
        "direction": direction,
        "dispersion": round(pstdev(current_targets) / curr_avg * 100, 2)
        if curr_avg and len(current_targets) >= 2 else None,
    }


def rating_wave(reports: list[dict], days: int = 30) -> dict:
    """최근 N일 upgrade vs downgrade 카운트."""
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
    cut = datetime.now(tz=KST) - timedelta(days=days)
    up, down, init, reit = 0, 0, 0, 0
    for r in reports:
        pub = _to_dt(r.get("published_at"))
        if pub is None:
            continue
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=KST)
        if pub < cut:
            continue
        rc = r.get("rating_change")
        if rc == "upgrade":
            up += 1
        elif rc == "downgrade":
            down += 1
        elif rc == "initiate":
            init += 1
        elif rc == "reiterate":
            reit += 1

    net = up + init - down
    if net >= 3:
        sentiment = "strongly_bullish"
    elif net >= 1:
        sentiment = "bullish"
    elif net <= -3:
        sentiment = "strongly_bearish"
    elif net <= -1:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "upgrades": up,
        "downgrades": down,
        "initiations": init,
        "reiterations": reit,
        "net": net,
        "sentiment": sentiment,
    }


def beat_history(surprise_history: list[dict]) -> dict:
    """
    surprise_history: [{quarter, actual, consensus, surprise_pct}, ...]
    """
    if not surprise_history:
        return {"beat_rate": None, "avg_surprise": None}

    beats = sum(1 for s in surprise_history if (s.get("surprise_pct") or 0) > 3)
    misses = sum(1 for s in surprise_history if (s.get("surprise_pct") or 0) < -3)
    inlines = len(surprise_history) - beats - misses

    avg_surprise = mean(s["surprise_pct"] for s in surprise_history if s.get("surprise_pct") is not None)

    return {
        "quarters": len(surprise_history),
        "beats": beats,
        "misses": misses,
        "inlines": inlines,
        "beat_rate": round(beats / len(surprise_history) * 100, 1),
        "avg_surprise_pct": round(avg_surprise, 2),
    }
