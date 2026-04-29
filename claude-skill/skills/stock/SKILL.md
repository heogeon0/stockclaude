---
name: stock
description: 개인 주식 포트폴리오 운영·분석 통합 skill (KR + US). 일일 운영(daily) / 신규 발굴(discover) / 6차원 정량 분석(research) / base 자동 갱신(sub-agent) 모든 모드 통합. 매매 추천·피라미딩·손절·집중도·실적임박·컨센·재무·모멘텀·52주돌파·수급 분석. 사용자가 주식·매매·종목·포트·투자·분석·발굴·매도·매수·익절·손절·차트·시그널·재무·실적·컨센·DCF 같은 단어를 언급하면 반드시 이 skill 사용. 매트릭스(변동성×재무 12셀)로 액션 차등화. stock-manager MCP 서버(58 툴) + PostgreSQL 백엔드 + 4개 KR/US 슬래시 명령(stock-daily/discover/research/base-*).
---

# Stock — 통합 주식 운영 skill

> **단일 진입점**으로 모든 주식 운영 처리.
> 모드별 워크플로우는 `references/{daily,discover,research}-workflow.md` 분리.
> base 본문 작성은 `agents/base-*-updater` sub-agent 격리.
> 데이터·계산은 `stock-manager` MCP (48 툴) + PostgreSQL.

---

## 호출 인터페이스 (4 모드)

| 슬래시 | wrapper 위치 | 모드 | 워크플로우 |
|---|---|---|---|
| `/stock-daily` | `~/.claude/commands/stock-daily.md` | daily — 보유+Pending 종목 일일 운영 | `references/daily-workflow.md` |
| `/stock-discover` | `~/.claude/commands/stock-discover.md` | discover — 신규 종목 발굴 | `references/discover-workflow.md` |
| `/stock-research` | `~/.claude/commands/stock-research.md` | research — 6차원 정량 분석 | `references/research-workflow.md` |
| `/base-economy` `/base-industry` `/base-stock` | `~/.claude/commands/base-*.md` | base 갱신 (수동 호출) | `agents/base-*-updater` spawn |

각 wrapper 가 stock skill 의 해당 모드로 진입. 컨텍스트는 항상 stock skill 단일.

### 자연어 입력 시 모드 추측 (사용자가 슬래시 안 쓸 때)

사용자가 슬래시 명시 없이 자연어로 입력하면 의도 분석 후 적절한 모드로 진입:

| 입력 패턴 | 모드 | 예시 |
|---|---|---|
| "내 포트 / 어제 매매 / 보유 종목 현황 / 매매 추천 / 익절·손절·피라미딩" | **daily** | "내 포트 어때?", "오늘 뭐 사야 돼?", "삼성전자 매도할까?" |
| "신규 종목 / 발굴 / 추천 / 모멘텀 상위 / 어떤 종목이 좋아 / 테마" | **discover** | "요즘 좋은 종목 추천해줘", "AI 관련 신규 종목 찾아줘" |
| "분석 / 6차원 / 재무 / 컨센 / DCF / 모멘텀 / `{종목명}` 어때 / 비교" | **research** | "삼성SDI 분석해줘", "엔비디아 컨센 어떻게 변했어?" |
| "base 갱신 / 만기 / 재작성 / Narrative / 펀더멘털 풀 분석" | **base sub-agent** | "삼성전자 base 갱신해줘" → `Agent("base-stock-updater", code=...)` spawn |
| "거시 / 금리 / 환율 / FOMC / 외국인 수급" | **base-economy sub-agent** | "오늘 거시 어때?" → `Agent("base-economy-updater", market="kr")` |

**복합 요청** (예: "포트 점검하고 신규도 찾아줘") → daily 먼저, 끝난 뒤 discover 진입.
**모호 시** → 사용자에게 한 번 확인 ("daily 모드로 진입할까요?").
**호출 후** → 결과 보고 시 모드 + 진입 사유 한 줄 명시 (예: "daily 모드 — 보유 종목 점검 의도").

