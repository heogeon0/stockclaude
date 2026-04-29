"""API 공통 의존성 (인증, 현재 유저).

운영 모델:
- 웹 (Vercel) → Google Sign-In → ID token (JWT) 발급
- 웹 → FastAPI 호출 시 `Authorization: Bearer <id_token>` 헤더 첨부
- FastAPI 가 `verify_google_id_token` 으로 검증 + ALLOWED_EMAILS 화이트리스트 통과 확인
- 통과 시 email 반환, 실패 시 401

로컬 개발:
- APP_ENV != production 이면 토큰 없이 통과 (dev 편의)
- 운영 배포에선 반드시 토큰 검증
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token as g_id_token

from server.config import settings
from server.repos import users as users_repo

# Google ID token issuer 후보 (둘 다 유효)
_GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

# google-auth 가 매 호출마다 새 Request 만들지 않도록 모듈 레벨에 1개 보유
_g_request = g_requests.Request()


def verify_google_id_token(token: str) -> str | None:
    """Google ID token (JWT) 검증 → email 반환.

    검증 항목:
    - 서명 (Google JWKS)
    - aud (= settings.google_client_id)
    - iss (accounts.google.com)
    - 만료 시간

    Returns:
        검증 통과 시 email 문자열, 실패 시 None.
    """
    if not settings.google_client_id:
        return None
    try:
        idinfo = g_id_token.verify_oauth2_token(
            token,
            _g_request,
            settings.google_client_id,
        )
    except (ValueError, Exception):
        return None
    if idinfo.get("iss") not in _GOOGLE_ISSUERS:
        return None
    email = idinfo.get("email")
    if not email or not idinfo.get("email_verified"):
        return None
    return str(email).lower()


def require_google_user(authorization: str | None = Header(default=None)) -> str:
    """Authorization: Bearer <google_id_token> 검증 + ALLOWED_EMAILS 화이트리스트.

    - 개발 모드 (APP_ENV != production) + 토큰 없음 → "dev@localhost" 반환 (로컬 편의).
    - 그 외엔 토큰 필수. 미일치 시 401.
    """
    # 로컬 개발 편의: 토큰 없으면 더미 통과
    if not settings.is_production and not authorization:
        return "dev@localhost"

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    email = verify_google_id_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid Google ID token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    allowed = {e.lower() for e in settings.allowed_emails_list}
    if not allowed or email not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="email not in ALLOWED_EMAILS",
        )
    return email


def current_user_id(email: str = Depends(require_google_user)) -> UUID:
    """OAuth 검증 통과 email → DB users 테이블에서 user_id lookup.

    - 검증된 email (heo3793@gmail.com 등) → DB row 조회.
    - 처음 보이는 email 이면 자동 생성 (ALLOWED_EMAILS 통과한 신뢰 가능 사용자).
    - dev 모드 토큰 우회 (`dev@localhost`) → settings.stock_user_id (singleton fallback).

    멀티유저 확장 시 이 함수만 그대로 두면 됨 — 각 email 이 별도 user_id 갖게 됨.
    """
    if email == "dev@localhost":
        return settings.stock_user_id
    return users_repo.get_or_create_by_email(email)
