# .claude/skills/stock/ — stock skill 구조 가이드

> 이 폴더는 통합 stock skill (개인 KR/US 포트폴리오 운영) 본체. 본 CLAUDE.md 는 **skill 구조 보존** 과 **신규 reference 추가 절차** 를 다룬다. 워크플로우 작성 규약은 한 단계 깊은 `references/CLAUDE.md` (d4 — 가장 상세) 에 있다.

---

## 1. 3계층 구조 (절대 깨지 말 것)

```
.claude/skills/stock/
├── SKILL.md                   # 진입점 — 모드 라우팅 + 핵심 사실 (모드별 디테일 X)
├── references/<주제>.md       # 워크플로우·룰·체크리스트 (모드 진입 후 inline 호출 단위)
│   └── _archive/              # 폐기된 룩업 보존 (재제안 방지)
└── assets/<*>-template.md     # 출력 포맷 (보고서·회고·포지션·모멘텀 ranking 등)
```

3계층은 라운드 2026-05 의 결정 (`docs/rounds/2026-05-stock-daily-overhaul.md`, `2026-05-weekly-review-overhaul.md`) 으로 정착. 각 계층의 책임은 절대 뒤섞지 않는다.

| 계층 | 책임 | 금기 |
|---|---|---|
| `SKILL.md` | 모드 라우팅 + 도메인 핵심 사실 + 5단계 단일 진입점 (per-stock-analysis) | 모드별 디테일·절차 본문 작성 금지 |
| `references/*.md` | 모드별 워크플로우, base 갱신 절차, 매매 룰, 거장 원칙 등 | 출력 포맷 (템플릿) 직접 작성 금지 — assets/ 로 |
| `assets/*-template.md` | 보고서·회고·포지션·랭킹 등 일관 출력 포맷 | 룰·절차·계산 로직 금지 — references/ 로 |

---

## 2. SKILL.md 책임

- **모드 라우팅 표** — 슬래시 wrapper ↔ 모드 ↔ references 매핑.
- **자연어 의도 추측** — 사용자가 슬래시 안 쓸 때 어떤 모드로 진입할지.
- **종목 1건 단일 진입점** — 모드 무관 5단계 (`references/per-stock-analysis.md`).
- **공통 룰** — 거장 10원칙·rule_catalog DB SSoT 명시·MCP 단일 의존.
- **금지** — 모드별 워크플로우 본문, 매매 룰 디테일, 출력 템플릿, 절차 8-step/Phase 본문.
- **신규 reference 추가 시 SKILL.md 인덱스 갱신 의무** (라우팅 표 또는 공통 룰 섹션에 1줄 추가).

---

## 3. 6 모드 (현재 인벤토리)

| 모드 | wrapper | references 진입점 |
|---|---|---|
| `daily` | `.claude/commands/stock-daily.md` | `references/daily-workflow.md` |
| `discover` | `.claude/commands/stock-discover.md` | `references/discover-workflow.md` |
| `research` | `.claude/commands/stock-research.md` | `references/research-workflow.md` |
| `weekly-strategy` | `.claude/commands/stock-weekly-strategy.md` | `references/weekly-strategy-brainstorm.md` |
| `weekly-review` | `.claude/commands/stock-weekly-review.md` | `references/weekly-review-workflow.md` (4-Phase) |
| `base-{economy,industry,stock}` (3개) | `.claude/commands/base-*.md` | `references/base-{level}-update-inline.md` |

신규 모드 추가 시: (a) `.claude/commands/<name>.md` wrapper 신설 (b) `references/<name>-workflow.md` 본문 작성 (c) SKILL.md 라우팅 표·자연어 추측 표에 행 추가 (d) 필요 시 `assets/<name>-template.md`.

---

## 4. inline 처리 룰 (sub-agent 신설 금지)

- 커밋 `c9e3994 refactor(skill)` 에서 `base-*-updater` sub-agent 폐기 → **메인 Claude 가 inline** 으로 base 갱신 절차 수행.
- 사유: (a) sub-agent 컨텍스트 분리로 base 본문 누수 (b) 모바일/Desktop/iOS 호환성 (c) 결과 검증 단순화.
- **신규 모드도 sub-agent 신설 금지**. 모든 절차는 메인 Claude 가 references 절차 따라 inline 수행.
- inline 절차서 명명 규약: `base-<level>-update-inline.md` (level ∈ {economy, industry, stock}).

---

## 5. base 3계층 cascade

```
economy (거시·금리·환율·시장 regime)
   └─ industry (산업 평균 PER/PBR/ROE/마진/vol_baseline)
         └─ stock (종목 narrative + base 본문 — analyze_position 이 inject)
```

- 한 단계 stale 면 그 단계부터 재작성 (`check_base_freshness` MCP 툴).
- 재작성 절차: 해당 `base-<level>-update-inline.md` 진입 → 메인 inline 실행.
- daily 모드 Phase 1 에서 cascade 자동 점검.

### base-patch vs base-appendback