---

## 프로젝트 핵심 사실

- **데이터·계산은 MCP**: `stock-manager` MCP 서버가 **48 툴** 제공 (`~/Desktop/Project/stock-manager/`)
- **PostgreSQL 백엔드**: 포지션·거래·지표·시그널·애널·스코어링 가중치 모두 DB
- **MCP 단일 의존**: 모든 데이터는 MCP 호출로 조회. **markdown 파일 직접 Read 금지** (DB source of truth)
- **너의 역할 = 해석·판단·서술**. 숫자는 MCP, 의미 부여는 references 룰
- **사용자 기대치**: 월스트리트 IB 시니어 분석가 품질. 질문하지 말고 실행

---

## 공통 룰 (모든 모드 적용)

### 변동성×재무 매트릭스 (v17 핵심)

종목별 액션 차등은 **변동성 × 재무 헬스 12셀**로 결정:
- 변동성: `analyze_volatility(code).regime` → normal / high / extreme
- 재무: `compute_score(code).breakdown.financial` → A / B / C / D
- 셀별: 진입 사이즈 / 피라미딩 단계 / 손절폭

→ 12셀 정의: **`references/scoring-weights.md`**.

**단타/스윙/중장기/모멘텀 4종 폐지** (v17). 단일 룰 + 매트릭스 차등.

### 12 기술 시그널

`compute_signals(code).signals` 12 전략 + 종합 verdict 산정:

→ **`references/signals-12.md`**.

### 과열 경고 임계

RSI / Stoch / 52주 고가 이격 / ADX / 20MA 이격 / 변동성 / 거래량:

→ **`references/overheat-thresholds.md`**.

### 포지션 액션 6대 룰

보유 종목 액션 결정 (수익률 구간 × 시그널 매트릭스 + 손절 단계):

→ **`references/position-action-rules.md`**.

### KR/US 시장 자동 라우팅

종목명/티커로 market 식별:
- KR: 6자리 숫자 / 한글명
- US: 1~5자 대문자 (`AAPL`, `NVDA`, `BRK.B`)

상세 매핑: → `references/market-routing.md`.
판정: LLM 이 입력 형태로 직접 판단 (6자리 숫자 = KR / 1~5자 대문자 = US).

---

## base 자동 갱신 (sub-agent spawn)

base 본문 작성·갱신은 **별도 sub-agent 격리** — 메인 LLM 컨텍스트 보호.

### 만기 표

| Base | 만기 | sub-agent | 호출 형식 |
|---|---|---|---|
| economy | 1일 | `base-economy-updater` | `Agent("base-economy-updater", market="kr"\|"us")` |
| industry | 7일 | `base-industry-updater` | `Agent("base-industry-updater", name="반도체"\|"us-tech")` |
| stock | 30일 | `base-stock-updater` | `Agent("base-stock-updater", code="005930"\|"NVDA")` |

### 자동 갱신 정책

각 모드 (daily/discover/research) 진입 시:
1. `check_base_freshness(auto_refresh=True)` MCP 호출 — KR stock_base 데이터는 자동 refresh, 본문 텍스트가 필요한 base 는 `auto_triggers` 반환
2. `is_stale: true` 인 base 마다 즉시 sub-agent spawn
3. **cascade 순서**: economy → industry → stock (메인 LLM 순차 spawn)
4. **sub-agent 안에서 sub-spawn 금지** — 의존성은 메인이 책임

### 결과 검증 (Trust but verify)

sub-agent 종료 후 메인이 즉시:
- `get_economy_base(market)` / `get_industry(code)` / `get_stock_context(code).base` 호출
- DB 의 `updated_at` 이 spawn 시각 이후인지 확인
- 미달 시 사용자 보고 + 1회 재시도 (그래도 실패 시 사용자 개입)

