# Base Economy

stock skill 의 **base-economy 갱신** 호출 (사용자 명시 호출). 메인 LLM 이 inline 으로 직접 처리 (옛 sub-agent 폐기, 2026-04-30 — multi-device 호환).

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 base 갱신 정책 적용
2. 메인이 `~/.claude/skills/stock/references/base-economy-update-inline.md` 절차를 직접 수행
3. 종료 후 메인이 `get_economy_base(market)` 로 DB read-back 검증

## 인자

- `$ARGUMENTS`:
  - `--kr` → market="kr"
  - `--us` → market="us"
  - `--all` 또는 비어있음 → 양쪽 다 inline 처리 (순차 — KR → US)

## 절차

1. (선택) `check_base_freshness(auto_refresh=False)` 로 stale 확인
2. 메인이 inline 절차 진입 (`references/base-economy-update-inline.md`):
   - 데이터 수집 (FRED/한은/WebSearch 4종)
   - 8 섹션 본문 작성
   - Daily Appended Facts 통합
   - 메타 7키 + `save_economy_base(market, content, context)` 호출
3. `get_economy_base(market)` 로 DB updated_at 검증
4. 검증 통과 시 사용자 보고 + 핵심 변경 3줄

## 위치

- inline 절차: `~/.claude/skills/stock/references/base-economy-update-inline.md`
- 템플릿: `~/.claude/skills/stock/assets/economy-base-template.md`
