# Round 2026-05 — daily 워크플로우 강화 (Phase 2 매크로 BLOCKING + base stale 분산 + WebSearch BLOCKING 복원)

> **요약**: (1) Phase 2 매크로 4종 BLOCKING + economy_base 갱신 자기완결 phase 신설.
> (2) base stale 체크를 phase별 자기 영역으로 분산 — `check_base_freshness(scope, code, auto_refresh)` 인자 추가.
> (3) v7 WebSearch 자율 정책 부분 회귀 — 도메인 화이트리스트 (Tier 1~4) 기반 단계별 BLOCKING 복원.
>
> 이전 라운드 `cfccf7a (#9)` "WebSearch 의존도 감축 1차" 의 자율 정책이 daily 운영에서 정형 미커버 nuance (발언 톤·지정학·점유율·기술·경쟁사 동향·규제) 누락을 유발 — Trust but verify 보강.
>
> 영향 11 파일 (백엔드 1 + 테스트 1 + skill 7 + 라운드 1 + 신규 skill 1).

---

## 1. TL;DR (작업 전 → 작업 후)

| 측면 | 작업 전 | 작업 후 |
|---|---|---|
| base stale 체크 | Phase 0 통합 (`check_base_freshness(auto_refresh=True)` 1회로 economy/industry/stock 3계층 동시 점검) | Phase 별 자기 영역 분산 — Phase 2 economy / Phase 3 stock·industry (cascade) |
| Phase 2 매크로 호출 | LLM 자율 (종종 누락) | `detect_market_regime` / `get_macro_indicators_us/kr` / `get_yield_curve` / `get_fx_rate` **BLOCKING 4~5종** |
| economy_base 갱신 위치 | Phase 0 cascade 자동 | **Phase 2 자기완결** — 매크로 BLOCKING 결과를 1차 소스로 재사용 후 inline 진입 |
| WebSearch 강도 | v7 자율 (강제 횟수 X) | 단계별 BLOCKING 복원 — economy 2회 / industry 2회 / stock 딜레이더 #3·#4 각 1회 / per-stock 1회 |
| 도메인 통제 | 권장만 (강제 X) | **화이트리스트 4 Tier** (`websearch-domains.md` 신규) — 매치 0 시 재검색 |
| 인용 형식 | 자유 | **`(매체, YYYY-MM-DD)` 인라인 의무** — 본문 직접 노출 |
| `check_base_freshness` 시그니처 | `(auto_refresh: bool=False)` | `(scope: str="all", code: str|None=None, auto_refresh: bool=False)` |

---

## 2. 작업 원인

### 2.1 한계 3가지

| # | 한계 | 영향 |
|---|---|---|
| **A** | Phase 0 통합 stale 체크가 한 번에 3계층 — economy / industry / stock 책임 위치 모호 | economy 갱신이 Phase 0 에서 끝나면 Phase 2 매크로 호출이 "이미 끝났다" 착각 → 실제 매크로 데이터 본문 누락 |
| **B** | v7 자율 정책이 daily 에서 정형 미커버 nuance 일관 누락 | 발언 톤 / 지정학 / 점유율 / 기술 / 경쟁사 동향 / 규제 — 정형 자산 거의 없는데 search skip OK 로 해석되어 본문이 정형 수치만 반영 |
| **C** | WebSearch 호출 시 노이즈 도메인 (블로그 / 커뮤니티 / SeekingAlpha 개인기고) 인용 위험 | base 가 30일 동안 daily/research 가 참조하는 정식 문서인데 출처 신뢰도 낮음 |

### 2.2 함정

- **anchor 효과 재발 위험**: 강제 BLOCKING 횟수 N을 다시 도입하면, LLM 이 "N회 채우기 위한 search" 로 변질될 수 있음 → 본 라운드는 **단계별** + **도메인 Tier 한정** 으로 횟수만이 아닌 출처 품질도 가드.
- **5분 TTL 캐시 우회**: 같은 분 내 동일 쿼리 재호출은 의미 없음. 본 라운드는 같은 분 내 정형/WebSearch 모두 캐시 OK 명시 (BLOCKING 횟수 산정 시 캐시 hit 도 1회로 간주).
- **Phase 0 통합 부활 유혹**: 코드만 보면 `check_base_freshness(auto_refresh=True)` 가 한 줄로 끝나서 깔끔해 보이지만, 책임 위치 모호 + economy/industry/stock 만기 다른데 한 번에 묶임 → 분산 결정.

