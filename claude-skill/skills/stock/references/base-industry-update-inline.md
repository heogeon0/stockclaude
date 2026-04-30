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
- **WebSearch 횟수 제한**: 4회 이내 (점유율 / 규제 / M&A / 기술). 압축 시도 금지.
- 한 번의 호출 = 한 산업. 여러 산업 stale 이면 산업별로 절차를 따로따로 실행.

---

## 1단계 — 데이터 수집

| 차원 | 소스 |
|---|---|
| 사이클 | WebSearch (애널 리포트 / 산업 뉴스) |
| 점유율 | WebSearch (가트너, IDC 등 조사기관) + 기업 IR |
| 규제 | WebSearch + 정부 공식 발표 |
| 경쟁 | WebSearch (M&A / 분사 / 신규 진입) |
| 기술 | WebSearch (학회 / 기업 공식 발표) |

WebSearch 표준 쿼리 (필요 분만):
```
"YYYY {산업} 시장 점유율 최신"
"YYYY {산업} 규제 정책 변화"
"YYYY {산업} M&A 인수합병"
"YYYY {산업} 기술 트렌드"
```

---

## 2단계 — 본문 재작성 (8 섹션)

표준 템플릿: → `~/.claude/skills/stock/assets/industry-base-template.md` (있다면) 참조.

base 본문 구조:
1. **Frontmatter** — 산업 등급 / 사이클 / 핵심 변수
2. 섹터 개요 / 사이클
3. 시장 점유율 (Top 5 + 추이)
4. 규제 / 정책
5. 경쟁 구도 / M&A
6. 기술 트렌드
7. (옵션) 산업 평균 PER / PBR
8. **📝 Daily Appended Facts** — 통합 후 비움

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

## 4단계 — 메타 5키 + score + 저장

```python
save_industry(
    code='반도체',
    name='반도체',
    market='kr',                  # 'kr' | 'us'
    parent_code=None,
    content=<완성된 8 섹션 본문>,
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
)
```

`score` 가 메인 LLM 의 정성 판단치 — 후속 종목 점수 계산 (`compute_score`) 의 산업 차원으로 직접 사용된다. **0/None 금지** (디폴트 50 fallback 이지만 회피).

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

- [ ] 8 섹션 (Frontmatter 포함) 모두 작성
- [ ] 메타 5키 모두 채움 + `score` 0~100 (None/0 금지)
- [ ] `save_industry(...)` 호출 성공
- [ ] `get_industry(code)` read-back — `updated_at` 갱신 + `score` 일치 확인
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
