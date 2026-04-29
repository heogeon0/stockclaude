"""/skills 라우터 — ~/.claude/skills/*/SKILL.md 라이브 렌더."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server.api.deps import require_google_user
from server.config import settings
from server.schemas.skill import (
    SKILL_NAMES,
    SkillContentOut,
    SkillListItem,
    SkillListOut,
    SkillName,
)

router = APIRouter(prefix="/skills", tags=["skills"], dependencies=[Depends(require_google_user)])

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@router.get("", response_model=SkillListOut)
def list_skills() -> SkillListOut:
    items: list[SkillListItem] = []
    for name in SKILL_NAMES:
        path = _skill_path(name)
        if not path.exists():
            items.append(SkillListItem(name=name, bytes=0))
            continue
        text = path.read_text(encoding="utf-8")
        items.append(
            SkillListItem(
                name=name,
                title=_extract_title(text),
                summary=_extract_summary(text),
                updated_at=_mtime(path),
                bytes=len(text.encode("utf-8")),
            )
        )
    return SkillListOut(skills=items)


@router.get("/{name}", response_model=SkillContentOut)
def get_skill(name: SkillName) -> SkillContentOut:
    """name 은 Literal 로 강제 — path traversal 차단."""
    path = _skill_path(name)
    if not path.exists():
        raise HTTPException(404, f"SKILL.md not found: {name}")
    text = path.read_text(encoding="utf-8")
    return SkillContentOut(
        name=name,
        title=_extract_title(text),
        content=text,
        updated_at=_mtime(path),
    )


def _skill_path(name: SkillName) -> Path:
    return settings.skills_dir / name / "SKILL.md"


def _extract_title(text: str) -> str | None:
    m = H1_RE.search(text)
    return m.group(1) if m else None


def _extract_summary(text: str) -> str | None:
    """첫 H1 다음의 첫 비어있지 않은 단락 첫 줄."""
    body = H1_RE.split(text, maxsplit=1)
    if len(body) < 3:
        return None
    after_h1 = body[2]
    for line in after_h1.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:160]
    return None


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
