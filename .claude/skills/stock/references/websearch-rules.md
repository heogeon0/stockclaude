# WebSearch 가이드 (v8, 2026-05 — BLOCKING 복원 + 도메인 화이트리스트)

> 로드 시점: per-stock-analysis 4단계 LLM 판단 / base inline 1단계 데이터 수집 / daily Phase 2 매크로 / 재실행 시.
> 라운드 2026-05-daily-workflow-tightening: **v7 자율 정책 폐기 → BLOCKING 복원 + 도메인 화이트리스트**.
> 도메인 목록 단일 출처 → `websearch-domains.md`. 본 파일은 정책 (몇 회 / 어디 / 인용 룰) 위주.

---

## v7 자율 정책 폐기 사유

v7 (라운드 2026-05 초기) 은 "정형 데이터 90% 커버 → WebSearch 자율" 노선이었으나 다음 이유로 부분 회귀:

1. **정형 90% 는 *수치*만** — DFF / CPI / 환율은 정형으로 충분하지만 **매체 톤·지정학·시장 반응**은 정형 자산이 거의 없음 (FOMC 의장 기자회견 톤, 중동 긴장 격화, 컨센 변경 사유 등).
2. **자율 = 효율 추구** — LLM 이 매번 "정형으로 충분" 판단으로 search 스킵 빈발 → 보고서 nuance 0건. 시간 절약 패턴이 BLOCKING 복원 사유.
3. **도메인 노이즈** — 자율로 호출해도 SEO/AI 생성 사이트·개인 블로그가 매번 상위 노출. 화이트리스트로 강제하지 않으면 신뢰성 무너짐.

→ **단계별 BLOCKING 복원 + Tier 1~4 화이트리스트 의무화**.

---

## ⛔ 단위별 BLOCKING 매트릭스

| 단계 | 최소 search 횟수 | 권장 Tier | 결과 인용 위치 |
|---|---|---|---|
| **daily Phase 2 — economy 발언 톤** | 1회 BLOCKING | Tier 1 + Tier 2 (Bloomberg/Reuters + Fed/BOK) | daily 보고서 `## 매크로 / FOMC·금통위 톤` |
| **daily Phase 2 — economy 지정학** | 1회 BLOCKING | Tier 1 (Bloomberg/Reuters/FT/WSJ) | daily 보고서 `## 지정학 / 리스크` |
| **daily Phase 3 — per-stock 뉴스** | 1회/종목 BLOCKING | Tier 1 + Tier 4 (KR 종목이면) | daily 종목 보고서 `## 뉴스 / 촉매` |
| **base-industry — 점유율** | 1회 BLOCKING | Tier 3 (Gartner/IDC/Counterpoint/SemiAnalysis) | industry base 본문 `## 점유율` |
| **base-industry — 기술 트렌드** | 1회 BLOCKING | Tier 3 (Gartner/IDC + 분야별 전문 매체) | industry base 본문 `## 기술 트렌드` |
| **base-stock #3 경쟁사** | 1회 BLOCKING | Tier 1 (글로벌 매체) | stock base 본문 `## 딜레이더 #3 경쟁사` |
| **base-stock #4 규제** | 1회 BLOCKING | Tier 2 공식 우선 (sec.gov / fsc.go.kr / fss.or.kr 등) | stock base 본문 `## 딜레이더 #4 규제` |