- **base-patch** (`references/base-patch-protocol.md`) — 소규모 갱신 (예: 컨센 수정, 산업 평균 1건). 만기 연장 X.
- **base-appendback** (`references/base-appendback-protocol.md`) — weekly-review Phase 3 결과를 base 에 역반영. 회고에서 발견된 사실 누적.

`base-impact-on-review.md` 가 회고-base 충돌 4분류 분기 룰 (W18 GOOGL 사례).

---

## 6. rule_catalog DB SSoT

- 매매 룰의 단일 진실은 **DB `rule_catalog` 테이블** (`server/repos/rule_catalog.py`).
- references 의 룰 텍스트 (예: `signals-12.md`, `expiration-rules.md`, `master-principles.md`) 는 **사람이 읽기 위한 사본**.
- Claude 가 markdown 의 룰 텍스트만 보고 매매 판단하면 DB 최신과 어긋남.
- 신규 룰은 `register_rule` MCP 툴로 등록 → 자동 격상 → weekly-review 가 win-rate 산출.
- references 의 룰 markdown 변경 시 DB 동기화 의무 (또는 SSoT 측 우선).

---

## 7. _archive/ 보존 룰 (재제안 방지)

라운드 2026-05 에서 폐기된 룩업·매트릭스는 `references/_archive/` 에 헤더 `> [DEPRECATED YYYY-MM-DD: <라운드>] <사유>` 추가 후 보존:

- `_archive/decision-tree.md` (5×6 매트릭스, 폐기)
- `_archive/scoring-weights.md` (합성 점수 가중치, 폐기)
- `_archive/position-action-rules.md` (6대 룰, 폐기)
- (잠재) `_archive/12셀 매트릭스`, base-*-updater sub-agent 절차서

**재제안 금지 목록** (Claude 가 다시 만들려고 시도하기 쉬움):
- 매트릭스 룩업 (volFinMatrix, 12셀, 5×6 decision-tree).
- 합성 점수·셀·is_stale 같은 deterministic anchor.
- 룰 markdown 단일 SSoT (DB 가 SSoT).
- base 갱신 sub-agent (inline 처리로 통일됨).

폐기 처리 절차 디테일은 `references/CLAUDE.md` §4 참조.

---

## 8. assets/ 템플릿 출력

- `daily-report-template.md`, `portfolio-summary-template.md` — daily 모드 출력.
- `weekly-review-per-stock-template.md` (Phase 1 8-step), `weekly-review-portfolio-template.md` (Phase 2 6-section) — 4-Phase weekly-review 출력.
- `weekly-review-template.md` — deprecated 헤더 보존 (Phase 분리 전 단일 템플릿).
- `discover-output-template.md`, `momentum-ranking-template.md`, `score-block-template.md`, `position-template.md`, `economy-base-template.md`, `industry-base-template.md`, `base-stock-template.md`, `economy-daily-template.md`, `rebalance-template.md`, `dependency-audit-template.md`.
- 신규 모드/리포트 추가 시 `assets/<name>-template.md` 신설 후 references 에서 참조.

---

## 9. 진입점 안내 (자기 CLAUDE.md 보유)

| 폴더 | 가이드 |
|---|---|
| `references/` | `.claude/skills/stock/references/CLAUDE.md` (**d4 — 가장 상세**) — 36 reference 작성 규약·_archive 처리·폐기 절차·길이 가이드·Phase 매핑 |
| `assets/` | (별도 CLAUDE.md 없음 — 본 파일 §8 참고) |
| 슬래시 wrapper 폴더 | `.claude/commands/CLAUDE.md` (d2) — wrapper 패턴 |

본 폴더에 신규 reference 작성·기존 reference 폐기 작업 시 **반드시 `references/CLAUDE.md` 먼저 진입**.

---

## 10. 신규 reference 추가 체크리스트 (요약 — 디테일은 references/CLAUDE.md)

1. 파일명 규약 확인 (`<mode>-workflow.md`, `<topic>-rules.md`, `base-<level>-update-inline.md` 등).
2. 길이 100~300줄 (더 길면 분할).
3. 절차서면 단계 번호 (Phase 또는 8-step) 부여.
4. SKILL.md 인덱스 (라우팅 표 / 공통 룰) 갱신.
5. DB `rule_catalog` 와 충돌 검토 — 룰 텍스트면 SSoT 측 우선.
6. 매트릭스/합성 점수/sub-agent 등 폐기 항목 재제안 검토 — 해당 시 즉시 중단.
7. assets/ 템플릿 매칭 (출력 포맷 있으면).
8. 라운드 doc (`docs/rounds/`) 업데이트 — 큰 결정이면 신규 라운드 doc 또는 기존 라운드에 추가.

---

## 11. 본 skill 외부에 두지 말 것

- 매매 시그널 계산·매수/매도 임계값 분기 → 백엔드 (`server/analysis/`, `server/repos/rule_catalog.py`).
- 출력 포맷 → `assets/`.
- 슬래시 진입 안내 → `.claude/commands/<name>.md` (wrapper 만, 로직 X).
- DB 저장 룰·테이블 디자인 → `db/CLAUDE.md` + `server/repos/CLAUDE.md`.
- MCP 툴 등록 패턴 → `server/mcp/CLAUDE.md`.
