# server/ — 백엔드 일반 가이드

## 진입점 2개 / 코어 1개

```
FastAPI (server/main.py)        ┐
                                ├─→ repos/ (DB)  +  analysis/ (계산)  +  scrapers/ (외부 API)
FastMCP  (server/mcp/server.py) ┘
```

같은 코어를 두 진입점이 공유. **인증만 다르다**:
- FastAPI: Google OAuth ID token (Bearer) + `ALLOWED_EMAILS` 화이트리스트 (`server/api/deps.py`)
- FastMCP stdio: 무인증 (자식 프로세스 신뢰)
- FastMCP streamable-http: GoogleProvider OAuth proxy (`server/mcp/auth.py`)

## 분업 원칙 (db/schema.sql:11)

> **서버 = deterministic, Claude = reasoning.**
> 서버는 정량 계산만, 의미 부여·자연어 본문은 Claude가.

이 원칙은 모든 서버 코드의 기본 정신. 합성 점수·매트릭스·decision-tree 같은 anchor성 산출은 라운드 2026-05에서 폐기 — 재제안 금지 (자세한 내역은 `server/mcp/CLAUDE.md` §합성 점수 회피).

## 레이어 룰

- `api/` & `mcp/` → 반드시 `repos/` 경유. **api/mcp 안에서 직접 SQL 작성 금지.**
- `repos/` → DB access (raw SQL + `dict_row`). user_id 필터 강제.
- `analysis/` → 순수 함수 (numpy/pandas). DB 의존 X.
- `scrapers/` → 외부 API (KIS/DART/FRED/Finnhub/SEC/ECOS/Naver/yfinance/KRX). 인증·rate-limit·fallback·OHLCV 컬럼 normalize.

## 핵심 파일 1줄 역할

- `config.py` — pydantic-settings 싱글턴. `settings`는 모든 모듈이 import. env 로딩.
- `db.py` — psycopg `ConnectionPool` + `get_conn()` 컨텍스트 (트랜잭션 자동 commit/rollback). `open_pool()/close_pool()`은 lifespan에서.
- `main.py` — FastAPI app 등록 + 13 라우터 + CORS lifespan. 84줄로 단순.
- `mcp/server.py` — FastMCP entry. 88 `@mcp.tool` 단일 파일 (4250줄 — 분할은 #12 이슈로 추적).

## 단일 유저 fallback

1인 운영 전제 + dev/MCP-stdio 모드. `STOCK_USER_ID` env 필수. legacy alias `DEFAULT_USER_ID`도 인식 (AliasChoices). 신규 코드는 `settings.stock_user_id` 사용.

API 라우터에선 `Depends(current_user_id)`로 OAuth 통과 email→user_id 변환 (멀티유저 대비). dev 모드 더미 토큰(`dev@localhost`)은 fallback singleton으로 매핑.

## 통화·환율 (자세한 룰은 server/api/CLAUDE.md, server/mcp/CLAUDE.md)

- MCP는 **unconverted** 반환. KR=KRW, US=USD 분리.
- API 라우터에서 환율 변환 (필요 시). 서로 다른 currency 합산 금지.

## 하위 폴더 안내 (각자 CLAUDE.md 보유)

| 폴더 | 책임 | 자기 CLAUDE.md |
|---|---|---|
| `api/` | 13 REST 라우터 (deps 인증·response_model·prefix) | 있음 |
| `mcp/` | 88 MCP 툴 단일파일 (`@mcp.tool`·`_json_safe`·docstring ⚠️) | 있음 — **ROI 최상** |
| `repos/` | raw SQL + dict_row + user_id 필터 | 있음 |
| `analysis/` | 순수 계산 (한글 컬럼·KST 분기) | 있음 |
| `scrapers/` | 외부 API (인증·한도·fallback) | 있음 |
| `jobs/` | 배경 작업 (현재 진입점 미상 — #16) | 있음 |
| `schemas/` | pydantic 응답 모델 (frontend types 수동 동기화 #15) | 있음 |

진입한 폴더의 CLAUDE.md를 자동 로드. 본 파일은 공통 룰만, 디테일은 most-local 1곳에.