총 합산 (daily portfolio 기준):
- Phase 2 economy: 2회
- Phase 3 per-stock: 종목수 × 1회 (Active + Pending)
- base-industry stale 발생 시: 산업수 × 2회 (cascade)
- base-stock stale 발생 시: 종목수 × 2회 (#3 + #4 cascade)

---

## ⛔ 결과 quality 가드

### 화이트리스트 매치 강제

- 검색 결과 상위 10건 중 **Tier 1~4 화이트리스트 도메인 매치 ≥ 1**.
- 매치 0건 → 쿼리 재시도 (`site:` 한정 더 좁힘 또는 키워드 변경).
- 2회 재시도 후에도 매치 0이면 보고서에 ⚠️ "WebSearch 결과 화이트리스트 매치 0 — Tier 외 결과 인용 금지" 명시 후 다른 정형 자산 fallback.

### 도메인·날짜 인용 의무

- daily 보고서 본문 / base 본문 인용 시 형식: `(도메인, YYYY-MM-DD)`
- 예: `(Bloomberg, 2026-05-04) "FOMC 의장 의장 톤은 dovish 로 해석된다" — 시장 반응 ...`
- 도메인·날짜 둘 다 누락 시 사용자 검증 불가 → 인용 무효 처리.

### 금지 도메인 무시

- 검색 결과 상위에 SeekingAlpha 개인 기고·네이버 블로그·티스토리·Reddit·SEO 사이트 (predictabledesigns 등) 가 보이면 무시.
- 단일 출처 → `websearch-domains.md` "금지 도메인" 섹션.

---

## 캐시 룰 (5분 TTL)

- 같은 분(分) 내 동일 쿼리 재호출 금지 — 결과 캐시 재사용.
- 5분 경과 후 재호출 가능 (장중 가격 변화·신규 보도 반영).
- 30분+ 차이 재실행: WebSearch 동일 쿼리 재호출 가치 작음 (검색 결과 변화 적음). 정형 MCP 는 fresh 조회 권장.
- 실적 D-7 종목: 시즌 동안 매 분석마다 search BLOCKING (가이던스·컨센 빠른 변화).
- NXT/시간외 가격 vs KRX 종가 ±3%+: 사유 추적용 search 추가 권장 (BLOCKING 외).

---

## 도메인 한정 쿼리 패턴

쿼리 예시·도메인 목록은 본 파일에 두지 않음 (중복 방지). **단일 출처 → `references/websearch-domains.md`**.

쿼리 일반 형식:
```
site:<tier1_domain> OR site:<tier2_domain> {키워드} YYYY-MM[-DD]
```

각 단계가 사용해야 할 Tier 매트릭스도 `websearch-domains.md` "단계 × Tier 매트릭스" 섹션 참조.

---

## BLOCKING 누락 시 동작

- daily 자체는 **중단하지 않음** — 누락 항목을 보고서 최상단에 ⚠️ "WebSearch BLOCKING 위반 — 누락: [Phase 2 발언 톤 / Phase 3 종목 N개 등]" 명시 후 진행.
- 사용자 판단으로 (a) 무시하고 진행 (b) 재실행 결정.
- 자가 보고로 "사실상 다 했다" 우기지 말 것 — 실제 호출 로그 / 응답 도메인 매치 기준.
- 누락 패턴 누적은 `dependency-audit-template.md` "참고 메트릭" 섹션 기록.

---

## 결과 활용 (기존 보존)

### daily 보고서

- `## 뉴스 / 촉매` 섹션에 인용 — 종목 1건 (Phase 3) 결과
- `## 매크로 / FOMC·금통위 톤` (Phase 2 발언 톤) + `## 지정학 / 리스크` (Phase 2 지정학) — 보고서 상단
- 화이트리스트 매치 0 시 ⚠️ 표기 + Tier 외 인용 금지

### base 본문 (`📌 영향도 판단` 섹션)

- 유의미한 팩트는 base 본문의 `📌 Base 영향도 판단` 또는 `📌 Daily Appended Facts` 로 승격
- base-industry / base-stock 의 BLOCKING search 결과는 5 차원 본문 내 직접 인용 (`base-industry-update-inline.md`, `base-stock-update-inline.md` 절차서)

---

## compute_signals 서버 에러 시 우회

- 지표(`compute_indicators`) + 이벤트(`detect_events`) + 등급(`compute_score`)을 조합해 **수동 verdict 산정**
- daily 보고서에 "⚠️ compute_signals 실패 — 지표 기반 수동 판정" 명시
- WebSearch BLOCKING 은 신호 에러와 무관하게 그대로 적용
