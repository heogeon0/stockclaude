# .claude/skills/stock/references/ — reference 작성 규약 (가장 상세)

> 본 폴더는 stock skill 의 **워크플로우·룰·체크리스트** 본체. SKILL.md 가 모드 라우팅만 담당하고 모든 절차 디테일은 여기에 산다. 36 개 reference 파일 (+ `_archive/` 폐기 보존).
>
> 본 CLAUDE.md 는 **계층적 CLAUDE.md 트리에서 가장 깊은 d4** — 가장 상세한 규약. 신규 reference 작성·기존 reference 폐기·라운드 결정 반영 시 **반드시 본 파일 통과**.

---

## 1. 파일명 규약 (강제)

| 패턴 | 의미 | 예시 |
|---|---|---|
| `<mode>-workflow.md` | 모드별 워크플로우 (BLOCKING + Phase Pipeline) | `daily-workflow.md`, `discover-workflow.md`, `research-workflow.md`, `weekly-review-workflow.md` |
| `<mode>-brainstorm.md` | 브레인스토밍 절차 (사용자+LLM 대화형) | `weekly-strategy-brainstorm.md` |
| `base-<level>-update-inline.md` | base 갱신 inline 절차서 (메인이 직접 수행) | `base-economy-update-inline.md`, `base-industry-update-inline.md`, `base-stock-update-inline.md` |
| `base-<protocol>-protocol.md` | base 변경 메타 프로토콜 | `base-patch-protocol.md`, `base-appendback-protocol.md` |
| `<topic>-rules.md` | 룰셋 (체크리스트 또는 임계값) | `expiration-rules.md`, `websearch-rules.md`, `weekly-context-rules.md` |
| `<topic>-classification.md` | 분류 룩업 (n분류 분기) | `economy-base-classification.md`, `industry-base-classification.md`, `stock-base-classification.md`, `base-impact-classification.md`, `base-impact-on-review.md` |
| `<topic>.md` | 개념·원칙·표준 (단일 주제) | `master-principles.md`, `per-stock-analysis.md`, `signals-12.md`, `momentum-6dim-scoring.md`, `valuation-frameworks.md`, `narrative-10-key-points.md` |

**금지**: 자유 명명 (예: `my-new-flow.md`, `notes.md`). 신규 reference 는 위 패턴 중 하나로 매핑.

---

## 2. 1 reference = 1 워크플로우/룰셋

- 한 파일은 한 가지 절차 또는 한 가지 룰셋만 담는다.
- 모드 진입 후 inline 호출 가능한 단위 (Claude 가 1회 컨텍스트 로드 후 끝까지 따름).
- 파일이 두 가지 책임을 가지면 분할.
- 다른 reference 를 인용 (예: `master-principles.md` 의 10원칙) 할 때는 경로 명시 — 본문 복사 X.

---

## 3. 절차서 형식 (Phase / 단계 번호 의무)

절차를 가진 reference 는 단계 번호를 부여한다. 라운드 2026-05 에서 표준화된 패턴:

### 3.1 per-stock-analysis 5단계 (v6 단순화, `per-stock-analysis.md`)

종목 1건 분석은 모드 무관 항상 동일 5단계:
1. stale 조회 (`check_base_freshness`)
2. stale 갱신 (cascade economy → industry → stock, 발견 시만)
3. 종목 분석 (`analyze_position(code, include_base=True)` 1 MCP — 12 카테고리)
4. LLM 종합 판단 (필요 시 자율 WebSearch)
5. 출력 + 저장 (`save_daily_report`, verdict 5종)

이 5단계는 daily / research / discover 진입점에서 동일 호출. 이전의 7~8 reference 분산은 폐기됨.

### 3.2 daily-workflow BLOCKING + 7-Phase Pipeline (`daily-workflow.md`)

