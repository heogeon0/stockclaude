/**
 * v17 base 3계층 만기·갱신 규칙.
 * stock/SKILL.md "Base 갱신 (자동 호출)" 인용.
 */

export interface BaseExpiryRule {
  layer: "economy" | "industry" | "stock";
  skill: string;
  label: string;
  expiry: string;
  expiryDays: number;
  triggers: string[];
  refreshedBy: string[];
}

export const BASE_EXPIRY_RULES: BaseExpiryRule[] = [
  {
    layer: "economy",
    skill: "base-economy",
    label: "거시경제 (1일)",
    expiry: "1일",
    expiryDays: 1,
    triggers: [
      "FOMC / 한은 금통위",
      "CPI 발표",
      "환율 임계 돌파",
      "지정학 이벤트",
    ],
    refreshedBy: ["stock-daily", "stock-research", "stock-discover"],
  },
  {
    layer: "industry",
    skill: "base-industry",
    label: "산업 (7일)",
    expiry: "7일",
    expiryDays: 7,
    triggers: ["점유율 변동", "규제 변화", "M&A", "기술 트렌드 변화"],
    refreshedBy: ["stock-research", "base-stock"],
  },
  {
    layer: "stock",
    skill: "base-stock",
    label: "종목 (30일)",
    expiry: "30일",
    expiryDays: 30,
    triggers: [
      "분기 실적 ±10%",
      "컨센 ±15%",
      "신규 리포트 ≥3건",
      "대주주 변동",
      "M&A",
    ],
    refreshedBy: ["stock-research", "stock-discover"],
  },
];

export const CASCADE_PRINCIPLE =
  "상위 base 만기 시 하위 skill 호출이 자동 연쇄 갱신을 트리거. 사용자 호출 없이 stale base → 신선 base 로 보정.";
