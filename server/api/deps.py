"""API 공통 의존성 (인증, 현재 유저)."""

from __future__ import annotations

from uuid import UUID

from fastapi import Header, HTTPException, status

from server.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """간단한 API key 헤더 인증.
    운영: X-API-Key 헤더 필수. Phase 4 이후 JWT·OAuth 로 확장.
    """
    if settings.is_production and (x_api_key is None or x_api_key != settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-API-Key",
        )
    # 개발 모드는 통과 (로컬 편의)


def current_user_id() -> UUID:
    """SaaS 이전에는 환경변수로 단일 유저. JWT 이후는 토큰 클레임에서 추출."""
    return settings.default_user_id
