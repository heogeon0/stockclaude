# Daily Workflow — 일일 운영 절차

> stock skill 의 daily 모드 진입 시 따라야 할 워크플로우.
> 라운드 2026-05-daily-workflow-tightening: Phase 0 통합 stale 체크 폐지 → phase별 자기영역 분산 + 매크로 정형 4종 BLOCKING + WebSearch BLOCKING 복원.
> SKILL.md 본문은 호출 정책만 명시, 상세 절차는 이 파일에 분리.

---

## ⛔ BLOCKING — 시작 전 22개 체크 (라운드 2026-05-daily-workflow-tightening)

`/stock-daily` (특히 portfolio 모드) 진입 시 반드시 Phase 0~3 진입 전에 아래 22 항목 다 호출. 하나라도 스킵하면 결과 최상단에 **⚠️ BLOCKING 위반 — 반쪽 daily** 명시 (daily 자체는 중단하지 않음 — 사용자 판단에 맡김).

> **환경 무관 실행 의무** (`SKILL.md` ⛔ 섹션) — 모바일·Desktop·iOS Custom Connector 어떤 환경에서도 BLOCKING 22 전부 호출. 토큰·시간·환경을 이유로 임의 스킵·축약·우회 금지. 유일 예외는 사용자 명시 `/stock-daily --fast` 또는 기술적 불가 (silent skip 절대 금지, 명시적 에러 보고).