---

## 3. 갈림길 결정

| # | 갈림길 | 선택 | 이유 |
|---|---|---|---|
| **R1** | base stale 체크 centralize (Phase 0 통합) vs distribute (각 phase 자기 영역 소유) | **distribute** | economy 1일 만기 / industry 7일 / stock 30일 — 만기 다르고 갱신 주체 다름. 각 phase 가 자기 base 책임 → top-down 정합 |
| **R2** | Phase 2 매크로를 LLM 자율 vs BLOCKING | **BLOCKING 4~5종** | 매크로는 모든 종목 분석의 anchor — 누락 시 economy_base 본문이 stale 한 채 종목 분석 진입. 자율로는 일관성 X |
| **R3** | WebSearch 강제 횟수만 N회 (v7 회귀) vs 단계별 BLOCKING + 도메인 Tier | **단계별 + Tier** | 횟수만 강제하면 노이즈 도메인 탑재 위험 — 단계 (economy/industry/stock) 와 Tier (글로벌 매체/공식 기관/산업 전문/KR) 매핑이 출처 품질도 가드 |
| **R4** | 도메인 화이트리스트 본 reference 분산 vs 단일 출처 | **단일 출처** (`websearch-domains.md` 신규, W2 산출물) | 도메인 리스트 추가·검증·폐기 시 1 파일만 수정 — 다른 reference 는 참조만 |
| **R5** | BLOCKING 누락 시 daily 자체 중단 vs 최상단 ⚠️ 보고 | **⚠️ 보고** (현재) | 중단은 운영 마비 위험. 보고서 최상단 ⚠️ 로 사용자 가시성 확보 후 다음 라운드에서 검토 |

---

## 4. 새 워크플로우 / 새 컬럼 / 새 MCP 인자

### 4.1 백엔드 — `check_base_freshness(scope, code, auto_refresh)` 인자 추가 (W1)

```python
def check_base_freshness(
    scope: str = "all",                    # "all" | "economy" | "industry" | "stock"
    code: str | None = None,               # scope ∈ {"industry","stock"} 일 때만 의미
    auto_refresh: bool = False,            # 기존 호환
) -> dict:
    """
    Phase 2: check_base_freshness(scope="economy") — economy_base stale 만 점검
    Phase 3 per-stock: check_base_freshness(scope="stock", code=code) — 그 종목의 stock_base + 해당 산업 industry_base 만
    """
```

호환성: 기존 `check_base_freshness()` 호출 (default `scope="all"`) 동작 그대로.

테스트 5건 추가 (`tests/server_mcp/test_daily_blocking.py`):
- `test_check_base_freshness_scope_economy_only`
- `test_check_base_freshness_scope_stock_with_code`
- `test_check_base_freshness_scope_industry`
- `test_check_base_freshness_scope_all_unchanged` (회귀 가드)
- `test_check_base_freshness_invalid_scope_raises`

### 4.2 daily-workflow Phase 2 — 매크로 + economy 자기완결 (W2)

```
Phase 2 — 매크로 + economy_base 갱신 (자기완결)
1. check_base_freshness(scope="economy")           ← Phase 2 자기 체크
2. detect_market_regime()                          ┐
3. get_macro_indicators_us(...)                    │
4. get_macro_indicators_kr(...)                    │ BLOCKING 4~5종
5. get_yield_curve()                               │
6. get_fx_rate("DEXKOUS")                          ┘
7. (선택) get_economic_calendar(days=7)
8. WebSearch 2회 BLOCKING — 발언 톤(Tier 1+2) + 지정학(Tier 1)
9. economy stale → base-economy-update-inline.md 진입
   ↳ 위 매크로 결과를 1차 소스로 재사용 (재호출 X — 같은 분 내 캐시)
```

### 4.3 Phase 3 per-stock 5단계 (W2)

```
1. check_base_freshness(scope="stock", code=code)   ← economy 제외, industry+stock 만
2. cascade industry → stock (stale 발견 시 inline)
3. analyze_position(code, include_base=True)
4. LLM 종합 판단 + WebSearch 1회 BLOCKING (Tier 1 글로벌 매체 + Tier 4 KR 매체 KR 종목이면)
5. 출력 + 저장
```

### 4.4 base inline 절차 3종 — WebSearch BLOCKING 추가 (W3, 본 라운드)

