# Base Industry

stock skill 의 **base-industry 갱신** 호출 (사용자 명시 호출). 메인 LLM 이 inline 으로 직접 처리 (옛 sub-agent 폐기, 2026-04-30 — multi-device 호환).

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 base 갱신 정책 적용
2. 메인이 `~/.claude/skills/stock/references/base-industry-update-inline.md` 절차를 `$ARGUMENTS` 인자로 직접 수행
3. 종료 후 메인이 `get_industry(code)` 로 DB read-back 검증

## 인자

- `$ARGUMENTS`: 산업 코드 (필수)
  - KR 한글 슬러그: `반도체`, `게임`, `전력설비`, `금융지주`, `2차전지`, `AI-PCB`
  - US: `us-tech`, `us-communication`, `us-financials`, ...

## 절차

1. 메인이 inline 절차 진입 (`references/base-industry-update-inline.md`):
   - 정형 메트릭은 `compute_industry_metrics(industry_code)` 1 MCP 자동 산출 (avg_per/pbr/roe/op_margin/vol_baseline_30d)
   - 5차원 정성 본문 (사이클/점유율/규제/경쟁/기술) — 정형 미커버 차원만 LLM 자율 WebSearch (도메인 한정 권장)
   - 11 섹션 본문 작성 (v4 — 사이클 단계 + RS 모멘텀 + 리더/팔로워 포함)
   - Daily Appended Facts 통합
   - 메타 5키 + score 0~100 + `save_industry(...)` 호출
2. `get_industry(code)` 로 DB updated_at + score 검증
3. 사용자 보고 + 핵심 변경 (점유율 / 규제 / M&A 변화 등)

## 위치

- inline 절차: `~/.claude/skills/stock/references/base-industry-update-inline.md`
- 템플릿: `~/.claude/skills/stock/assets/industry-base-template.md`
- 산업 분류: `~/.claude/skills/stock/references/industry-sectors.md`
