# stockclaude — 프로젝트 루트 가이드

> 이 파일은 매 세션 첫 진입 시 자동 로드된다. **여기는 메타·인덱스·헤드라인만** 둔다. 디테일은 모두 서브폴더 CLAUDE.md에 있다 (most-local 단일 출처). 본문 한국어 + 식별자/SQL 영어.

---

## 정체성

1인 운영 KR/US 주식 포트폴리오 운영·분석 시스템. **Claude Code skill** (`.claude/skills/stock/`, 6 모드: daily/discover/research/weekly-strategy/weekly-review/base-*)이 진입점이고, **MCP 88 툴** (`server/mcp/server.py` FastMCP)이 정량 데이터를, **FastAPI + React 18 대시보드** (`server/main.py` + `web/`)가 시각화를, **PostgreSQL 15** (`db/schema.sql` 565줄, 멀티테넌트 user_id FK)가 SSoT를 담당한다. Railway 배포 + release 시 `bash scripts/run_migrations.sh` 자동.

## 분업 원칙

**서버 = deterministic, Claude = reasoning** (출처: `db/schema.sql:11`). 정량 계산·DB·외부 API는 서버, 의미 부여·자연어 본문은 Claude. 매매 룰 SSoT는 DB의 `rule_catalog`이고 markdown은 사람이 읽기 용도다.

## 도메인 함정 헤드라인 (디테일은 서브 CLAUDE.md)

1. **KST 거래일이 default** — `datetime.now()` 금지, `ZoneInfo("Asia/Seoul")` 명시. SQL은 `(executed_at AT TIME ZONE 'Asia/Seoul')::date`. 디테일: `db/CLAUDE.md`, `server/repos/CLAUDE.md`, `server/analysis/CLAUDE.md`.
2. **KIS 100/150건 한도 + silent fallback** — KR ≤150 KIS / 초과 naver, US ≤100 KIS / 초과 yfinance. OHLCV 컬럼은 한글 (`날짜/시가/고가/저가/종가/거래량`)로 normalize. 디테일: `server/scrapers/CLAUDE.md`, `server/mcp/CLAUDE.md`.
3. **통화 미변환** — MCP는 unconverted 반환, **환율 변환은 API 단에서만**. KR/US 합산 시 단위 섞임 주의. 디테일: `server/api/CLAUDE.md`, `server/mcp/CLAUDE.md`.
4. **Pending vs Active** — `get_portfolio()`는 Active만, daily 워크플로우는 반드시 `list_daily_positions()` (Active+Pending). 디테일: `server/mcp/CLAUDE.md`.
5. **매트릭스·합성점수·서브에이전트 폐기 (재제안 금지)** — v6 12셀 매트릭스, decision-tree 5×6, position-action-rules 6대 룰, scoring 합성점수·is_stale·cell, base-*-updater 서브에이전트 모두 폐기. `references/_archive/` 보존. 디테일: `.claude/skills/stock/references/CLAUDE.md`, `server/analysis/CLAUDE.md`, `web/src/lib/CLAUDE.md`.

## 라운드 결정 인덱스

- `docs/rounds/2026-05-stock-daily-overhaul.md` — per-stock-analysis 5단계 단일 진입점 + 합성점수·매트릭스 폐기 + base 본문 inject 의무 + 결론 정량 컬럼(verdict/size_pct/stop_*) + learned_patterns + 산업 표준 메트릭 + 자동 마이그레이션.
- `docs/rounds/2026-05-weekly-review-overhaul.md` — 4-Phase 회고 (종목별 8-step → 포트 → base 역반영 → 룰 win-rate) + rule_catalog DB SSoT 통합 + base appendback + BLOCKING #14 (`pending_base_revisions ≥ 3`).
- **재제안 금지**: 매트릭스 룩업 / decision-tree / position-action-rules / 합성점수·is_stale·cell / base-*-updater 서브에이전트 / 룰 markdown 단일 SSoT (DB가 SSoT).

## 서브폴더 CLAUDE.md 인덱스 (진입 시 자동 로드)