| 절차 | BLOCKING |
|---|---|
| `base-economy-update-inline.md` | 2회 — search 1 (발언 톤, Tier 1+2) + search 2 (지정학, Tier 1) |
| `base-industry-update-inline.md` | 2회 — search 1 (점유율, Tier 3) + search 2 (기술 트렌드, Tier 3) |
| `base-stock-update-inline.md` | 2회 — 딜레이더 #3 경쟁사 (Tier 1) + #4 규제 (Tier 2 공식 기관 우선) |

### 4.5 도메인 화이트리스트 4 Tier (W2 — `websearch-domains.md` 신규)

본 라운드 W3 산출물에서는 리스트 직접 작성 X. 단일 출처 (`references/websearch-domains.md`) 참조만. 4 Tier 개요만 본 라운드 doc 에 명시:

- **Tier 1** — 글로벌 매체 (Bloomberg / Reuters / FT / WSJ / Nikkei / CNBC)
- **Tier 2** — 공식 기관 (Fed / SEC / BLS / BOK / FSC / FSS / MOEF / ECB / europa.eu)
- **Tier 3** — 산업 전문 (Gartner / IDC / Counterpoint / Statista / SemiAnalysis / TrendForce / Omdia)
- **Tier 4** — KR 매체 (한경 / 매경 / 이데일리 / 더벨 / 머니투데이)

단계×Tier 매핑은 `websearch-domains.md` 본문 참조.

### 4.6 Quality Gate

- 인용 의무: 모든 WebSearch 인용에 `(매체, YYYY-MM-DD)` 인라인 — 본문 직접 노출 (각주·끝주 X).
- 5분 TTL 캐시: 같은 분 내 동일 쿼리 재호출은 캐시 hit 으로 간주 (BLOCKING 횟수 산정 시 1회 카운트).
- 화이트리스트 매치 0: 재검색 (도메인 한정 쿼리 다시 작성).

---

## 5. 폐기 항목

### 5.1 v7 "WebSearch 강제 횟수만 N회" 자율 정책 (회귀)

라운드 `cfccf7a (#9) — WebSearch 의존도 감축 1차` (2026-04) 에서 도입한 v7 가이드.

