# Stock Research

stock skill 의 **research 모드** 호출. 6차원 정량 분석 (재무/기술/수급/모멘텀/이벤트/컨센).

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 룰 적용
2. `~/.claude/skills/stock/references/research-workflow.md` 의 0~6단계 진입
3. 인자 처리:
   - `$ARGUMENTS` 가 종목명/티커 1개 → 단일 분석
   - `--rebalance` → 보유 종목 전체 6차원 재평가
   - `종목A vs 종목B` → 비교 분석
   - `--dim financial,consensus` → 부분 분석

## 절차

1. 의존성 체크 — base 만료 시 sub-agent spawn (cascade economy → industry → stock)
2. Market 라우팅 (KR/US 자동) — LLM 직접 판단 (6자리 숫자 = KR / 1~5자 대문자 = US)
3. 9 MCP 툴 일괄 호출 (재무 + 컨센 + 리포트 + 추이 + 수급 + 변동성 + 이벤트 + 등급 + 시그널)
4. 6차원 verdict 산정
5. 유의미 발견 시 종목 base 의 `Daily Appended Facts` append

## 위치

- 본 skill 본체: `~/.claude/skills/stock/`
- 워크플로우: `~/.claude/skills/stock/references/research-workflow.md`
- 출력 템플릿: `~/.claude/skills/stock/assets/momentum-ranking-template.md`, `rebalance-template.md`
