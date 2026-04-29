# stockclaude

> Personal stock portfolio manager — Claude Code skill + MCP server + dashboard for KR/US markets.

1인 운영용 주식 포트폴리오·분석·매매 기록 시스템. Claude Code 와 통합되어 daily 운영부터 종목 발굴까지 자연어로 지시 가능.

## 구성

```
stockclaude/
├── server/         FastAPI REST + FastMCP 통합 서버 (Python 3.14, uv)
├── web/            Vite + React + TypeScript + Tremor 대시보드
├── db/             PostgreSQL 15 schema + 예시 시드
├── scripts/        DB 마이그레이션 + 백업 스크립트
└── claude-skill/   Claude Code 통합용 skill + slash command 정의
    ├── skills/stock/   ~/.claude/skills/stock/ 으로 설치
    └── commands/       ~/.claude/commands/ 로 설치
```

## 핵심 기능

- **MCP 서버** (50+ 툴) — 시그널·재무·모멘텀·매매기록·컨센서스 등을 Claude 가 직접 호출
- **데일리 운영** — `/stock-daily` 한 줄로 보유·감시 종목 일일 분석
- **신규 발굴** — `/stock-discover` 광역 모멘텀 스크리닝 (KR 2,500 / US 530 종목)
- **Base 분석** — 경제·산업·종목 3계층 펀더멘털 base.md 작성·갱신
- **변동성×재무 매트릭스** — 12셀 룩업 기반 진입 사이즈·피라미딩·손절 결정
- **룰 카탈로그** (15 룰) — 매매 시점 룰 명시 → 주간 회고 자동 분류
- **대시보드** — 포트폴리오·매매기록·전략·리포트 시각화

## 데이터 소스

- **KIS Open API** — KR/US OHLCV (한국투자증권 계좌 토큰 필요)
- **DART** — 한국 공시·재무제표
- **FRED** — 미국 거시지표
- **Finnhub** — US 실적 캘린더·컨센서스
- **SEC EDGAR** — 미국 공시 (User-Agent 만 필요)
- **Naver / yfinance** — fallback OHLCV
- **KRX Open API** — 공매도·시총·종목마스터

## 빠른 시작

### 1. 환경 변수
```bash
cp .env.example .env
# .env 에 KIS_APP_KEY, DART_API_KEY, FINNHUB_API_KEY 등 채움
```

### 2. DB 기동
```bash
docker compose up -d
psql $DATABASE_URL < db/schema.sql
psql $DATABASE_URL < db/seed.example.sql  # 데모 유저 + 산업 분류
```

### 3. 서버 실행
```bash
uv sync
uv run uvicorn server.main:app --reload   # FastAPI :8000
uv run python -m server.mcp.server        # MCP stdio
```

### 4. 대시보드 실행
```bash
cd web
npm install
npm run dev                                # Vite :5173
```

### 5. (선택) Claude Code 스킬 설치
```bash
bash scripts/install-claude-skill.sh
```

## 면책

본 프로젝트는 개인 운영·학습 목적의 도구이다. **투자 자문 또는 매매 권유가 아니며**, 분석 결과로 인한 투자 손실에 대해 어떠한 책임도 지지 않는다. 모든 매매 결정은 사용자의 판단과 책임 하에 이루어진다.

## 라이선스

MIT — `LICENSE` 참조.
