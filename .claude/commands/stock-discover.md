# Stock Discover

stock skill 의 **discover 모드** 호출. 신규 종목 발굴 (광역 모멘텀 → 좁은 분석 → Top 3~5).

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 룰 적용
2. `~/.claude/skills/stock/references/discover-workflow.md` 의 3단계 워크플로우 진입
3. 인자 처리:
   - `$ARGUMENTS` 가 비면 → 시장 자동 (사용자 컨텍스트 기반)
   - `--kr` / `--us` → 시장 명시
   - 테마 키워드 (예: "AI 전력", "2차전지") → `discover_by_theme` 우선

## 절차

1. 광역 모멘텀: `rank_momentum_wide(market, top_n=30)` (메인 발굴)
2. 좁은 분석: 후보별 6차원 (research-workflow.md)
3. Top 3~5 + 변동성×재무 매트릭스 셀 적용
4. 사용자 "관심 등록" 시 MCP multi-step orchestration (LLM 직접) 의 `register_as_pending()` 호출

## 위치

- 본 skill 본체: `~/.claude/skills/stock/`
- 워크플로우: `~/.claude/skills/stock/references/discover-workflow.md`
- 출력 템플릿: `~/.claude/skills/stock/assets/discover-output-template.md`