| # | Phase | 체크 항목 | 호출 |
|---|---|---|---|
| 1 | 0 | **daily 스코프 일괄 로드** ⭐ | `list_daily_positions()` — Active + Pending 모두 (Close 제외). base 체크 X (각 phase 가 자기 영역 책임) |
| 2 | 1 | 어제 pending 액션 로드 | `get_portfolio_summary(yesterday)` |
| 3 | 1 | 어제 trades 매칭 | `reconcile_actions(yesterday)` |
| 4 | 1 | **오늘 trades 조회** ⭐ | `list_trades(limit=20)` |
| 5 | 1 | **오늘 trades 매칭** ⭐ | `reconcile_actions(today)` |
| 6 | 1 | 주간 회고 컨텍스트 | `get_weekly_context(weeks=4)` |
| 7 | 1 | **월요일 weekly_strategy 점검** | `get_weekly_strategy()` — 이번 주 미작성 + 월요일 발견 시 ⚠️ "weekly-strategy 미작성, carry-over 사용 중" 알림. carry_over=True 면 보고서 최상단 표기 |
| 8 | 1 | **base 미처리 narrative revision 큐** | `get_pending_base_revisions(weeks=4)` — `count >= 3` 시 보고서 최상단 ⚠️ 알림 |
| 9 | 2 | **economy stale 자기 체크** ⭐ ⛔ | `check_base_freshness(scope="economy")` — economy_base 만 검사 (industries/stocks 제외) |
| 10 | 2 | 시장 국면 판정 | `detect_market_regime()` |
| 11 | 2 | **매크로 정형 — US** ⭐ ⛔ | `get_macro_indicators_us()` (DFF/CPI/UNRATE/DGS10/SP500 등). **핵심 시리즈 4 중 3 OK 이면 BLOCKING 충족** (DFF/CPIAUCSL/DGS10/VIXCLS — partial fail 정책 #24) |
| 12 | 2 | **매크로 정형 — KR** ⭐ ⛔ | `get_macro_indicators_kr()` (기준금리/CPI/M2/경상수지 등 8 default). **핵심 시리즈 3 중 2 OK 이면 BLOCKING 충족** (722Y001/901Y009/731Y004) |
| 13 | 2 | **수익률 곡선** ⭐ ⛔ | `get_yield_curve()` (UST 3M~30Y + 10Y_3M_spread + 역전 여부). **핵심 4 중 3 OK 이면 BLOCKING 충족** (3M/2Y/10Y/spread) |
| 14 | 2 | **환율** ⭐ ⛔ | `get_fx_rate("DEXKOUS")` (1일 TTL — FRED → yfinance KRW=X fallback, #22 처리). 1차 fail 도 fallback 충족 시 BLOCKING 통과 |
| 15 | 2 | (선택) 경제 캘린더 | `get_economic_calendar(days=7)` — Finnhub. 누락 허용 (BLOCKING 외) |
| 16 | 2 | **WebSearch — 발언 톤** ⭐ ⛔ | 1회 BLOCKING — Tier 1 (Bloomberg/Reuters) + Tier 2 (Fed/BOK 공식). FOMC/금통위·CPI·연설 톤 추적 |
| 17 | 2 | **WebSearch — 지정학** ⭐ ⛔ | 1회 BLOCKING — Tier 1 (Bloomberg/Reuters/FT/WSJ). 중동·미중·우크라·제재 |
| 18 | 2 | **economy stale → inline** ⛔ | #9 결과 `is_stale=true` 면 `references/base-economy-update-inline.md` 진입 → economy_base 갱신 |
| 19 | 3 | **per-stock-analysis 5단계** ⭐ ⛔ | 종목마다 `references/per-stock-analysis.md` 절차. step 1 = `check_base_freshness(scope="stock", code=code)` 자기 영역 체크 |
| 20 | 3 | **per-stock cascade — industry → stock** ⭐ ⛔ | step 2 cascade — economy 제외 (Phase 2 가 처리). industry stale → stock stale 만 |
| 21 | 3 | **per-stock WebSearch** ⭐ ⛔ | step 4 LLM 종합 판단 시 WebSearch 1회/종목 BLOCKING — KR 종목: Tier 1 (Bloomberg/CNBC/Nikkei) + Tier 4 (한경/매경/이데일리). US 종목: Tier 1 만 (KR 매체 skip — #25 운영 효율). **이벤트 트리거 (실적 D-7 / 52w 신고가 / 등락률 ±3%) 시 무조건 풀 search** (조건부 강화) |
| 22 | 7 | **save_daily_report + save_portfolio_summary** ⛔ | DB read-back 의무 (Phase 7 종료 체크리스트 — 본 파일 하단) |

**⭐ 변경 사실 (라운드 2026-05-daily-workflow-tightening)**:
- 옛 BLOCKING #2 통합 stale 체크 (`check_base_freshness(auto_refresh=True)`) 폐지 → Phase 2 (#9 economy 만) 와 Phase 3 (#19 per-stock 만) 으로 분산
- 매크로 정형 4종 (#11~#14) 신규 BLOCKING 승격 (옛 v6 "선택"에서 의무로)
- WebSearch BLOCKING 복원 (#16~#17 economy + #21 per-stock) — v7 자율 정책 부분 회귀. 도메인 화이트리스트 의무 (`websearch-domains.md`)
- 백엔드 변경 (W1, 동일 라운드): `check_base_freshness(scope, code, auto_refresh)` 시그니처 — `scope ∈ {"all","economy","industry","stock"}`, `code` (industry/stock 일 때 단일 종목/산업 필터). default `scope="all"` 호환 유지.

**⭐ #19 (per-stock)**: per-stock-analysis 5단계 (v6 단순화) — `analyze_position(code, include_base=True)` 1 MCP 로 12 카테고리 통합. step 1 의 stale 체크 범위가 종목+산업으로 좁혀짐 (economy 는 Phase 2 책임).

긴급 시엔 `/stock-daily --fast` 명시로만 일부 스킵 허용. Phase 2 매크로 정형 4종 (#11~#14) 과 Phase 3 per-stock WebSearch (#21) 는 `--fast` 에서도 스킵 권장 X (시장 컨텍스트 기반 판단의 토대).

### BLOCKING 누락 시 처리

- daily 자체는 **중단하지 않음** — 누락 항목을 보고서 최상단에 ⚠️ "BLOCKING 위반 — 누락: [#N (항목명)]" 명시 후 진행
- 사용자가 **무시하고 진행** 또는 **재실행** 결정
- 자가 보고로 "사실상 다 했다" 우기지 말 것 — 실제 호출 로그/응답 기준

### 자기 감사 — `save_portfolio_summary` 직전 출력

→ `~/.claude/skills/stock/assets/dependency-audit-template.md` 참조.

---

## 7-Phase Pipeline (라운드 2026-05-daily-workflow-tightening)

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 0: daily 스코프 로드                                    │
│   list_daily_positions() — Active + Pending 일괄            │
│   ※ base 체크 없음 (각 phase 가 자기 영역 책임)               │
├─────────────────────────────────────────────────────────────┤
│ Phase 1: 과거 학습 회수 (어제·오늘 거래 + 주간 회고 + 큐)     │
│   get_portfolio_summary(yesterday) + reconcile_actions      │
│   list_trades + reconcile_actions(today)                    │
│   get_weekly_context(weeks=4)                               │
│   get_weekly_strategy() — 월요일 분기                        │
│   get_pending_base_revisions(weeks=4) — count≥3 ⚠️           │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: 매크로 + economy base 자기완결 (BLOCKING ⛔)         │
│   ① check_base_freshness(scope="economy")                   │
│   ② detect_market_regime()                                  │
│   ③ get_macro_indicators_us()       ┐                       │
│   ④ get_macro_indicators_kr()       │ 정형 4종 BLOCKING      │
│   ⑤ get_yield_curve()               │                       │
│   ⑥ get_fx_rate("DEXKOUS")          ┘                       │
│   ⑦ (선택) get_economic_calendar(days=7)                    │
│   ⑧ WebSearch 2회 BLOCKING (발언 톤 + 지정학)                │
│       — Tier 1 + Tier 2 (websearch-domains.md)              │
│   ⑨ #1 결과 is_stale=true 면 base-economy-update-inline 진입│
├─────────────────────────────────────────────────────────────┤
│ Phase 3: 종목별 per-stock-analysis 순회 (Active + Pending)   │
│   for code in all_codes:                                    │
│     references/per-stock-analysis.md 5단계 절차              │
│       1. check_base_freshness(scope="stock", code=code)     │
│          ※ economy 제외 — Phase 2 가 처리                    │
│       2. cascade industry → stock (economy 제외)             │
│       3. analyze_position(code, include_base=True) — 1 MCP  │
│       4. LLM 종합 판단                                       │
│          — WebSearch 1회/종목 BLOCKING ⛔ (Tier 1 + Tier 4)  │
│       5. save_daily_report                                   │
│     coverage_pct < 80% → ⚠️ 반쪽 분석 표기                  │
├─────────────────────────────────────────────────────────────┤
│ Phase 4: LLM 본문 판단 (Cell + Verdict, 자동 derive 없음)     │
│   per-stock 4단계에서 종목별 진행. 포트 단위 종합은 Phase 5.│
├─────────────────────────────────────────────────────────────┤
│ Phase 5: 액션 결정 (LLM 본문 판단 + master-principles)        │
│   → references/master-principles.md 의 10 카테고리 인용     │
├─────────────────────────────────────────────────────────────┤
│ Phase 6: 게이트 (deterministic)                               │
│   check_concentration / 예수금 / 실적 D-7 / 수급 z 검증     │
├─────────────────────────────────────────────────────────────┤
│ Phase 7: 출력·저장                                            │
│   save_daily_report × N + save_portfolio_summary           │
│   Phase Audit 표 자동 출력                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 실행 모드

### 1. 단일 종목 — `/stock-daily {종목}`
- 하나의 종목만 daily 생성
- market 자동 판정 (LLM 직접 판단 (6자리 숫자 = KR / 1~5자 대문자 = US))
- Phase 2 매크로 BLOCKING 은 단일 종목 모드에서도 의무 (시장 컨텍스트 토대)

### 2. 포트폴리오 — `/stock-daily` / `/stock-daily portfolio`
- `list_daily_positions()` 로 Active + Pending 일괄 로드
- 각 종목 daily + 마지막에 포트폴리오 종합 요약
- **하이브리드 포트**:
  - 통화별 총자산 (KRW / USD) 분리 + 환산 통합액
  - USD 비중 > 25% 시 환율 민감도 경고

### 상태 필터

| 상태 | daily 생성 |
|---|---|
| Active | ✅ |
| Pending | ✅ (감시) |
| Close | ❌ (스킵) |

---

## 0단계 전 — 어제 액션 플랜 리마인드 (포트폴리오 모드 필수)

1. `get_portfolio_summary(date=yesterday)` 호출
2. `found: true` 면 `reconcile_actions(yesterday)` 자동 호출 → trades 매칭
3. 업데이트된 `action_plan` 다시 조회
4. 남은 `pending` / `conditional` 액션을 사용자에게 먼저 제시

`found: false` 면 skip (첫 사용 또는 휴장일).

---

## Phase 2 상세 — 매크로 + economy base 자기완결

> 시장 컨텍스트는 Phase 3 종목 분석의 토대. 라운드 2026-05-daily-workflow-tightening 으로 정형 4종 + WebSearch 2회 BLOCKING 승격. 옛 v6 "선택" 정책 폐지.

### 2-① economy stale 자기 체크 (BLOCKING #9)

```python
fresh = check_base_freshness(scope="economy")
# economy_base 만 검사. industries/stocks 미반환.
# scope 인자 (W1 백엔드 변경, 동일 라운드): default "all" 호환
```

### 2-② 시장 국면 (BLOCKING #10)

```python
regime = detect_market_regime()
# regime ∈ {"trending_up","range","trending_down","extreme_vol"} 등
```

### 2-③ ~ 2-⑥ 매크로 정형 4종 (BLOCKING #11~#14, ⛔)

| 호출 | 응답 핵심 |
|---|---|
| `get_macro_indicators_us(default=True)` | DFF / CPIAUCSL / UNRATE / DGS10 / SP500 시계열 |
| `get_macro_indicators_kr(default=True)` | 기준금리 / CPI / M2 / 경상수지 / 실업률 / 외환보유고 / 산업생산 8 default stat_code |
| `get_yield_curve()` | UST 3M~30Y + 10Y_3M_spread + 역전 여부 |
| `get_fx_rate("DEXKOUS")` | 1일 TTL FRED 환율 |

⚠️ 4종 중 한 건이라도 누락 시 보고서 최상단 ⚠️ "BLOCKING 위반".

### 2-⑦ 경제 캘린더 (선택, BLOCKING 외)

```python
events = get_economic_calendar(days=7)  # Finnhub
# 누락 허용 — 외부 API 의존성 높음
```

### 2-⑧ WebSearch 2회 BLOCKING (#16, #17, ⛔)

| # | 주제 | Tier | 권장 쿼리 (도메인 한정) |
|---|---|---|---|
| #16 | 발언 톤 (FOMC/금통위·CPI·연설) | Tier 1 + Tier 2 | `site:bloomberg.com OR site:reuters.com OR site:federalreserve.gov FOMC 발언 톤 YYYY-MM` |
| #17 | 지정학 (중동·미중·우크라·제재) | Tier 1 | `site:bloomberg.com OR site:reuters.com OR site:ft.com OR site:wsj.com geopolitics YYYY-MM` |

도메인 화이트리스트 단일 출처 → `websearch-domains.md`. 결과 인용 시 `(도메인, YYYY-MM-DD)` 의무.

### 2-⑨ economy stale → inline 진입 (BLOCKING #18)

2-① 결과 `is_stale=true` 면:
```
references/base-economy-update-inline.md 진입
   └─ economy_base 갱신 (8 섹션 + 메타 7키)
   └─ DB read-back: get_economy_base(market).updated_at 갱신 확인
```

stale 아니면 본 단계 skip.

---

## Phase 3 — 종목별 per-stock-analysis 순회

종목 1건 분석은 모드 무관 항상 `references/per-stock-analysis.md` 5단계 절차 단일 사용. daily 모드는 `all_codes` 전부에 대해 1회씩 호출.

라운드 2026-05-daily-workflow-tightening 의 변경:
- step 1 — `check_base_freshness(scope="stock", code=code)` (economy 제외, Phase 2 책임)
- step 2 — cascade 에서 economy 빠짐 (industry → stock 만)
- step 4 — WebSearch 1회/종목 BLOCKING (Tier 1 + Tier 4 KR이면)

상세는 `references/per-stock-analysis.md` 참조.

### 포트 단위 — 별도 호출 (per-stock-analysis 외부)

- `detect_market_regime` (Phase 2 — 위 2-②)
- `portfolio_correlation(days=60)` (Phase 6 — correlation + effective_holdings)
- `detect_portfolio_concentration` (Phase 6 — concentration)
- `get_weekly_context(weeks=4)` (Phase 1)
- `rank_momentum(codes=[...])` (선택)

---

## 매매 집행 전 체크 (집행 직전 필수)

피라미딩 / 매수 / 매도 시그널 실행 전:
- `check_concentration(code, qty, price)` MCP 호출 — 25% 룰 + 섹터 비중 + 효과적 종목수 자동 계산
- 25% 룰 위반 시 daily 보고서 최상단 ⚠️ 경고
- 사용자가 "무시하고 집행" 하지 않는 한 자동 실행 금지

---

## 보고서 저장 (Phase 7) — ⛔ BLOCKING 종료 체크리스트

⚠️ **이 단계 누락 시 daily 결과가 DB 에 영구 기록되지 않음.** 4/29·4/30 누락 사례 (analyze_position 13건 다 돌렸지만 stock_daily 저장 0건) 방지용 강제 체크리스트.

### 필수 호출 순서

```
1. save_daily_report(code, date, verdict, content)  # 각 종목별 — list_daily_positions 의 all_codes 전부
2. save_portfolio_summary(
     date=today,
     per_stock_summary=[...],
     risk_flags=[...],
     action_plan=[...],
     headline="한 줄 결론",
     summary_content="<마크다운 본문 + Audit 최상단>",
   )
3. DB read-back 검증:
   - stock_daily.list_reports_on_date(today) → row count 가 all_codes 수와 일치 확인
   - get_portfolio_summary(today).found == true
```

### 종료 직전 자가 점검

- [ ] **economy stale 잔여 0 확인** ⛔ — Phase 2 #9 재호출 (`check_base_freshness(scope="economy")`). 미달이면 BLOCKING #9·#18 위반 → 즉시 inline 절차 진입 후 재검증
- [ ] **per-stock stale 잔여 0 확인** ⛔ — `check_base_freshness(scope="all")` 1회 (마무리). industries/stocks `is_stale=true` 카운트 0
- [ ] 종목별 `save_daily_report` 호출 — `list_daily_positions().counts.total` 만큼 (Active + Pending 포함). 호출 시 **`verdict` 인자 필수** (강한매수/매수우세/중립/매도우세/강한매도 5종 중 1)
- [ ] 종합 `save_portfolio_summary` 호출 — `summary_content` + `per_stock_summary` + `action_plan` 3 인자 모두 채움
- [ ] DB read-back: `list_reports_on_date(today)` 의 row 수 = `all_codes` 수
- [ ] DB read-back: `get_portfolio_summary(today).found == true`
- [ ] 누락 발견 시 즉시 재호출 (보고서 출력 전)
- [ ] WebSearch BLOCKING 충족 — Phase 2 2회 + Phase 3 종목수×1회. 누락 시 ⚠️ 보고서 최상단

### 자주 빠지는 패턴 (4/29·4/30 사례)

- ❌ "analyze_position × N ✅" 만 적고 save_daily_report 호출 누락 → stock_daily 빈 채로 daily 종료
- ❌ verdict 인자를 None/공백 으로 보내서 verdict 컬럼 NULL 화 (서버 fix 후엔 verdict 무시 안 함)
- ❌ portfolio_summary 본문은 적었지만 `save_portfolio_summary` MCP 호출 안 함
- ❌ Phase 2 WebSearch 자율로 스킵 → 라운드 2026-05-daily-workflow-tightening 으로 BLOCKING 복원

JSON 스키마: → `snapshot-schema.md` 참조.

### 분석 순서 우선순위

1. 🔥 실적 D-7 이내 종목 (`detect_events` D-N 자동)
2. ⚠️ 손절선 -3% 이내 종목
3. 🛡️ Defensive 등급 종목 (리스크 체크)
4. 🏆 Premium / Standard 등급 (피라미딩 트리거)
5. 변동성 extreme regime 종목 (즉시 대응)

---

## 전날 daily 참조 원칙 (편향 방지)

- ✅ 참조: "한 줄 결론" / "예측 트리거" / "손절선"
- ❌ 금지: 기술분석 해석 / 투자의견 본문 / 10 Key Points

---

## position.md 업데이트 프로토콜

→ `~/.claude/skills/stock/assets/position-template.md` 참조.

### Tier 1 — 매매 체결 시 (즉시, 필수)

매매 알리면 즉시 3가지 동시 업데이트:
1. 해당 종목 position.md
2. portfolio.md (테이블 / 예수금 / 비중 / 매매 이력 / 실현이익)
3. 사용자 요약 리포트 (Before/After + 다음 감시 레벨 + 집중도 경고)

### Tier 2 — daily 실행 시 (현재가 관련만)

- 현재가 / 평가액 / 평가손익
- 갱신일 stamp
- 감시 레벨 % 표기
- 변동성·재무 등급 자동 갱신

### Tier 3 — 이벤트 트리거

- 감시 레벨 터치 → "달성/경고" 마크
- 기준선/손절선 이탈 → ⚠️ 최상단 경고
- base.md 갱신 → 진입 논리·목표가 재검토

### 금지

- 매매 없이 평단 임의 변경
- 감시 레벨 절대 가격 임의 조정
- 매매 이력 삭제
- Close 상태 파일 매매 이력 편집

---

## 보조 파일 인덱스 (이 워크플로우)

references:
- `master-principles.md` — Phase 5 액션 결정의 거장 원칙 (v6 신설, 옛 decision-tree 대체)
- `expiration-rules.md` — base 만기·자동 재생성
- `base-impact-classification.md` — 4분류 룰 (high/medium/review/low)
- `base-patch-protocol.md` — Daily Appended Facts append 절차
- `websearch-rules.md` — WebSearch 정책 (v8, BLOCKING 복원 + 도메인 화이트리스트)
- `websearch-domains.md` — Tier 1~4 도메인 화이트리스트 단일 출처 (라운드 2026-05-daily-workflow-tightening 신설)
- `weekly-context-rules.md` — 4가지 활용 룰
- `snapshot-schema.md` — `save_portfolio_summary` JSON 스키마
- `base-economy-update-inline.md` — Phase 2 #18 진입점 (economy stale 시)
- `base-industry-update-inline.md` — Phase 3 step 2 cascade 진입점 (industry stale 시)
- `base-stock-update-inline.md` — Phase 3 step 2 cascade 진입점 (stock stale 시)
- `per-stock-analysis.md` — Phase 3 종목 1건 단일 진입점 (5단계)

assets:
- `daily-report-template.md` — 종목 daily 본문
- `portfolio-summary-template.md` — 포트폴리오 종합 요약
- `position-template.md` — 보유 종목 position.md
- `dependency-audit-template.md` — Audit 출력 + ⚠️ 반쪽 daily
- `economy-daily-template.md` — economy/{날짜}.md 자동 생성
