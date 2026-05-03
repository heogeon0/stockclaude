"""
환경변수 로딩. 다른 모든 모듈이 `from server.config import settings` 로 접근.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    # 운영 사용자 UUID. 1인 운영 전제 + dev 모드 fallback.
    # FastAPI 는 v21c 부터 OAuth email → DB user_id lookup 으로 동작 (이 값은 dev/MCP 용).
    # `STOCK_USER_ID` (정식) 또는 `DEFAULT_USER_ID` (legacy) 둘 다 인식.
    stock_user_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000000"),
        validation_alias=AliasChoices("stock_user_id", "default_user_id"),
    )
    api_key: str = "local-dev"

    @property
    def default_user_id(self) -> UUID:
        """legacy alias — 새 코드는 `settings.stock_user_id` 사용."""
        return self.stock_user_id

    # Database
    database_url: str

    # ---- MCP transport / auth ----
    # stdio: 로컬 Claude Code 가 자식 프로세스로 spawn (default).
    # streamable-http: Railway 등 원격 배포용. Google OAuth 자동 활성화.
    stock_mcp_transport: str = "stdio"  # 'stdio' | 'streamable-http'
    mcp_host: str = "0.0.0.0"
    # Railway / Heroku 등은 `PORT` env 를 자동 주입 → 그걸 우선 사용.
    # `MCP_PORT` 가 명시되면 그 값. 둘 다 없으면 8001 (로컬 기본).
    mcp_port: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PORT") or os.getenv("PORT") or 8001)
    )
    # Public base URL — OAuth Discovery 엔드포인트가 이걸 issuer 로 사용.
    # streamable-http 모드일 때만 필요. 예: https://stock-mcp.up.railway.app
    mcp_base_url: str | None = None

    # ---- Google OAuth (FastAPI + MCP 공유 IdP) ----
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # 콤마 분리. 공백 무시. 빈 문자열이면 모두 거부 (보안 기본값).
    allowed_emails: str = ""

    # ---- CORS (FastAPI) ----
    # 콤마 분리 origin 화이트리스트. localhost 는 항상 자동 허용.
    # 예: "https://stockclaude.vercel.app,https://app.example.com"
    allowed_origins: str = ""
    # Vercel preview 같은 와일드카드. 정규식.
    # 예: "^https://stockclaude(-[a-z0-9-]+)?\\.vercel\\.app$"
    allowed_origin_regex: str | None = None

    # KIS (read-only 시장 데이터)
    kis_app_key: str | None = None
    kis_app_secret: str | None = None
    kis_account_no: str | None = None
    kis_env: str = "real"  # 'real' | 'paper'

    # External APIs
    krx_api_key: str | None = None
    dart_api_key: str | None = None
    fred_api_key: str | None = None
    finnhub_api_key: str | None = None
    sec_edgar_user_agent: str | None = None
    # 한국은행 ECOS OpenAPI (KR 매크로 — 기준금리/CPI/환율/M2/경상수지 등)
    # 발급: https://ecos.bok.or.kr/api/  무료, 즉시.
    ecos_api_key: str | None = None

    # Optional (서버 AI — Phase 3에선 미사용)
    anthropic_api_key: str | None = None

    # Skills 매뉴얼 파일 경로 (default: ~/.claude/skills)
    skills_dir: Path = Field(default_factory=lambda: Path.home() / ".claude" / "skills")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def allowed_emails_list(self) -> list[str]:
        """ALLOWED_EMAILS env 를 리스트로 파싱. 소문자 정규화."""
        return [e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()]

    @property
    def mcp_remote_enabled(self) -> bool:
        """원격 MCP 모드 여부 (streamable-http)."""
        return self.stock_mcp_transport.lower() != "stdio"


settings = Settings()  # type: ignore[call-arg]
