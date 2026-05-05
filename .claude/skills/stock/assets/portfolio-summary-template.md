# 📊 포트폴리오 종합 요약 — YYYY-MM-DD

> 템플릿. 포트폴리오 모드 마지막에 작성. `save_portfolio_summary` 의 `summary_content` 인자 본문.
> JSON 필드 (`per_stock_summary` / `risk_flags` / `action_plan`) 스키마: → `references/snapshot-schema.md` 참조.

## ✅ Dependency Audit (YYYY-MM-DD)

> 표준 출력: → `assets/dependency-audit-template.md` 참조 (이 본문 최상단에 삽입).

## ■ 총 자산 변화

- 총 평가액: ₩XX (전일 대비 ±X.X%)
- 실현 이익: ₩XX (당일)
- 미실현 손익: ₩XX
- 예수금: ₩XX

(하이브리드 포트면 KRW + USD 분리 표기 + 환산 통합액)

## ■ 종목별 한 줄 요약

| 종목 | 등급 | 손익% | Verdict | 변화 |
|---|---|---|---|---|
| 🏆 ... | ... | ... | ... | ... |

## ■ 시그널 변화 핵심 (`compute_signals` 풀 가동)

| 종목 | 매수 | 매도 | 핵심 시그널 |
|---|---|---|---|

## ■ 내일 우선순위 액션 (자금 배분 순)

1. [최우선]
2. [차우선]
3. ...

(상세 JSON은 `action_plan` 필드, 절차 → `references/snapshot-schema.md`)

## ■ 예수금 활용 플랜

- 시나리오별 최대 소진: ₩X
- 보존 권장: ₩X

## ■ ⚠️ 경고 시그널 (있을 때만)

- {종목}: [경고]
  (상세 JSON은 `risk_flags` 필드)

## ■ 한 줄 결론

**핵심 1줄**

---

## 종료 루틴 (필수 순서)

> ⚠️ `reconcile_actions(today)` 는 SKILL.md BLOCKING #6 (Phase 1) 에서 호출. 여기서는 보고서 작성 중 발생한 늦은 trade 흡수 위한 선택 호출만.

```
0. ✅ Dependency Audit 출력 (위 섹션)
1. (선택) reconcile_actions(today)     # 늦은 trade 흡수용 (1차는 Phase 1)
2. save_portfolio_summary(             # 본 템플릿 + JSON 필드
     date=today,
     per_stock_summary=[...],
     risk_flags=[...],
     action_plan=[...],
     headline="한 줄 결론",
     summary_content="<이 마크다운 본문>",
   )
```
