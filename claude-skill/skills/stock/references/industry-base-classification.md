# 산업 Base 영향도 분류 룰

> 로드 시점: stock-daily 의 산업 fact append 시 + base 갱신 트리거 판정 시.

## 4단계 분류

| 분류 | 영향도 | 처리 |
|---|---|---|
| **high (fact)** | 즉시 base patch + 본문 반영 | 산업 base append + 갱신 트리거 |
| **medium (fact)** | 즉시 base patch | 산업 base append (7일 만기 갱신 시 통합) |
| **review_needed (flag)** | 사이클 / 핵심 변수 재검토 | base append + 누적 3개+ 시 base 재작성 권장 |
| **low (daily only)** | base 영향 없음 | daily 보고서에만 |

## 분류 표

| 감지 사항 | 예시 | 분류 |
|---|---|---|
| **산업 경쟁 구도 변화** | "HBM4 시장 SK하이닉스 주도권 확대" | **high** |
| **규제·정책 변화** | "게임 셧다운제 완화", "Section 232 발효" | **high** |
| **대형 M&A·분사·인수** | "Alphabet의 Wiz 인수 완료" | **high (트리거)** |
| **기술 패러다임 변화** | "AI 반도체 수요 재평가", "HBM4 양산 시작" | **medium** |
| **점유율 ±5%p 변화** | "삼성 HBM 점유율 17→28%" | **medium** |
| **섹터 전반 수급 전환** | "외국인 반도체 순매수 10일 연속" | **medium** |
| **산업 이벤트 (분쟁 / 적대적 M&A 시도)** | "경쟁사 적대적 M&A 시도" | **review_needed** |
| **신기술 발표 (대형 컨퍼런스)** | "엔비디아 GTC, OpenAI DevDay" | **review_needed** |
| **단일 기업 분기 실적** | "삼성 1Q26 실적" | **low** (개별 종목 base 영역) |

## Append 포맷

```markdown
## 📝 Daily Appended Facts (since last full review)

### 2026-04-22
- [high/competition] HBM4 시장 SK하이닉스 주도권 확대 — 점유율 54→55% — source: 머니투데이
- [medium/policy] 미국 Section 232 첨단 반도체 25% 관세 1/14 발효 — 기존 보도

### 2026-04-24
- [review_needed/competition] 경쟁사 대규모 증설 발표 — 공급 과잉 우려
- [high/m&a] HD현대일렉트릭 주요 수주 발표 — 전력설비 섹터 narrative 강화
```

## 갱신 트리거 (자동 호출)

다음 조건 중 하나 충족 시 base-industry 즉시 호출 (만기 7일 무관):

1. 산업 Top 5 내 대형 M&A / 분사 / 인수
2. 신규 규제 발효 또는 폐지
3. 기술 패러다임 변화 (HBM 세대 변화 등)
4. 시장 점유율 Top 1 변동 (예: 1위 변경)
5. **review_needed 플래그 3개+ 누적**

## 통합 룰 (재작성 모드)

기존 `Daily Appended Facts` 를:

1. 분류 별 묶기
2. **high** → 본문 해당 섹션
   - 점유율 변화 → "시장 점유율" 섹션
   - 규제 변화 → "규제·정책" 섹션
   - M&A → "경쟁 구도" 섹션
3. **medium** → 추세 / 누적 변화 반영
4. **review_needed** → "사이클" / "핵심 변수" 재검토 명시
5. 통합 후 섹션 비움 + last full review 날짜 갱신

## stock-daily 와 공유

- stock-daily 의 종목 daily 분석 중 산업 이슈 감지 시 본 룰로 분류
- → `~/.claude/skills/stock/references/base-impact-classification.md` 의 "산업 base 영향도 분류" 표와 cross-link
- DRY 원칙: 본 파일이 정의처
