# Base Stock

stock skill 의 **base-stock 갱신** 호출 (사용자 명시 호출). 메인 LLM 이 inline 으로 직접 처리 (옛 sub-agent 폐기, 2026-04-30 — multi-device 호환).

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 base 갱신 정책 적용
2. 의존성 cascade 체크 — economy / industry stale 시 먼저 inline 처리 (메인이 순차)
3. 메인이 `~/.claude/skills/stock/references/base-stock-update-inline.md` 절차를 `$ARGUMENTS` 인자로 직접 수행
4. 종료 후 메인이 `get_stock_context(code).base` 로 DB read-back 검증

## 인자

- `$ARGUMENTS`: 종목 코드 (필수)
  - KR: 6자리 숫자 (예: `005930`) 또는 한글명 (예: `삼성전자`)
  - US: 티커 (예: `NVDA`, `GOOGL`, `AAPL`)
  - `--mode new` / `--mode refresh` (생략 시 자동 — base 존재 여부로 판단)

## 절차

1. `get_stock_context(code)` — 현재 base 존재 + 만기 확인
2. 의존성 cascade — economy / industry / stock 순서로 stale 한 base 먼저 inline 처리 (각각 `references/base-{economy,industry}-update-inline.md`)
3. 메인이 inline 절차 진입 (`references/base-stock-update-inline.md`):
   - MCP 9 호출 + 딜 레이더 WebSearch 6종
   - Reverse/Forward DCF + Comps + 컨센 + 백테스트
   - 9 섹션 본문 작성 (≥ 4KB)
   - 17 인자 (점수 4 / 등급 1 / 컨센 4 / 재무 4 / 텍스트 4) + `save_stock_base(...)` 호출
4. DB read-back 검증 (Trust but verify) — `get_stock_context(code)`
5. 사용자 보고 — grade + 핵심 변경 3~5줄

## 위치

- inline 절차: `~/.claude/skills/stock/references/base-stock-update-inline.md` (가장 무거움 — 9 섹션 풀 작성)
- 템플릿: `~/.claude/skills/stock/assets/base-stock-template.md`
- 컨센 추적: `~/.claude/skills/stock/references/analyst-consensus-tracking.md`
- 10 Key Points: `~/.claude/skills/stock/references/narrative-10-key-points.md`
