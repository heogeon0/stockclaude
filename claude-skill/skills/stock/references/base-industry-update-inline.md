# base-industry-update — inline 절차

> **stale industry_base 발견 시 메인 에이전트가 직접 수행하는 절차.**
> 옛 `agents/base-industry-updater.md` (sub-agent) 폐기 → multi-device 운영 호환을 위해 inline 화.
>
> **단일 책임**: `industries` 테이블의 산업 1개 본문 재작성 + 메타 5키 + score 0~100 + DB 저장 + read-back.
> **언제**: `check_base_freshness` 결과 `industries[*].is_stale=true` 또는 사용자 `/base-industry {산업코드}` 호출 시.
> **누가**: stock skill 메인 LLM. sub-agent spawn 금지.

---

## 입력 인자

```
name: 산업 코드 (KR 한글 슬러그 또는 us-{gics_sector_slug})
       예: "반도체", "게임", "전력설비", "us-tech", "us-communication"
```

## 0단계 — 진입 가드

- **다른 작업 중 inline 진입 시**: 직전 분석 결과 (다른 산업/종목/포트폴리오) 를 본문에 인용하지 않음. **깨끗한 상태로 8 섹션을 처음부터 작성**.
- **정형 MCP 우선** — 산업 평균 메트릭은 `compute_industry_metrics` 1회로 자동 산출. 5 차원 본문(점유율/규제/M&A/기술/사이클)은 정형 미커버라 WebSearch 권장.
- 한 번의 호출 = 한 산업. 여러 산업 stale 이면 산업별로 절차를 따로따로 실행.

---

## 1단계 — 데이터 수집

**산업 평균 메트릭(정량)은 정형 MCP 1회. 5 차원 본문(정성)은 WebSearch 권장 — 정형 자산 거의 없음.**

| 차원 | 정형 MCP (1차) | WebSearch 권장 (도메인 한정) |
|---|---|---|
| 산업 평균 메트릭 (avg_per/pbr/roe/op_margin/vol_baseline_30d) | **`compute_industry_metrics(industry_code)`** — leader 종목 평균 자동 산출 | — |
| 사이클 | — | 애널 리포트 / 산업 뉴스 (`site:hankyung.com OR site:bloomberg.com`) |
| 점유율 | — | 가트너 / IDC / 카운터포인트 (`Gartner OR IDC market share`) + 기업 IR |
| 규제 | — | `site:fsc.go.kr OR site:sec.gov OR site:europa.eu` |
| 경쟁 (M&A·분사) | `compute_industry_metrics` 의 leaders 변동 + leader 종목별 `get_kr_disclosures` / `get_us_disclosures` | M&A 루머 / 비공식 보도 |
| 기술 | — | 학회 / 기업 공식 발표 (`site:arxiv.org OR site:nature.com` 등) |

WebSearch 권장 쿼리 (도메인 한정 강력 권장):
```
"YYYY {산업} 시장 점유율" Gartner OR IDC
site:fsc.go.kr OR site:sec.gov "{산업}" 규제
site:bloomberg.com OR site:reuters.com "{산업}" M&A YYYY
```

> v6 산업 표준 메트릭(avg_per/pbr/roe/op_margin/vol_baseline_30d)은 `compute_industry_metrics` 1회 호출로 자동 산출 — 수동 산출(WebSearch + DART/EDGAR) 불필요.

---

## 2단계 — 본문 재작성 (8 섹션)

표준 템플릿: → `~/.claude/skills/stock/assets/industry-base-template.md` (있다면) 참조.

base 본문 구조:
1. **Frontmatter** — 산업 등급 / 사이클 / 핵심 변수 + cycle_phase + RS + leader_followers
2. 섹터 개요 / 사이클
3. 시장 점유율 (Top 5 + 추이)
4. 규제 / 정책
5. 경쟁 구도 / M&A
6. 기술 트렌드
7. (옵션) 산업 평균 PER / PBR
8. ⭐ **사이클 단계 (도입 / 성장 / 성숙 / 쇠퇴)** ← v4-c 신설
   - 4단계 중 1개 명시 + 근거 (매출 성장률 / capex / R&D 비중 / 진입사 수)
   - 단계별 평균 PER 밴드 + 권장 포지션 사이즈 가이드 (도입=고밸류 변동/소액, 성장=주력, 성숙=배당/방어, 쇠퇴=피함)
9. ⭐ **산업 모멘텀 (RS / 자금 흐름)** ← v4-d 신설
   - Relative Strength: 산업 ETF/지수 대비 KOSPI/SPY 상대 강도 (3M / 6M / 1Y) — 수치 명시
   - 자금 흐름: 기관/외국인 누적 순매수 추이 (KRX/Finnhub 인용 가능 시)
   - 임계: RS 상위 30% = Overweight / 하위 30% = Underweight / 중간 = Neutral
10. ⭐ **리더 / 팔로워 분류** ← v4-e 신설
    - 산업 내 시총 / 매출 / 마진 기준 Top 3 리더 + 신흥 도전자 (팔로워) 2~3개
    - 리더 vs 팔로워의 일반적 valuation 갭 + 그 갭이 정상 범위인지 판정
11. **📝 Daily Appended Facts** — 통합 후 비움

산업 분류: → `~/.claude/skills/stock/references/industry-sectors.md` (KR 11 + US GICS 11).

---

## 3단계 — Daily Appended Facts 통합

기존 `📝 Daily Appended Facts` 섹션 처리:

1. 분류 별 (high / medium / review_needed) 묶기
2. **high** → 본문 해당 섹션 반영
   - 점유율 변화 → "시장 점유율"
   - 규제 변화 → "규제"
   - M&A → "경쟁 구도"