- **BLOCKING 14 개** (Phase 0~1) — 누락 시 결과 최상단 ⚠️ 명시.
- **Phase 0** — 시장 routing + KST 거래일 확정.
- **Phase 1** — base cascade 점검 + `pending_base_revisions` count 체크 (#14 BLOCKING).
- **Phase 2** — 포트 단위 (`detect_market_regime`, `portfolio_correlation`, `detect_portfolio_concentration`, `get_weekly_context`).
- **Phase 3** — 종목별 5단계 (per-stock-analysis) 순회 (Active + Pending).
- **Phase 4~7** — 종합 / 매매 추천 / 보고서 생성 / DB read-back 검증.

### 3.3 weekly-review 4-Phase (`weekly-review-workflow.md`, 라운드 2026-05)

| Phase | 내용 | 출력 템플릿 |
|---|---|---|
| Phase 1 | 종목별 회고 8-step (per-stock 단위) | `assets/weekly-review-per-stock-template.md` |
| Phase 2 | 포트폴리오 종합 6-section | `assets/weekly-review-portfolio-template.md` |
| Phase 3 | base 역반영 (4분류 분기 — `base-impact-on-review.md`) | base 본문 직접 수정 + `base-appendback-protocol.md` |
| Phase 4 | 룰 win-rate 분류 + `learned_patterns` 누적 | DB 직접 (`register_rule` / `promote_learned_pattern`) |

신규 reference 가 weekly-review 흐름에 들어가면 어느 Phase 인지 헤더에 명시.

### 3.4 weekly-strategy 5단계 (`weekly-strategy-brainstorm.md`, v8)

사용자+LLM 브레인스토밍. 자연어 패턴 → `learned_patterns` 누적 → daily 분석이 인용. 단계 번호 명시.

---

## 4. 폐기 처리 절차 (재제안 방지 — 가장 중요)

라운드 2026-05 에서 결정된 폐기 룩업·매트릭스·sub-agent 는 다음 절차로 처리.

### 4.1 5단계 폐기 절차

1. **이동** — `_archive/<원파일명>.md` 로 mv (디렉토리 그대로 보존).
2. **헤더 추가** — 파일 최상단에 `> [DEPRECATED YYYY-MM-DD: <라운드>] <폐기 사유 1~2줄>` 표시.
3. **본문 보존** — 절대 본문 삭제 금지. Claude 가 다시 제안하려고 할 때 _archive 본문을 보고 "이미 폐기됨" 인지하기 위함.
4. **SKILL.md 인덱스 제거** — 라우팅 표·공통 룰 섹션에서 해당 reference 참조 제거.
5. **라운드 doc 명시** — `docs/rounds/<YYYY-MM-주제>.md` 의 "폐기" 섹션에 파일명·사유 기록.

### 4.2 폐기 사례 (현 인벤토리)

| 폐기 항목 | 위치 | 라운드 | 사유 |
|---|---|---|---|
| `decision-tree.md` (5×6) | `_archive/` | 2026-05-stock-daily-overhaul | anchor 효과 + 검증 안 된 직관 |
| `scoring-weights.md` (합성 점수 가중치) | `_archive/` | 2026-05-stock-daily-overhaul | 합성 점수가 LLM 본문 추론 anchor |
| `position-action-rules.md` (6대 룰) | `_archive/` | 2026-05-stock-daily-overhaul | 매트릭스 룩업 폐기 |
| 12셀 매트릭스 (volFinMatrix) | (잠재 — 프론트 잔재 §10.4) | 2026-05-stock-daily-overhaul | 재제안 금지 |
| base-*-updater sub-agent 절차서 | (커밋 c9e3994 로 inline 통합) | 2026-04-30 | sub-agent 컨텍스트 분리로 base 본문 누수 |

### 4.3 재제안 금지 목록 (Claude 가 무의식적으로 다시 만들려는 패턴)

- **매트릭스 룩업** — volFinMatrix, 12셀, 5×6 decision-tree 등 n×m 표 룩업.
- **합성 점수** — analyze_position 에 `score / cell / is_stale` 같은 deterministic anchor 재도입 금지. raw 9 카테고리 유지.
- **룰 markdown 단일 SSoT** — DB `rule_catalog` 가 SSoT. references 룰 텍스트는 사람이 읽기용.
- **base 갱신 sub-agent** — inline 처리로 통일됨 (c9e3994).
- **단계 분산** — per-stock-analysis 5단계를 다시 7~8 reference 로 쪼개려는 시도 금지.

신규 reference 작성 중 위 패턴이 부활하면 즉시 중단하고 사용자 확인.

---

## 5. master-principles 톤 (거장 10원칙)

라운드 2026-05 에서 매트릭스 폐기 후 도입된 단일 룰 출처는 `master-principles.md` (Livermore / Minervini / O'Neil / Weinstein / Buffett / Marks / PTJ / Lynch). **추상 방향성만, 구체 수치 X**.

10 카테고리:
1. 손익 관리 (Cut losses, let winners run)
2. 추세 추종 (The trend is your friend)
3. 변동성 관리
4. 사이클 인식 (Stage Analysis)
5. 재무 우량 + 모멘텀 (SEPA / CAN SLIM)
6. 이벤트 리스크
7. Top-down (시장 → 산업 → 종목)
8. 인내와 규율 (Wait for fat pitches)
9. 자본 보호 (Mark-to-market)
10. 자기 인식 (Know thyself, Trade your own personality)

신규 룰 reference 작성 시 위 10 카테고리 중 어디에 속하는지 헤더에 명시. 구체 수치 (예: 손절 -7%) 는 LLM 자율 판단 + 산업 평균 (industries.avg_*) 대비.

---

## 6. rule_catalog DB SSoT 통합

- 매매 룰의 단일 진실은 DB `rule_catalog` (`server/repos/rule_catalog.py`).
- references 룰 텍스트 (`signals-12.md`, `expiration-rules.md`, `rule-catalog.md`) 는 사람이 읽기 위한 사본.
- 신규 룰은 `register_rule` MCP 툴 → 자동 등록 + 격상 + win-rate 자동 분류.
- `learned_patterns` (자연어 패턴) → 검증 후 `promote_learned_pattern` 으로 정식 룰 격상.
- references 룰 markdown 변경 시 (a) DB 동기화 또는 (b) 명시적 deprecate 헤더.

---

## 7. base 4계층 (cascade + 회고-base 분기)

```
economy → industry → stock → (회고) base-impact-on-review
```

| 파일 | 역할 |
|---|---|
| `base-economy-update-inline.md` | 거시·금리·환율·시장 regime 갱신 inline 절차 |
| `base-industry-update-inline.md` | 산업 평균 PER/PBR/ROE/마진/vol_baseline 갱신 |
| `base-stock-update-inline.md` | 종목 narrative 본문 갱신 (analyze_position inject 대상) |
| `base-patch-protocol.md` | 소규모 갱신 (만기 연장 X) |
| `base-appendback-protocol.md` | weekly-review Phase 3 결과 base 역반영 |
| `base-impact-on-review.md` | 회고-base 충돌 4분류 분기 (W18 GOOGL 사례) |
| `base-impact-classification.md` | base 영향 분류 룩업 |
| `economy-base-classification.md` / `industry-base-classification.md` / `stock-base-classification.md` | 각 계층 base 분류 룩업 |

**stale 감지 시 cascade**: economy stale → economy 부터 재작성. industry stale → industry 부터. stock stale → stock 만.

---

## 8. BLOCKING 룰 번호 부여 의무

daily-workflow 의 BLOCKING 룰은 번호로 식별 (#1~#14, 2026-05 라운드에서 12 → 14 확장). 신규 BLOCKING 룰 추가 시:

1. 마지막 번호 + 1 부여 (현재 최신은 #14 = `get_pending_base_revisions` count≥3 ⚠️).
2. `daily-workflow.md` Phase 0 또는 Phase 1 에 추가.
3. 누락 시 결과 최상단 ⚠️ 명시 동작 정의.
4. SKILL.md 의 BLOCKING 카운트 갱신.

---

## 9. 길이 가이드

| 길이 | 분류 | 처리 |
|---|---|---|
| 100~200줄 | 단일 절차 | 권장 — 1회 로드로 끝 |
| 200~300줄 | 큰 워크플로우 (4-Phase 등) | OK — Phase 별 헤더로 항해 |
| 300줄+ | 분할 검토 | (a) Phase 단위 분할 (b) 룰셋 분리 (c) 어려우면 헤더 명확히 |
| 100줄- | 너무 짧음 | 다른 reference 와 병합 검토 |

본 references/ 폴더는 모드 진입 후 1회 로드. 너무 길면 컨텍스트 비효율.

---

## 10. 한글 톤

- 본문: 한국어 (라운드 2026-05 표준).
- 식별자·SQL·MCP 툴명·테이블명: 영어 (`analyze_position`, `rule_catalog`, `executed_at AT TIME ZONE 'Asia/Seoul'`).
- 코드블록 주석: 영어 또는 한국어 (일관성 우선).
- 룰 헤더 prefix: `⚠️` (함정·경고), `⛔` (절대 금지·BLOCKING), `⭐` (라운드 신설 핵심).

---

## 11. 신규 reference 추가 체크리스트 (10단계)

1. **파일명 규약** — §1 패턴 매핑.
2. **헤더 메타** — 첫 줄에 `> 라운드 / 모드 / 진입점` 명시. 폐기되면 `> [DEPRECATED ...]`.
3. **절차 본문** — Phase 또는 단계 번호 부여 (§3).
4. **assets/ 템플릿 매칭** — 출력 포맷 있으면 `assets/<name>-template.md` 신설 또는 기존 매칭.
5. **SKILL.md 인덱스 갱신** — 라우팅 표 / 공통 룰 / BLOCKING 카운트.
6. **DB rule_catalog 동기화** — 룰 텍스트면 SSoT 확인 (§6).
7. **폐기 항목 충돌 검토** — §4.3 재제안 금지 목록 위반 여부.
8. **master-principles 톤** — 추상 방향성, 구체 수치는 LLM 자율.
9. **라운드 doc 업데이트** — 큰 결정이면 `docs/rounds/<YYYY-MM-주제>.md` 신규 또는 기존에 추가.
10. **smoke** — Claude 가 본 reference 만 읽고 절차 따라갈 수 있는지 흐름 검증.

---

## 12. 폐기 reference 추가 체크리스트 (5단계)

1. `_archive/<원파일명>.md` 로 mv.
2. 헤더 `> [DEPRECATED YYYY-MM-DD: <라운드>] <사유 1~2줄>` 추가.
3. 본문 보존 (재제안 방지).
4. SKILL.md 인덱스에서 참조 제거.
5. 라운드 doc 의 "폐기" 섹션에 파일명·사유 기록.

---

## 13. 현 인벤토리 (36 reference + 3 _archive)

### Active reference (모드/주제별)

- **모드 워크플로우** — `daily-workflow.md`, `discover-workflow.md`, `research-workflow.md`, `weekly-review-workflow.md`, `weekly-strategy-brainstorm.md`.
- **단일 진입점** — `per-stock-analysis.md` (5단계).
- **base 갱신** — `base-economy-update-inline.md`, `base-industry-update-inline.md`, `base-stock-update-inline.md`, `base-patch-protocol.md`, `base-appendback-protocol.md`, `base-impact-on-review.md`, `base-impact-classification.md`.
- **base 분류** — `economy-base-classification.md`, `industry-base-classification.md`, `stock-base-classification.md`.
- **룰셋** — `master-principles.md` (거장 10원칙), `rule-catalog.md`, `signals-12.md`, `expiration-rules.md`, `websearch-rules.md`, `weekly-context-rules.md`.
- **분석 프레임** — `momentum-6dim-scoring.md`, `momentum-filters.md`, `momentum-principles.md`, `valuation-frameworks.md`, `narrative-10-key-points.md`, `six-dim-analysis.md`.
- **discover/research 보조** — `discover-filters.md`, `theme-keywords.md`, `industry-sectors.md`, `market-routing.md`, `analyst-consensus-tracking.md`, `deal-radar-checklist.md`, `overheat-thresholds.md`, `snapshot-schema.md`.

### `_archive/` (폐기 보존)

- `decision-tree.md` (5×6 매트릭스)
- `scoring-weights.md` (합성 점수 가중치)
- `position-action-rules.md` (6대 룰)

---

## 14. 본 references/ 외부에 두지 말 것

- 모드 라우팅·진입 안내 → `SKILL.md`.
- 출력 포맷 (보고서 템플릿) → `assets/`.
- 슬래시 진입 안내 → `.claude/commands/<name>.md`.
- 룰 본문 SSoT → DB `rule_catalog` (markdown 은 사람이 읽기용 사본).
- 매매 시그널 계산 로직 → `server/analysis/`.
- 출력 페이로드 normalize (`_json_safe`) → `server/mcp/server.py`.
