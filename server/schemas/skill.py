"""스킬 매뉴얼 (~/.claude/skills/*/SKILL.md) 응답 스키마."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SkillName = Literal[
    "stock",
    "stock-research",
    "stock-daily",
    "stock-discover",
    "base-economy",
    "base-industry",
    "base-stock",
    "stock-momentum",  # DEPRECATED (v17, 2026-04-27) — stock-research 의 모멘텀 차원으로 흡수
]

SKILL_NAMES: tuple[SkillName, ...] = (
    "stock",
    "stock-daily",
    "stock-research",
    "stock-discover",
    "base-economy",
    "base-industry",
    "base-stock",
    "stock-momentum",
)


class SkillListItem(BaseModel):
    name: SkillName
    title: str | None = None  # 첫 H1 추출
    summary: str | None = None  # 첫 단락 (옵션)
    updated_at: datetime | None = None
    bytes: int = 0


class SkillListOut(BaseModel):
    skills: list[SkillListItem] = Field(default_factory=list)


class SkillContentOut(BaseModel):
    name: SkillName
    title: str | None = None
    content: str
    updated_at: datetime | None = None
