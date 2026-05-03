# Daily Workflow — 일일 운영 절차

> stock skill 의 daily 모드 진입 시 따라야 할 워크플로우.
> v2 7-Phase Pipeline + BLOCKING 12 + 종목별 묶음 분석 + 매매 룰.
> SKILL.md 본문은 호출 정책만 명시, 상세 절차는 이 파일에 분리.

---

## ⛔ BLOCKING — 시작 전 14개 체크

`/stock-daily` (특히 portfolio 모드) 진입 시 반드시 Phase 0~1 진입 전에 아래 14 항목 다 호출. 하나라도 스킵하면 결과 최상단에 **⚠️ 반쪽 daily** 명시.

| # | Phase | 체크 항목 | 호출 |
|---|---|---|---|
| 1 | 0 | **daily 스코프 일괄 로드** ⭐ | `list_daily_positions()` — Active + Pending 모두 (Close 제외). `get_portfolio()` 사용 금지 (Active 만) |
| 2 | 0 | **base 만기 + 자동 갱신** ⭐ ⛔ 강제 | `check_base_freshness(auto_refresh=True)` — stale stock_base 자동 refresh + **economy/industry stale 발견 시 즉시 메인 inline 절차 실행** (`references/base-*-update-inline.md`). **자율 스킵 금지** ('효율 우선' / '시간 절약' / '1일 정도는 무시' 등 LLM 의 능동 회피 패턴 차단). 스킵 시 ⚠️ 반쪽 daily 즉시 격상 + 보고서 최상단 ⚠️ 명시 |
| 3 | 1 | 어제 pending 액션 로드 | `get_portfolio_summary(yesterday)` |
| 4 | 1 | 어제 trades 매칭 | `reconcile_actions(yesterday)` |
| 5 | 1 | **오늘 trades 조회** ⭐ | `list_trades(limit=20)` — 오늘 이미 체결된 매매 인지 필수 |
| 6 | 1 | **오늘 trades 매칭** ⭐ | `reconcile_actions(today)` — Phase 1 에서 호출 (종료 루틴이 아님) |
| 7 | 1 | 주간 회고 컨텍스트 | `get_weekly_context(weeks=4)` (→ `weekly-context-rules.md`) |
| 8 | 2 | 시장 국면 판정 | `detect_market_regime()` |
| 9 | 2 | 당일 매크로 / 뉴스 | `WebSearch("YYYY-MM-DD 한국/미국 주식 주요 이슈")` 최소 1회 |
| 10 | 2 | `economy/{오늘}.md` | 없으면 즉시 자동 생성 (`economy-daily-template.md`) |
| 11 | 3 | **종목별 per-stock-analysis 7단계** ⭐ | `references/per-stock-analysis.md` 절차를 #1 결과의 `all_codes` 전부 1회 따라감 (analyze_position raw + base 조회 + WebSearch + LLM 판단 + 저장) |
| 12 | 3 | **(per-stock-analysis 의 5단계 WebSearch 안에 포함됨)** | 별도 호출 X. 절차 위반 (per-stock 5단계 누락) 시 ⚠️ 반쪽 daily |
| 13 | 1 | **월요일 weekly_strategy 점검** (v8) | `get_weekly_strategy()` — 이번 주 미작성 + 월요일 발견 시 ⚠️ "weekly-strategy 미작성, carry-over 사용 중" 알림. 사용자 명시 `/stock-weekly-strategy` 호출 안내 (자동 트리거 X). carry_over=True 면 보고서 최상단에 표기 |
| 14 | 1 | **base 미처리 narrative revision 큐 점검** (라운드 2026-05) | `get_pending_base_revisions(weeks=4)` — `count >= 3` 시 daily 보고서 **최상단 ⚠️ 알림 강제** ("미처리 base narrative revision N건 누적, `/base-stock {code}` 또는 `/base-industry` 처리 권장"). 회고 Phase 3 에서 적재된 사용자 큐 (contradictory + base_refresh_required 케이스) 가 daily 까지 누적되지 않도록 강제 |

**⭐ #1**: `list_daily_positions()` — Active + Pending 일괄 반환. Pending 도 daily 생성.
**⭐ #2** (강제): `auto_refresh=True` 로 KR stock_base 자동 갱신. economy/industry 는 메인 inline 처리 — `references/base-*-update-inline.md` (옛 sub-agent 폐기, 2026-04-30).

> ⛔ **stale 발견 시 강제 진입**. 옛 sub-agent 시절엔 메인이 spawn 호출만 하면 sync wait 로 자동 처리됐지만, inline 화 후엔 메인이 능동 진입 필수. **"효율 우선"·"1일 정도 무시" 스킵 금지** — 매일 강제 갱신이 sub-agent 폐기 결정의 전제 조건임. 스킵하려면 사용자 명시 승인 필요.
**⭐ #5/#6**: 오늘 trades 인지 누락 시 typical bug — executed 매매를 pending 으로 잘못 기재.
**⭐ #11**: 종목 1건당 `references/per-stock-analysis.md` 의 7단계 절차를 그대로 따른다. 그 안에서 base 조회 + `analyze_position` (raw 9 카테고리) + WebSearch + LLM 판단 + 저장이 통합 처리됨. 별도 carving 금지.

긴급 시엔 `/stock-daily --fast` 명시로만 일부 스킵 허용.

### 자기 감사 — `save_portfolio_summary` 직전 출력

→ `~/.claude/skills/stock/assets/dependency-audit-template.md` 참조.

---