이유: sub-agent 가 "갱신 완료" 만 보고하고 실제로 안 했을 가능성 차단. 무인 운영 신뢰성 핵심.

### stale 룰 — base 본문 vs Daily Appended Facts

- **만기 (stale) 도래** → 본문 재작성 (sub-agent 가 함)
- **트리거 (컨센±15%/실적±10%/신고가/공시 등)** → 본문 갱신 X. **`Daily Appended Facts` 섹션에 append 만** (사용자 정책: 4/28)
- 4/28 메모리 룰 `feedback_stale_auto_call.md` 정합

---

## 데이터 태깅 · 할루시네이션 방어

### 태그 규칙

- **[실제]** — MCP 조회값·DART/SEC 확정치
- **[추정]** — MCP 데이터 + 내 계산
- **[가정]** — 시나리오용 설정값 (변경 가능 명시)

### "모른다" 선언 의무

- base 없는 종목: MCP 조회 결과 없으면 추정 절대 금지, "base 미작성" 명시
- 애널 컨센 없음: `get_analyst_consensus` → None 이면 "애널 커버 없음"
- 재무 비공개: `compute_financials` 실패 시 "DART/SEC 재무 접근 불가, 미공시 가능"
- 비교기업: 실존 + DB 검증된 종목만 멘션

---

## 매매 집행 전 체크리스트 (모든 모드 공통)

매수 / 피라미딩 / 매도 결정 직전 체크:

```
[ ] check_concentration → 25% 룰 통과
[ ] 예수금 충분 (currency 기준 — KRW / USD 분리)
[ ] 실적 D-7 이내면 손절선 타이트화
[ ] 최근 외인/기관 수급 톤 (analyze_flow)
[ ] 동일 섹터 보유 총합 (portfolio_correlation)
[ ] 회고 룰 — get_weekly_context.rolling_stats.rule_win_rates 확인
    • 적용할 rule_category 의 누적 승률 < 50% → D+1 안착 룰 또는 추가 검증 강제
    • < 30% → 4주 누적 폐지 후보 (사용자 검토 권장)
[ ] 변동성×재무 셀 사이즈 적용 (references/scoring-weights.md)
[ ] ⭐ record_trade 시 rule_category 명시 — 카탈로그 15 룰 (references/rule-catalog.md)
    • 카탈로그 외 매매 패턴 발견 시 카탈로그 확장 후 진행
[ ] 집행 후 trades AFTER trigger 가 positions / cash_balance / realized_pnl 자동 재계산
[ ] 필요 시 propose_watch_levels(persist=True) 로 감시 레벨 자동 생성
```

상세 룰: → `references/position-action-rules.md`.

---

## ⛔ 종목 신규 등록 시 industry_code 매핑 의무

신규 종목을 stocks 테이블에 INSERT 하는 모든 진입점에서 LLM 이 즉시 industry_code 를 판단해서 같이 입력. **NULL 상태로 stocks INSERT 절대 금지**.

### 진입점

- `record_trade` — 처음 매매 종목이면 stocks row 자동 생성됨
- Pending 포지션 추가 — 감시 종목 등록 시
- `save_stock_base` — base 저장 시 stocks row 신규/갱신

### 매핑 절차

1. **종목명/티커로 산업 판단** — 사업 영역, 섹터, 매출 구성
   - 예: 하나금융지주 → `금융지주`, 삼성SDI → `2차전지`, 이수페타시스 → `AI-PCB`, NVDA → `us-tech`, GOOGL → `us-communication`

2. **industries 테이블 존재 확인**
   - `get_industry(code)` → 있으면 매핑
   - 없으면 → `Agent("base-industry-updater", name="...")` spawn 후 매핑

3. **stocks.industry_code UPDATE**
   - INSERT 시점에 같이 입력하거나, 누락됐으면 즉시 UPDATE

4. **`analyze_position` 결과 검증**
   - `is_stale.industry: null` 반환되면 매핑 누락 신호

