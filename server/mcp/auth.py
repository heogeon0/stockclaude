"""MCP OAuth 인증 — Google IdP + 이메일 화이트리스트.

- FastMCP 3.2 의 `GoogleProvider` 가 OAuth Proxy 역할.
  Discovery (`/.well-known/oauth-authorization-server`), `/authorize`, `/token`
  엔드포인트를 자동으로 노출하고, 업스트림은 Google.
- `GoogleTokenVerifier` 위에 `_AllowedEmailGoogleVerifier` 를 얹어
  토큰의 `email` 클레임이 `ALLOWED_EMAILS` 안에 있는지 추가 검증.
- 1인 (또는 화이트리스트 멀티유저) 운영 전제. v24+ 오픈가입 시 제거.

기능:
- streamable-http 모드일 때만 활성화 (stdio 모드는 auth=None).
- Claude 클라이언트 콜백 URL (claude.ai/api/mcp/auth_callback,
  claude.ai/api/auth/callback) 을 화이트리스트에 사전 등록.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.providers.google import GoogleProvider, GoogleTokenVerifier
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


# Claude 가 OAuth flow 완료 후 콜백할 URL — claude.ai 측 고정값.
# 신규 클라이언트가 등장하면 여기 추가.
CLAUDE_REDIRECT_URIS = [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.ai/api/auth/callback",
]


class _AllowedEmailGoogleVerifier(GoogleTokenVerifier):
    """`email` 클레임을 화이트리스트와 대조하는 GoogleTokenVerifier 래퍼.

    - 빈 화이트리스트 = 모두 거부 (보안 기본값).
    - 미일치/미존재 시 `None` 반환 → FastMCP 가 401 처리.
    """

    def __init__(self, *, allowed_emails: Iterable[str], **kwargs):
        super().__init__(**kwargs)
        self._allowed: frozenset[str] = frozenset(
            e.strip().lower() for e in allowed_emails if e and e.strip()
        )
        if not self._allowed:
            logger.warning(
                "ALLOWED_EMAILS 비어있음 — 모든 토큰 거부. "
                "환경변수에 허용 이메일 콤마 분리로 등록 필요."
            )

    async def verify_token(self, token: str) -> AccessToken | None:
        access = await super().verify_token(token)
        if access is None:
            return None
        email = (access.claims.get("email") or "").lower()
        if not email:
            logger.warning("Google 토큰에 email 클레임 없음 — 거부")
            return None
        if email not in self._allowed:
            logger.warning("화이트리스트 외 이메일 거부: %s", email)
            return None
        return access


def build_google_oauth_provider(
    *,
    client_id: str,
    client_secret: str,
    base_url: str,
    allowed_emails: Iterable[str],
) -> GoogleProvider:
    """GoogleProvider 인스턴스 생성 + 이메일 화이트리스트 verifier 주입.

    GoogleProvider 내부에서 token_verifier 를 만들어 OAuthProxy 에 전달하므로,
    super().__init__ 후 `_token_validator` 를 우리 wrapper 로 교체하는 패턴.
    (FastMCP 3.2.4 에서 `OAuthProxy._token_validator` 가 `verify_token` 호출 진입점.)

    Args:
        client_id: Google OAuth Client ID
        client_secret: Google OAuth Client Secret
        base_url: 원격 MCP 의 public URL (예: https://stock-mcp.up.railway.app).
            OAuth Discovery 엔드포인트의 issuer 로 사용됨.
        allowed_emails: 접근 허용 이메일 (소문자 정규화).

    Returns:
        FastMCP `auth=` 인자에 그대로 넘길 수 있는 GoogleProvider.
    """
    provider = GoogleProvider(
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        # email scope 필수 — 토큰의 email 클레임으로 화이트리스트 검증
        required_scopes=["openid", "email"],
        allowed_client_redirect_uris=CLAUDE_REDIRECT_URIS,
    )

    # GoogleProvider 가 만든 verifier 의 설정을 승계해서 wrapper 로 교체
    original_verifier = provider._token_validator  # type: ignore[attr-defined]
    provider._token_validator = _AllowedEmailGoogleVerifier(  # type: ignore[attr-defined]
        allowed_emails=allowed_emails,
        required_scopes=original_verifier.required_scopes,
    )
    return provider