## 7-Phase Pipeline (v2)

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 0: 신선도 cascade (deterministic)                      │
│   check_base_freshness() → is_stale per-dim + auto_triggers │
│   stale 시 즉시 메인 inline (references/base-*-update-inline.md) │
├─────────────────────────────────────────────────────────────┤
│ Phase 1: 과거 학습 회수 (어제·오늘 거래 + 주간 회고)          │
│   ├─ get_portfolio_summary(yesterday)                       │
│   ├─ reconcile_actions(yesterday)                           │
│   ├─ list_trades(limit=20)                                  │
│   ├─ reconcile_actions(today)                               │
│   └─ get_weekly_context(weeks=4)                            │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: 시장·매크로 컨텍스트                                 │
│   detect_market_regime() + economy/{오늘}.md                │
├─────────────────────────────────────────────────────────────┤
│ Phase 3: 종목별 per-stock-analysis 순회 (Active + Pending)   │
│   for code in all_codes:                                    │
│     references/per-stock-analysis.md 7단계 절차 그대로 적용 │
│       (base 조회 + analyze_position raw + WebSearch +       │
│        LLM 판단 + save_daily_report)                        │
│     coverage_pct < 80% → ⚠️ 반쪽 분석 표기                  │
├─────────────────────────────────────────────────────────────┤
│ Phase 4: LLM 본문 판단 (Cell + Verdict, 자동 derive 없음)     │
│   cell = LLM 이 변동성 regime + 재무 본문 grade 로 판단     │
│   verdict = signals.summary.종합 (1차) + LLM override 가능  │
├─────────────────────────────────────────────────────────────┤
│ Phase 5: 액션 결정 (LLM 본문 판단 + master-principles)        │
│   → references/master-principles.md 의 10 카테고리 인용     │
│     (구체 수치 X, 케이스별 산업 평균 대비 본문 판단)        │
├─────────────────────────────────────────────────────────────┤
│ Phase 6: 게이트 (deterministic)                               │
│   check_concentration / 예수금 / 실적 D-7 / 수급 z 검증     │
│   실패 시 자동 매매 차단                                     │
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

## 종목별 — `references/per-stock-analysis.md` 7단계 절차 적용

종목 1건 분석 단일 진입점. 본문은 옮기지 않음 — 절차서 직접 인용.

요약:
1. base 신선도 체크 → 2. stale 갱신 (cascade) → 3. base 조회 (3층) → 4. `analyze_position(code)` raw 9 카테고리 → 5. WebSearch → 6. LLM 판단 → 7. `save_daily_report`

`analyze_position` 응답 카테고리 (raw 9):
context / realtime / indicators / signals / financials raw (score 제거) / flow / volatility / events / consensus.
**제거됨**: scoring / cell / is_stale (LLM 본문 판단 위임) / financials.score.

### 포트 단위 — 별도 호출 (per-stock-analysis 외부)

- `detect_market_regime` (Phase 2 — regime)
- `portfolio_correlation(days=60)` (Phase 6 — correlation + effective_holdings)
- `detect_portfolio_concentration` (Phase 6 — concentration)
- `get_weekly_context(weeks=4)` (Phase 1 — backtest 룰 win-rate)
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

- [ ] **base stale 잔여 0 확인** ⛔ — `check_base_freshness()` 재호출, economy/industries 의 `is_stale=true` 카운트 0. 미달이면 BLOCKING #2 위반 (Phase 0 단계 누락) → 즉시 inline 절차 진입 후 재검증
- [ ] 종목별 `save_daily_report` 호출 — `list_daily_positions().counts.total` 만큼 (Active + Pending 포함). 호출 시 **`verdict` 인자 필수** (강한매수/매수우세/중립/매도우세/강한매도 5종 중 1)
- [ ] 종합 `save_portfolio_summary` 호출 — `summary_content` + `per_stock_summary` + `action_plan` 3 인자 모두 채움
- [ ] DB read-back: `list_reports_on_date(today)` 의 row 수 = `all_codes` 수
- [ ] DB read-back: `get_portfolio_summary(today).found == true`
- [ ] 누락 발견 시 즉시 재호출 (보고서 출력 전)

### 자주 빠지는 패턴 (4/29·4/30 사례)

- ❌ "analyze_position × N ✅" 만 적고 save_daily_report 호출 누락 → stock_daily 빈 채로 daily 종료
- ❌ verdict 인자를 None/공백 으로 보내서 verdict 컬럼 NULL 화 (서버 fix 후엔 verdict 무시 안 함)
- ❌ portfolio_summary 본문은 적었지만 `save_portfolio_summary` MCP 호출 안 함

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
- `websearch-rules.md` — WebSearch 의무 + 5종 추가 조건
- `weekly-context-rules.md` — 4가지 활용 룰
- `snapshot-schema.md` — `save_portfolio_summary` JSON 스키마

assets:
- `daily-report-template.md`, `portfolio-summary-template.md`, `position-template.md`, `dependency-audit-template.md`, `economy-daily-template.md`
- `snapshot-schema.md` — `save_portfolio_summary` JSON 스키마

assets:
- `daily-report-template.md` — 종목 daily 본문
- `portfolio-summary-template.md` — 포트폴리오 종합 요약
- `position-template.md` — 보유 종목 position.md
- `dependency-audit-template.md` — Audit 출력 + ⚠️ 반쪽 daily
- `economy-daily-template.md` — economy/{날짜}.md 자동 생성

scripts:
- `detect_market.py` — KR/US 자동 판정
- `concentration_check.py` — 집행 전 집중도 체크 fallback
- `load_deps.py` — 직접 호출 모드 임포트 시퀀스 fallback