### 산업 코드 컨벤션

- KR: 한글 슬러그 (`반도체`, `게임`, `전력설비`, `지주`, `금융지주`, `2차전지`, `AI-PCB`)
- US: `us-{gics_sector_slug}` (`us-tech`, `us-communication`)

### 누락 발생 시

- 발견 즉시 처리 (다음 daily 까지 미루지 않음)
- 같은 종목 base.md 의 "섹터" 메타와 일관성 검증

---

## 모드별 워크플로우 (상세는 references/)

### daily 모드 → `references/daily-workflow.md`

**일일 운영** — 보유(Active) + 감시(Pending) 종목 일일 보고서 + 포트폴리오 종합.

핵심:
- ⛔ BLOCKING 12개 — Phase 0~1 진입 전 필수
- v2 7-Phase Pipeline (Phase 0~7)
- `analyze_position(code)` 1회로 16 카테고리 중 10개 묶음 반환
- KR/US 하이브리드 통화별 분리

### discover 모드 → `references/discover-workflow.md`

**신규 종목 발굴** — 광역 모멘텀 → 좁은 분석 → Top 3~5.

핵심:
- 광역 모멘텀이 메인, `screen_stocks`/`discover_by_theme` 는 부산물
- KR (~2,500 종목) / US (S&P500 ∪ NDX100 ~530)
- 변동성×재무 매트릭스 셀로 진입 사이즈 결정

### research 모드 → `references/research-workflow.md`

**6차원 정량 분석** — 재무/기술/수급/모멘텀/이벤트/컨센.

핵심:
- daily / discover 의 종목별 상세 분석 호출
- base 만료 시 sub-agent spawn (위 cascade)
- 유의미 발견 → 종목 base 의 `Daily Appended Facts` append

---

## MCP 56 툴 인벤토리

### 📊 조회 (7)
`get_portfolio`, `get_portfolio_summary`, `get_stock_context`, `get_applied_weights`, `list_trades`, `list_tradable_stocks`, `list_daily_positions`

### 📈 기술 분석 (7)
`compute_indicators`, `compute_signals`, `refresh_daily`,
`detect_market_regime`, `analyze_volatility`, `rank_momentum`, `rank_momentum_wide`

### 💰 재무·애널 (8)
`compute_financials`, `detect_earnings_surprise_tool`,
`record_analyst_report`, `list_analyst_reports`, `get_analyst_consensus`, `analyze_consensus_trend`,
`refresh_kr_consensus`, `refresh_us_consensus`

### 🔬 리스크·이벤트 (5)
`check_concentration`, `detect_portfolio_concentration`,
`detect_events`, `analyze_flow`, `portfolio_correlation`

### 🎯 진입 설계 (3)
`propose_position_params`, `propose_watch_levels`, `compute_score`

### 🔍 KIS 실시간 (4)
`kis_current_price`, `kis_us_quote`, `kis_intraday`, `realtime_price`

