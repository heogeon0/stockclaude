# docs/rounds/ — 라운드 회고 문서 (깊이 2)

> **목적**: 큰 결정 라운드의 회고를 모은 폴더. 새 세션이 "왜 지금 구조가 이런가 / 무엇이 폐기됐나 / 무엇을 다시 제안하면 안 되는가"를 1분 안에 흡수하기 위한 컨텍스트 자산.
> **청중**: 라운드 회고 작성 진입한 Claude + 라운드 인벤토리를 알고 싶은 세션.
> **most-local**: 본 폴더의 `*.md` 인덱스·작성 포맷·폐기 처리 룰은 모두 여기에 둔다.

---

## 1. 라운드 문서란

라운드 문서는 큰 결정 1건의 회고다. 다음 4가지를 명확히 남긴다.

1. **무엇을 도입했는가** — 새 워크플로우, 새 컬럼, 새 MCP 툴.
2. **무엇을 폐기했는가** — 매트릭스/룩업/서브에이전트/스코어 컬럼 등. 어디로 옮겼는지(_archive 경로) 명시.
3. **왜 결정했는가** — 갈림길 표(GN/RN) 형식 권장. 다른 선택지를 왜 버렸는지.
4. **재제안 금지 목록** — Claude가 같은 패턴을 다시 꺼내지 않도록 못박는다.

---

## 2. 파일명 규약

- `YYYY-MM-<주제-kebab>.md` (예: `2026-05-stock-daily-overhaul.md`).
- 한 라운드 = 한 파일. 후속 hotfix는 본문 뒤에 추가하거나 새 파일을 만들지 분기.
- 파일명은 `git mv` 외에는 고정. 인덱스(§4)도 같이 갱신.

---

## 3. 권장 섹션 (라운드 doc 본문)

```
1. TL;DR (작업 전 → 작업 후)  ← 변화 표 권장
2. 작업 원인 (한계 N가지 / 함정 N가지)
3. 갈림길 결정 (G1~Gn 또는 R1~Rn) — 선택 + 이유
4. 새 워크플로우 / 새 컬럼 / 새 MCP 툴
5. 폐기 항목 (이동 위치 명시, _archive 경로 포함)
6. 재제안 금지 목록  ← 가장 중요. 누락 금지.
7. 영향받은 파일 (서버/DB/스킬/웹)
```

---

## 4. 라운드 인덱스 (현 인벤토리)

> §10.8 "인덱스 부재" 룰화. 신규 라운드 추가 시 반드시 1줄 갱신.

- **`2026-05-stock-daily-overhaul.md`** — `/stock-daily` per-stock-analysis 단일 진입점(7단계) + analyze_position raw 9 카테고리 + base 3층 본문 inject 의무 + 정량 결론 컬럼(verdict/size_pct/stop_method/...) + learned_patterns + weekly_strategy 5번째 모드 + 산업 표준 메트릭(industries.avg_per/avg_pbr/avg_roe/...) + 자동 마이그레이션 인프라. **폐기**: v6 12셀 매트릭스 / decision-tree 5×6 / position-action-rules 6대 룰 / base-*-updater 서브에이전트 → 모두 `references/_archive/` 보존.
- **`2026-05-weekly-review-overhaul.md`** — 4-Phase weekly-review (Phase 0 base 갱신 → Phase 1 종목별 8-step → Phase 2 종합 6-section → Phase 3 base 역반영 분기 → Phase 4 룰 win-rate) + `prepare_weekly_review_per_stock` / `prepare_weekly_review_portfolio` 묶음 MCP + `weekly_review_per_stock` 테이블 + base 영향 4분류(decisive/supportive/contradictory/neutral) + append-back 채널 + rule_catalog DB SSoT 16 active + register_rule MCP 노출 + W18 GOOGL contradictory 분기 사례.

---

## 5. 폐기 명시 의무

라운드가 무엇을 폐기했는지 본문에 반드시 명시한다. 누락되면 다음 세션이 동일 패턴을 다시 제안한다.

- **이동 위치**를 본문에 적는다. 예: `references/_archive/scoring-weights.md`, `references/_archive/decision-tree-action.md`.
- **헤더에 [DEPRECATED YYYY-MM-DD: <라운드>] <사유>** 1줄을 박는다.
- 본문은 보존 (재제안 방지 컨텍스트). 삭제 금지.
- 이 절차의 디테일은 `.claude/skills/stock/references/CLAUDE.md` (d4)에 있다 — 거기 룰이 most-local.

---

## 6. 재제안 금지 목록 (현 라운드 누적)

본 인덱스를 1차 진입한 Claude가 가장 자주 부딪히는 5건. 본문은 각 라운드 doc 참고.

- 합성 점수·셀·is_stale 재도입 (analyze_position raw 9 카테고리 유지).
- 매트릭스 룩업 (12셀 / decision-tree / position-action-rules) 재제안.
- 룰 단일 markdown SSoT — 매매 룰은 DB `rule_catalog` SSoT.
- base-*-updater 서브에이전트 재신설 — 메인 Claude inline.
- 회고 매도 분류·foregone PnL 수기 — `prepare_weekly_review_per_stock` 자동 산출.

---

## 7. 신규 라운드 추가 체크리스트

- [ ] 파일명 `YYYY-MM-<주제>.md` 규약.
- [ ] §3 7섹션 모두 채움 (특히 "폐기 항목" + "재제안 금지").
- [ ] §4 본 CLAUDE.md 인덱스에 1줄 추가 (핵심 결정 + 폐기 1줄).
- [ ] 폐기 reference는 `_archive/` 이동 + 헤더 DEPRECATED 박기 (절차 = 스킬 references CLAUDE.md d4).
- [ ] 영향받은 CLAUDE.md (특히 server/mcp, server/repos, .claude/skills/stock/references) 룰 갱신 검토.
- [ ] 한국어 본문 + 영어 식별자 (§5.6 컨벤션).

---

## 8. 길이 가이드

- 라운드 doc 본문은 200~600줄. 너무 짧으면 갈림길 누락, 너무 길면 후속 세션이 안 읽음.
- TL;DR 표는 5~10행 권장 — 한눈에 변화 파악.
- 본 CLAUDE.md(인덱스)는 80~120줄 유지. 라운드 본문 디테일은 본 파일에 복제 금지 — 항상 라운드 doc로 포인터.

---

## 9. 본 폴더의 비-라운드 자산

- `../measurement/2026-05-03-analyze-position-tokens.md` — 토큰 측정 1건. 라운드 결정 근거 자료. 본 인덱스에는 포함하지 않는다 (라운드 회고 아님).