3. **medium** → 추세 반영
4. **review_needed** → 사이클 / 핵심 변수 재검토 명시
5. 통합 후 섹션 비움 + last full review 갱신

영향도 분류: → `~/.claude/skills/stock/references/industry-base-classification.md`.

---

## 4단계 — 메타 5키 + score + cycle_phase + RS + leader_followers + 저장

```python
save_industry(
    code='반도체',
    name='반도체',
    market='kr',                  # 'kr' | 'us'
    parent_code=None,
    content=<완성된 11 섹션 본문>,
    meta={
        '사이클': '확장' | '회복' | '둔화' | '침체',
        '점유율_변화': '집중' | '분산' | '안정',
        '규제_방향': '강화' | '완화' | '안정',
        '경쟁_강도': '높음' | '중간' | '낮음',
        '핵심_변수': 'HBM 점유율 추이',
    },
    market_specific={
        # KR 또는 US 특이사항 (선택)
    },
    score=85,  # 0-100, industry_score (compute_score 의 산업 차원이 이 값을 사용)
    # v4 (2026-05) 신규 인자 — DB 컬럼
    cycle_phase='성장',                 # '도입' | '성장' | '성숙' | '쇠퇴'
    momentum_rs_3m=18.5,                # KOSPI/SPY 대비 3M RS (%, 양수=outperform)
    momentum_rs_6m=24.2,                # 6M RS (%)
    leader_followers={
        'leaders': ['005930', '000660'],
        'followers': ['009830'],
    },
    # v6 (2026-05) 신규 인자 — 산업 표준 메트릭 (종목 financial_grade 본문 판단 근거)
    avg_per=15.3,                       # 산업 평균 PER
    avg_pbr=1.85,                       # 산업 평균 PBR
    avg_roe=12.4,                       # 산업 평균 ROE (%)
    avg_op_margin=14.2,                 # 산업 평균 영업이익률 (%)
    vol_baseline_30d=28.5,              # 산업 평균 30일 RV (%)
)
```

⚠️ v6 산업 표준 메트릭 작성 의무:
- **`compute_industry_metrics(industry_code)` 1회 호출로 자동 산출** — leader_followers.leaders 종목들에 compute_financials + 30일 RV 적용한 평균. 결과의 avg_per/avg_pbr/avg_roe/avg_op_margin/vol_baseline_30d 그대로 인자에 전달.
- 이 값이 종목 분석 시 financial_grade 결정의 anchor — 정확성 중요
- 누락 시 종목 분석에서 절대값 anchor 로 회귀 위험

`score` 가 메인 LLM 의 정성 판단치 — 후속 종목 점수 계산 (`compute_score`) 의 산업 차원으로 직접 사용된다. **0/None 금지** (디폴트 50 fallback 이지만 회피).

⚠️ score / meta.사이클 / cycle_phase 정합성 점검:
- meta.사이클 (정성 4종) 과 cycle_phase (4단계 명시) 가 충돌하지 않게 일관성 유지
- score 는 LLM 본문 판단 결과, cycle_phase + RS 는 정량 데이터 — 둘이 서로 보완

---

## 5단계 — Read-back 검증

저장 직후:
```python
result = get_industry(code=...)
assert result['updated_at'] > <save 호출 직전 시각>
assert result['score'] == <저장값>
```

---

## 작성 원칙

- 모든 점유율 / 수치는 출처 명시 (조사기관 + 발표일)
- 경쟁 구도는 Top 5 기업 명시 + 시장 점유율 % 동반
- 규제는 발효일 / 영향 범위 / 영향도 명시
- WebSearch 결과는 출처 URL 또는 매체 명시

---

## ✅ 완료 체크리스트

- [ ] 11 섹션 (Frontmatter + 사이클 단계 + RS 모멘텀 + 리더/팔로워 포함) 모두 작성
- [ ] 메타 5키 모두 채움 + `score` 0~100 (None/0 금지)
- [ ] `cycle_phase` 1개 명시 (도입/성장/성숙/쇠퇴)
- [ ] `momentum_rs_3m` / `momentum_rs_6m` 수치 명시 (정성 표현 X)
- [ ] `leader_followers` Top 3 리더 + 팔로워 2~3개 명시
- [ ] `save_industry(...)` 호출 성공 (새 인자 4개 포함)
- [ ] `get_industry(code)` read-back — `updated_at` 갱신 + `score` / `cycle_phase` 일치 확인
- [ ] Daily Appended Facts 비움 + last full review 갱신

## 완료 시 메인이 정리할 것

```
✅ industries[code=반도체] 갱신 (updated_at=YYYY-MM-DDTHH:MM, score=85)
주요 변경:
  - HBM 점유율 SK하이닉스 47% → 52% (Daily Appended → 본문 통합)
  - EU AI Act 발효 4월 → 규제 섹션 추가
  - 사이클 '회복' → '확장' 전환 (메타 갱신)
```

실패 시:
```
❌ industries[code=반도체] 갱신 실패
원인: <구체 에러>
재시도 권장: <조치>
```

---

> **inline 진입 시 주의 (재강조)**: 메인이 다른 작업 (daily/research/discover) 중에 본 절차로 진입하더라도, 직전 작업의 결과를 industry 본문에 끌어오지 않는다. 깨끗한 상태로 8 섹션을 처음부터 작성한다. **섹션 압축·생략 금지** — `industries` 행은 7일 동안 daily/research/종목 base 작성 시 참조하는 정식 문서다 (LLM 의 '효율 추구' 본능을 의식적으로 차단할 것).