```
./                                              CLAUDE.md  [d0] (이 파일)
├─ server/                                      CLAUDE.md  [d1] FastAPI+FastMCP 분업·레이어·진입점
│  ├─ api/                                      CLAUDE.md  [d2] 13 라우터·deps 인증·response_model·환율 변환 위치
│  ├─ mcp/                                      CLAUDE.md  [d2] 88 툴 단일파일·@mcp.tool·_json_safe·docstring ⚠️
│  ├─ repos/                                    CLAUDE.md  [d2] raw SQL+dict_row·user_id 필터·KST cast
│  ├─ analysis/                                 CLAUDE.md  [d2] 순수함수·DB금지·한글 컬럼·산업 평균
│  ├─ scrapers/                                 CLAUDE.md  [d2] 외부 API 인증·rate-limit·fallback·OHLCV normalize
│  ├─ jobs/                                     CLAUDE.md  [d2] 진입점 미상 — 작업 전 확인 (이슈 #16)
│  └─ schemas/                                  CLAUDE.md  [d2] pydantic·frontend types 수동 동기화 (이슈 #15)
├─ db/                                          CLAUDE.md  [d1] 565줄 schema·멀티테넌트·TIMESTAMPTZ·seed 분리·trigger
├─ scripts/                                     CLAUDE.md  [d1] 마이그레이션 NN_<설명>.sql idempotent·release-phase
├─ web/                                         CLAUDE.md  [d1] Vite+React18+Tremor3+RQ5+RR7·App.tsx 라우팅
│  └─ src/
│     ├─ hooks/                                 CLAUDE.md  [d3] 1훅=1엔드포인트·queryKey·UseQueryResult
│     ├─ features/                              CLAUDE.md  [d3] features 격리·Page+components·간 import 금지
│     └─ lib/                                   CLAUDE.md  [d3] 표시용 only·SSoT는 백엔드·매트릭스 잔재 정리 (이슈 #14)
├─ .claude/
│  ├─ skills/stock/                             CLAUDE.md  [d3] SKILL.md/references/assets·6 모드·_archive
│  │  └─ references/                            CLAUDE.md  [d4] 36 reference 작성 규약·폐기 절차·재제안 금지
│  └─ commands/                                 CLAUDE.md  [d2] 8 wrapper (skill 진입만)·로직 X
├─ docs/
│  └─ rounds/                                   CLAUDE.md  [d2] 라운드 doc 포맷·인덱스·폐기 명시 의무
└─ tests/                                       CLAUDE.md  [d1] smoke 정책 (현재 약함, 이슈 #10)
```

총 19개 서브 CLAUDE.md (루트 제외). 깊을수록 상세 — 디테일이 필요하면 가장 깊은 폴더부터.

## 명령 인덱스

- 백엔드 (REST): `uv run uvicorn server.main:app --reload`
- 백엔드 (MCP stdio): `uv run python -m server.mcp.server`
- DB 부팅 (로컬): `docker compose up -d` — Postgres 15 + adminer (TZ=Asia/Seoul)
- 마이그레이션: `bash scripts/run_migrations.sh` — `schema_migrations` 추적, 미적용만 적용
- 스킬 빌드: `bash scripts/build-skills.sh` → `dist/stockclaude.zip` (Anthropic 업로드 포맷)
- 스킬 설치: `bash scripts/install-claude-skill.sh` → `~/.claude/skills/stock` 심링크
- 프론트: `cd web && npm run dev`

## agent/ 워크플로우

`research → plan → modifier → action` 4단계 (글로벌 `~/.claude/CLAUDE.md`). `agent/research.md`·`agent/plan.md`는 **in-flight 작업 산출물**이라 `.gitignore` 유지 — PR에 올라가지 않는다. 의도된 정책 ((agent/ gitignore 의도) 확인됨), 변경 금지.

## 네이밍 룰

외부 식별자는 **`stockclaude`** 로 수렴 (commit `a8f1e24` 방향). 잔재 (DB 이름 `stock_manger` 오타, FastMCP 인스턴스명 `stock-manager`, `pyproject.toml name="stock-manager"`, 사이드바 title 등)는 **이슈 #11**에서 단계적 통일 추적. 신규 코드·문서는 처음부터 `stockclaude`.

## 트래킹 중인 이슈 (CLAUDE.md 라운드 발행 7건)

- `#10` — chore(tests): MCP 툴 / repos / analysis smoke 테스트 도입 로드맵
- `#11` — chore: 외부 식별자 stockclaude 단계적 통일 (DB·MCP 인스턴스명·pyproject 잔재)
- `#12` — chore(server/mcp): server.py 4250줄 단일파일 그룹별 분할 계획
- `#13` — chore(server/repos): portfolio_snapshots.py:170 timezone UTC 일관성 확인 필요
- `#14` — chore(web/src/lib): 폐기 매트릭스 잔재 정리 (signals12/positionActionRules/baseExpiryRules/volFinMatrix)
- `#15` — chore(server/schemas): frontend types 자동 생성 (openapi-typescript) 도입 검토
- `#16` — chore(server/jobs): 사용 여부 확인 — 진입점 미상 (`daily_snapshot.py / healthcheck.py / refresh_base.py`)

신규 불일치 발견 시 v4a 절차 (most-local CLAUDE.md에 룰 + GitHub 이슈 발행 `claude-md-audit` 라벨).