### 📝 쓰기 (11)
`record_trade` (cash_balance 자동 갱신 — issue #7 trigger), `register_stock` (신규 종목 등록 — industry_code 매핑 의무),
`save_daily_report`, `save_portfolio_summary`,
`save_stock_base`, `save_industry`, `save_economy_base`,
`override_score_weights`, `reset_score_weights`,
`refresh_stock_base`, `analyze_position` (16카테고리 묶음)

### 📊 회고·스냅샷 (5)
`save_weekly_review`, `get_weekly_review`, `list_weekly_reviews`, `get_weekly_context`, `reconcile_actions`

### 🌐 발굴 (2)
`screen_stocks`, `discover_by_theme`

### 🔧 base 조회 (3)
`get_economy_base`, `get_industry`, `check_base_freshness`

### 🩺 운영 (1)
`healthcheck` — 58 도구 + 8 스크래퍼 + DB 정합 + 신선도 일괄 점검 (quick=True 기본 ~30s)

### 📉 백테스트 (1)
`backtest_signals` — 단일 종목 12 시그널 5/10/20일 hold 승률 측정. discover 모드 2.5단계 자동 호출 (Phase 1: 정보 첨부, 자동 가중치 X)

### 📚 룰 카탈로그 (1)
`list_trades_by_rule` — 주간 회고 helper. 특정 주 trades 를 rule_category 별 그룹 반환 (`save_weekly_review` 작성 시 win/loss 분류). 14 룰 정의: → `references/rule-catalog.md`

---

## 수치 표기 규칙

- 주식수: **X주** (절반·1/3 금지)
- 금액: "5주 × ₩267,500 = ₩1,337,500"
- 수익: "+2.52% = +₩184,016"
- US 분수주 허용: 26.7975주

---

## 출력 원칙

- 마크다운 자유, 테이블 가독성 우선
- 장 상태 필수 표기
- 투자의견 반드시 3관점 (중장기/단기/포지션)
- 각 시그널 진입가/손절가 명시
- 집행 전 집중도 체크 결과 인용
- **한 줄 결론 필수** — 각 보고서 끝에
- 모든 숫자 [실제]/[추정]/[가정] 태깅
- WebSearch 결과 출처 + 시점 명시
- 컨센 데이터는 매번 fetch (캐시 재사용 금지)

---

## 메타 정보

### 프로젝트 경로

```
~/Desktop/Project/stock-manager/          ← MCP 서버 (FastAPI + PG + 48 tools)
  .mcp.json                                ← Claude Code 자동 등록
  server/
    api/, scrapers/, analysis/, repos/, jobs/, mcp/
  db/schema.sql                            ← 19개 테이블 + 트리거

~/.claude/skills/stock/                    ← 본 skill (단일 통합)
  ├── SKILL.md (이 파일)
  ├── references/  (29개 파일)
  ├── agents/      (3 sub-agent — base-*-updater)
  └── assets/      (12 templates)
  (scripts/ 폐지 — 모든 분석·계산은 MCP 단일 의존)

~/.claude/commands/                        ← wrapper 6개 (호환 슬래시)
  stock-daily.md, stock-discover.md, stock-research.md,
  base-economy.md, base-industry.md, base-stock.md

~/.claude/_archive_skills_2026-04-28/      ← 마이그레이션 백업 (롤백용)
```

### 서버 기동 (필요 시)

```bash
cd ~/Desktop/Project/stock-manager
docker compose up -d                       # PG + Adminer
uv run uvicorn server.main:app --reload    # FastAPI (선택)
```

MCP 서버는 `.mcp.json` 으로 Claude Code 가 자동 기동.

### 배치 job

```bash
uv run python -m server.jobs.daily_snapshot    # 매일 장 마감 후
uv run python -m server.jobs.refresh_base      # 분기별 재무 갱신
```

---

## 보조 파일 인덱스

### references/ (29개)

**공통 룰** (모든 모드 적용):
- `scoring-weights.md` — 변동성×재무 12셀 매트릭스 ⭐
- `signals-12.md` — 12 기술 시그널 정의
- `overheat-thresholds.md` — 과열 경고 임계
- `position-action-rules.md` — 포지션 액션 6대 룰
- `market-routing.md` — KR/US 데이터 소스 분기

**모드별 워크플로우**:
- `daily-workflow.md` — daily 모드 (BLOCKING 12 + Phase 0~7)
- `discover-workflow.md` — discover 모드 (광역 모멘텀 → Top 3~5)
- `research-workflow.md` — research 모드 (6차원 verdict)

**daily 보조**:
- `decision-tree.md` — Phase 5 액션 결정
- `expiration-rules.md` — base 만기·자동 재생성
- `base-impact-classification.md` — 4분류 (high/medium/review/low)
- `base-patch-protocol.md` — Daily Appended Facts append 절차
- `websearch-rules.md` — WebSearch 의무 + 5종 추가 조건
- `weekly-context-rules.md` — 4가지 활용 룰
- `snapshot-schema.md` — `save_portfolio_summary` JSON 스키마

**research 보조**:
- `six-dim-analysis.md` — 6차원 해석 룰
- `valuation-frameworks.md` — Reverse/Forward DCF/확률가중/Comps/SOTP
- `momentum-6dim-scoring.md` — 모멘텀 스코어링
- `momentum-principles.md` — 5대 원칙
- `momentum-filters.md` — 진입/청산/Crash 방어
- `deal-radar-checklist.md` — 6종 WebSearch
- `analyst-consensus-tracking.md` — 컨센 추적

**discover 보조**:
- `discover-filters.md` — 1/2/3단계 필터 + 매트릭스 적용
- `theme-keywords.md` — 테마별 키워드 (10+ 카테고리)

**base sub-agent 참조**:
- `economy-base-classification.md` — 경제 base 영향도 4분류
- `industry-base-classification.md` — 산업 base 영향도 4분류
- `industry-sectors.md` — KR 11 + US GICS 11 매핑
- `stock-base-classification.md` — 종목 base 영향도 4분류
- `narrative-10-key-points.md` — 10 Key Points 작성

### agents/ (3 sub-agent)

- `base-economy-updater.md` — 거시 base 갱신 (1일 만기)
- `base-industry-updater.md` — 산업 base 갱신 (7일 만기)
- `base-stock-updater.md` — 종목 base 갱신 (30일 만기, 9 섹션 풀)

### scripts/ — 폐지 (MCP 단일 의존)

기존 9개 script (detect_market / concentration_check / fetch_consensus / valuation_call 등) 모두 MCP 도구로 대체됨. 시장 판정·집중도·컨센 fetch·DCF 호출은 LLM 이 MCP 직접 호출 (위 48 툴 인벤토리 참조). multi-step orchestration (discover Pending 등록 등) 도 LLM 이 MCP 시퀀스로 직접 처리.

### assets/ (12 templates)

- `daily-report-template.md` — 종목 daily 본문
- `portfolio-summary-template.md` — 포트폴리오 종합 요약
- `position-template.md` — 보유 종목 position.md (변동성×재무 등급 포함)
- `dependency-audit-template.md` — Audit 출력 + ⚠️ 반쪽 daily
- `economy-daily-template.md` — economy/{날짜}.md 자동 생성
- `economy-base-template.md` — 경제 base.md 표준 (6차원)
- `industry-base-template.md` — 산업 base.md 표준 (5차원)
- `base-stock-template.md` — 종목 base.md 표준 (9 섹션)
- `score-block-template.md` — 등급 블록 표준
- `momentum-ranking-template.md` — Top N 출력
- `rebalance-template.md` — 월간 리밸런싱
- `discover-output-template.md` — 발굴 결과 표준 출력

---

## 지침 요약

1. **MCP 먼저** — 숫자·데이터는 항상 MCP 호출, 암기/추정 금지
2. **변동성×재무 매트릭스 우선** — `references/scoring-weights.md` 셀 룩업
3. **base 만기 → sub-agent spawn** — 본문 작성은 격리. 메인은 cascade 지휘 + DB read-back 검증
4. **6차원 분석** — daily / discover 모두 research 차원 활용
5. **point of truth: 보조 파일** — 같은 룰 여러 곳 복제 금지, references 정의처에서만
6. **태깅 의무** — [실제]/[추정]/[가정], 불확실은 명시
7. **집중도 우선** — 매수 제안 전 `check_concentration` 반드시
8. **자동화 활용** — `record_trade` 후 positions/realized_pnl 은 DB 트리거가 처리
9. **industry_code 매핑 의무** — NULL 금지
10. **모드 라우팅** — 사용자 입력에 따라 daily / discover / research / base-* sub-agent 진입