- 위치: `.claude/skills/stock/references/websearch-rules.md` v7 (W2 가 v8 로 전면 개정).
- 폐기 사유: daily 운영에서 정형 미커버 nuance 일관 누락 (한계 #B). 자율 정책의 "정형 미커버 nuance 발견 시 LLM 자율" 분기가 LLM 의 "정형으로 충분 — search skip" 판단으로 한쪽에 쏠림.
- 보존 위치: `references/_archive/websearch-rules-v7.md` (W2 가 처리 — 본 W3 작업 범위 외).

### 5.2 Phase 0 통합 stale 체크 (`check_base_freshness(auto_refresh=True)` 한 번에 3계층)

라운드 `f2d3188` 의 daily-workflow.md Phase 0 통합 패턴.

- 폐기 사유: 만기 다른 3계층 (economy 1일 / industry 7일 / stock 30일) 한 번에 묶임 + economy 갱신이 Phase 0 에서 끝나면 Phase 2 매크로 호출 누락 유발.
- 보존: 코드 호환성 위해 `auto_refresh=True` 인자는 유지 (default False). daily-workflow Phase 0 에서 더 이상 호출 X.

---

## 6. 재제안 금지 (가장 중요 — 미래 LLM이 다시 만들지 않도록)

> 본 라운드 doc 진입 시 가장 먼저 읽을 섹션. Claude 가 무의식적으로 다시 만들려고 시도하기 쉬운 5 패턴.

### 6.1 화이트리스트 외 도메인 사용

- 블로그 (네이버 / 티스토리 / Medium 개인) / 커뮤니티 (Reddit / X / DCInside / Pann) / SeekingAlpha 개인 기고 / AI 생성 사이트 — 모두 금지.
- "신뢰도 낮음" 한 줄 코멘트로 사용 정당화 X — 즉시 재검색.
- 신규 도메인 추가 시 `references/websearch-domains.md` 단일 출처에 라운드 doc 통해 추가 (본 reference 에서 직접 추가 X).

### 6.2 WebSearch 결과 인용 (도메인 + 날짜) 누락

- 인용 형식 `(매체, YYYY-MM-DD)` 본문 인라인 의무. 각주 / 끝주 / "출처: ..." 별도 섹션 분리 금지.
- 인용 누락 = 자체 추론으로 변질 → 30일/7일/1일 후 재진입 시 출처 추적 불가.

### 6.3 5분 TTL 캐시 우회 (같은 분 내 재호출)

- 같은 분 내 동일 쿼리 재호출은 정형 MCP / WebSearch 모두 캐시 OK — BLOCKING 횟수 산정 시 캐시 hit 도 1회로 간주.
- "fresh 데이터 보장" 명목으로 1분 내 동일 쿼리 재호출 패턴 만들기 금지.

### 6.4 Phase 0 통합 stale 체크 부활

- `check_base_freshness(scope="all", auto_refresh=True)` 를 daily Phase 0 에서 한 번 호출하면 끝, 같은 패턴 재제안 금지.
- economy / industry / stock 만기 다름 + Phase 책임 위치 다름 → 분산 결정 (R1).

### 6.5 economy_base 갱신 절차에서 매크로 호출 누락

- `base-economy-update-inline.md` 1단계 정형 MCP 1차 소스는 Phase 2 BLOCKING 결과 재사용 (같은 분 캐시) — 본문에 매크로 수치 반영 의무.
- "매크로는 daily Phase 2 가 이미 호출했으니 본 inline 절차에선 skip" 패턴 금지 — 본문 작성 시 매크로 수치 인용 필요.

---

## 7. 영향받은 파일 (11)

### 백엔드 (W1, 2)

- `server/mcp/server.py` — `check_base_freshness(scope, code, auto_refresh)` 인자 추가
- `tests/server_mcp/test_daily_blocking.py` — scope 분기 테스트 5건

### skill 핵심 (W2, 5)

- `.claude/skills/stock/SKILL.md` — BLOCKING 카운트 갱신 + WebSearch 도메인 화이트리스트 진입점 명시 + 라운드 인덱스 1줄
- `.claude/skills/stock/references/daily-workflow.md` — Phase 0 통합 stale 제거, Phase 2 자기완결 신설, Phase 3 5단계 갱신
- `.claude/skills/stock/references/per-stock-analysis.md` — step 1 `scope="stock", code=code`, cascade economy 제외, step 4 WebSearch BLOCKING
- `.claude/skills/stock/references/websearch-rules.md` — v8 BLOCKING 복원 + 도메인 화이트리스트 위임
- `.claude/skills/stock/references/websearch-domains.md` (신규) — 4 Tier 단일 출처

### base inline (W3, 본 라운드, 3)

- `.claude/skills/stock/references/base-economy-update-inline.md` — WebSearch 2회 BLOCKING (발언 톤 + 지정학)
- `.claude/skills/stock/references/base-industry-update-inline.md` — WebSearch 2회 BLOCKING (점유율 + 기술 트렌드)
- `.claude/skills/stock/references/base-stock-update-inline.md` — 딜레이더 #3 (경쟁사) + #4 (규제) WebSearch 1회씩 BLOCKING

### 라운드 (1)

- `docs/rounds/2026-05-daily-workflow-tightening.md` (본 파일)

---

## 8. 후속 라운드 후보

- **WebSearch 캐시 백엔드** — 현재 5분 TTL 은 Claude 자율 (캐시 hit 판정도 LLM). 더 정확한 5분 TTL 보장 필요 시 백엔드 캐시 (`web_search_cache` 테이블 + MCP 헬퍼) 추가.
- **도메인 화이트리스트 확장·검증** — 실 daily 운영 4~12주 후 누적 인용 도메인 통계 산출 → Tier 분류 재검토. 누락 도메인 발견 시 본 라운드 후속에 추가.
- **BLOCKING 누락 시 daily 자체 중단 옵션** — 현재 ⚠️ 보고만. 사용자 운영 패턴 안정 후 "BLOCKING 위반 N건 이상 시 중단" 임계 도입 검토.
- **WebSearch quality 측정 인프라** — 인용 도메인 통계 / Tier 분포 / 인용 누락률 / 화이트리스트 매치율. weekly-review Phase 2 6-section 에 1 섹션 추가 검토.
- **Tier 5 (학술) 신설** — arxiv.org / nature.com / science.org 등 산업별 base 의 기술 트렌드 search 에서 학술 자료가 산업 전문 (Tier 3) 보다 신뢰 높을 때 별도 Tier 분리 검토.
