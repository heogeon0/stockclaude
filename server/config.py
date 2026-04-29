"""
환경변수 로딩. 다른 모든 모듈이 `from server.config import settings` 로 접근.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import Field
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
    default_user_id: UUID = Field(
        default=UUID("00000000-0000-0000-0000-000000000000")
    )
    api_key: str = "local-dev"

    # Database
    database_url: str

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

    # Optional (서버 AI — Phase 3에선 미사용)
    anthropic_api_key: str | None = None

    # Skills 매뉴얼 파일 경로 (default: ~/.claude/skills)
    skills_dir: Path = Field(default_factory=lambda: Path.home() / ".claude" / "skills")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()  # type: ignore[call-arg]
