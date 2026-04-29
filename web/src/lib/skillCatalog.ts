/**
 * v17 skill 정적 카탈로그 — `~/.claude/skills/{stock,...}/SKILL.md` 인용.
 * 1 hub + 6 active + 1 deprecated.
 */

export type SkillRole = "hub" | "entry" | "module" | "base" | "deprecated";

export interface SkillCatalogEntry {
  name: string;
  role: SkillRole;
  summary: string;
  expiry?: string;
  triggers?: string[];
  callees?: string[];
  callers?: string[];
  deprecatedAt?: string;
  replacedBy?: string;
}

export const SKILL_CATALOG: SkillCatalogEntry[] = [
  {
    name: "stock",
    role: "hub",
    summary:
      "공통 규칙·MCP 인벤토리·12셀 매트릭스 정의처. 8 skill cross-reference 의 허브.",
  },
  {
    name: "stock-daily",
    role: "entry",
    summary: "보유·Pending 종목 일일 점검 + 액션 플랜 + 포트 종합 요약.",
    callees: ["stock-research", "base-economy", "base-industry", "base-stock"],
  },
  {
    name: "stock-discover",
    role: "entry",
    summary:
      "신규 종목 발굴 — 모멘텀·유동성 광역 스크리닝 → 6차원 분석 → Top 3~5.",
    callees: ["stock-research", "base-economy", "base-industry", "base-stock"],
  },
  {
    name: "stock-research",
    role: "module",
    summary:
      "공통 6차원 심도 분석 모듈 (재무/기술/수급/모멘텀/이벤트/컨센). daily·discover 가 호출.",
    callers: ["stock-daily", "stock-discover"],
    callees: ["base-economy", "base-industry", "base-stock"],
  },
  {
    name: "base-economy",
    role: "base",
    summary:
      "거시경제 base — 금리·환율·경기·지정학·섹터 포지셔닝·외국인 수급 6차원.",
    expiry: "1일",
    triggers: ["FOMC", "한은 금통위", "CPI", "환율 임계", "지정학 이벤트"],
  },
  {
    name: "base-industry",
    role: "base",
    summary:
      "산업 base — 사이클·점유율·규제·경쟁·기술 트렌드 5차원. KR 11섹터 + US GICS 11섹터.",
    expiry: "7일",
    triggers: ["점유율 변동", "규제", "M&A", "기술 변화"],
  },
  {
    name: "base-stock",
    role: "base",
    summary:
      "종목 base — Narrative + Reverse/Forward DCF + Comps + 애널 컨센 + 10 Key Points.",
    expiry: "30일",
    triggers: [
      "분기 실적 ±10%",
      "컨센 ±15%",
      "신규 리포트 ≥3건",
      "대주주 변동",
      "M&A",
    ],
  },
  {
    name: "stock-momentum",
    role: "deprecated",
    summary:
      "모멘텀 투자 — stock-research 의 6차원 분석 (모멘텀 차원) + base-economy 의 시장 국면으로 흡수됨.",
    deprecatedAt: "v17 (2026-04-27)",
    replacedBy: "stock-research + base-economy",
  },
];

export const SKILL_ROLE_LABEL: Record<SkillRole, string> = {
  hub: "허브",
  entry: "Entry Point",
  module: "공통 모듈",
  base: "Base 갱신",
  deprecated: "DEPRECATED",
};

export const SKILL_ROLE_COLOR: Record<SkillRole, string> = {
  hub: "slate",
  entry: "blue",
  module: "violet",
  base: "emerald",
  deprecated: "gray",
};
