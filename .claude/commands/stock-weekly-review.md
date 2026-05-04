# Stock Weekly Review

stock skill 의 **weekly-review 모드** wrapper. 주간 회고 4-Phase 절차 진입.

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 룰 적용
2. `~/.claude/skills/stock/references/weekly-review-workflow.md` 의 4-Phase 진입:
   - **Phase 0** (BLOCKING): base stale 갱신 (cascade economy → industry → stock, 이번주 거래 종목 우선)
   - **Phase 1**: 종목별 회고 (per-stock 8-step, 거래 발생 종목 N건)
   - **Phase 2**: 종합 회고 (portfolio 6-section, 1건)
   - **Phase 3**: base append-back (학습 → base 역반영)
3. 인자 처리:
   - 비면 → **이번 주** (오늘 기준 월요일~일요일)
   - `2026-04-27` 같은 월요일 ISO 면 → **해당 주**
   - `last` 면 → 직전 주

## 검증 필수

- Phase 0 누락 시 결과 최상단에 ⚠️ 명시
- Phase 1 종목별 회고 9건 모두 `save_weekly_review_per_stock` 저장 + read-back
- Phase 2 `save_weekly_review` 의 정량 6 인자 + Phase 결과 5 인자 모두 채움
- Phase 3 `append_base_facts` / `propose_base_narrative_revision` 호출 결과를 phase3_log 에 영속
- pending revisions 큐 ≥3 시 다음 daily BLOCKING 알림

## 위치

- 본 skill 본체: `~/.claude/skills/stock/`
- 워크플로우: `~/.claude/skills/stock/references/weekly-review-workflow.md`
- base 영향 4분류: `~/.claude/skills/stock/references/base-impact-on-review.md`
- Phase 3 절차: `~/.claude/skills/stock/references/base-appendback-protocol.md`
- 출력 템플릿:
  - `~/.claude/skills/stock/assets/weekly-review-per-stock-template.md` (Phase 1)
  - `~/.claude/skills/stock/assets/weekly-review-portfolio-template.md` (Phase 2)

## 신설 MCP (라운드 본 라운드)

- `prepare_weekly_review_per_stock(week_start, week_end, code)` — Phase 1 인풋 묶음
- `prepare_weekly_review_portfolio(week_start, week_end)` — Phase 2 인풋 묶음
- `save_weekly_review_per_stock`, `get_weekly_review_per_stock`, `list_weekly_review_per_stock`
- `append_base_facts`, `propose_base_narrative_revision`, `get_pending_base_revisions`
- `register_rule`, `list_rule_catalog`, `get_rule`, `update_rule`, `deprecate_rule`

## 학습 사이클

```
weekly_strategy (월요일 brainstorm)
   → daily 운영
   → trades 누적
   → weekly-review (본 명령) Phase 1~3
   → 다음 weekly_strategy (본 회고 lessons_learned 인용)
```

Phase 3 누락 시 학습이 base 에 도달 안 함 — 다음주 daily 가 옛 thesis 인용 → 같은 실수 반복.
