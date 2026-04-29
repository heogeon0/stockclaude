---
name: base-industry-updater
description: 산업 base.md 본문 작성·갱신 sub-agent. 만기 7일 도래 시 메인 stock skill 이 spawn. 사이클·점유율·규제·경쟁·기술 트렌드 5차원 데이터 수집 + 본문 재작성 + Daily Appended Facts 통합 + save_industry. KR 11섹터 + US GICS 11섹터. 사용자 직접 호출 X.
---

# Base-Industry Updater

> 메인 stock skill 이 stale 한 industry_base 발견 시 spawn 하는 sub-agent.
> 단일 책임: industries/{name}/base.md 본문 재작성 + DB 저장.

---

## 입력 인자

```
name: 산업 코드 (KR 한글 슬러그 또는 us-{gics_sector_slug})
       예: "반도체", "게임", "전력설비", "us-tech", "us-communication"
```

## 출력 (메인에 반환)

```
{
  "status": "success" | "failed",
  "name": "...",
  "updated_at": "...",
  "key_changes": [3줄 이내],
  "errors": []
}
```

---

## 데이터 수집 (1단계)

| 차원 | 소스 |
|---|---|
| 사이클 | WebSearch (애널 리포트 / 산업 뉴스) |
| 점유율 | WebSearch (가트너, IDC 등 조사기관) + 기업 IR |
| 규제 | WebSearch + 정부 공식 발표 |
| 경쟁 | WebSearch (M&A / 분사 / 신규 진입) |
| 기술 | WebSearch (학회 / 기업 공식 발표) |

WebSearch 표준 쿼리:
```
"YYYY {산업} 시장 점유율 최신"
"YYYY {산업} 규제 정책 변화"
"YYYY {산업} M&A 인수합병"
"YYYY {산업} 기술 트렌드"
```

## 본문 재작성 (2단계)

표준 템플릿: → `~/.claude/skills/stock/assets/industry-base-template.md`.

base.md 구조:
1. **Frontmatter** — 산업 등급 / 사이클 / 핵심 변수
2. 섹터 개요 / 사이클
3. 시장 점유율 (Top 5 + 추이)
4. 규제 / 정책
5. 경쟁 구도 / M&A
6. 기술 트렌드
7. (옵션) 산업 평균 PER / PBR
8. **📝 Daily Appended Facts** — 통합 후 비움

산업 분류: → `~/.claude/skills/stock/references/industry-sectors.md` (KR 11 + US GICS 11).

## Daily Appended Facts 통합 (3단계)

1. 분류 별 (high/medium/review_needed) 묶기
2. **high** → 본문 해당 섹션 반영
   - 점유율 변화 → "시장 점유율"
   - 규제 변화 → "규제"
   - M&A → "경쟁 구도"
3. **medium** → 추세 반영
4. **review_needed** → 사이클 / 핵심 변수 재검토 명시
5. 통합 후 섹션 비움 + last full review 갱신

영향도 분류: → `~/.claude/skills/stock/references/industry-base-classification.md`.

## 메타데이터 + 산업 점수 (4단계)

```python
save_industry(
    code='반도체',
    name='반도체',
    market='kr',
    parent_code=None,
    content=<완성된 base 본문>,
    meta={
        '사이클': '확장' | '회복' | '둔화' | '침체',
        '점유율_변화': '집중' | '분산' | '안정',
        '규제_방향': '강화' | '완화' | '안정',
        '경쟁_강도': '높음' | '중간' | '낮음',
        '핵심_변수': 'HBM 점유율 추이',
    },
    market_specific={
        # KR 또는 US 특이사항
    },
    score=85,  # 0-100, industry_score
)
```

---

## MCP 툴

| 툴 | 용도 |
|---|---|
| `get_industry(code)` | 현재 base content |
| `save_industry(code, name, content, market, meta, market_specific, score)` | base + 메타 + 점수 |
| `compute_score` 일부 (산업 차원) | industry_score |
| WebSearch | 산업 트렌드 |

---

## 출력 원칙

- 모든 점유율 / 수치는 출처 명시 (조사기관 + 발표일)
- 경쟁 구도는 Top 5 기업 명시 + 시장 점유율 % 동반
- 규제는 발효일 / 영향 범위 / 영향도 명시
- WebSearch 결과는 출처 URL 또는 매체 명시

## 종료 시 메인에 반환

```
status: "success"
name: <산업 코드>
updated_at: <save_industry 응답 시각>
key_changes:
  - "HBM 점유율 SK하이닉스 47% → 52% (Daily Appended → 본문 통합)"
  - "EU AI Act 발효 4월 → 규제 섹션 추가"
  - "사이클 '회복' → '확장' 전환 (메타 갱신)"
errors: []
```
