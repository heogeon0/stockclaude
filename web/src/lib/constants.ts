import type {
  ActionStatus,
  Grade,
  RiskLevel,
  Severity,
  Side,
  Status,
  Verdict,
} from "@/types/api";

type TremorColor =
  | "blue"
  | "emerald"
  | "amber"
  | "red"
  | "gray"
  | "violet"
  | "slate";

export const GRADE_COLOR: Record<Grade, TremorColor> = {
  Premium: "violet",
  Standard: "blue",
  Cautious: "amber",
  Defensive: "gray",
};

export const VERDICT_COLOR: Record<Verdict, TremorColor> = {
  강한매수: "emerald",
  매수우세: "blue",
  중립: "gray",
  관망: "slate",
  매도우세: "amber",
  강한매도: "red",
};

export const STATUS_COLOR: Record<Status, TremorColor> = {
  Active: "emerald",
  Pending: "amber",
  Close: "gray",
};

export const SEVERITY_COLOR: Record<Severity, TremorColor> = {
  warning: "amber",
  critical: "red",
};

export const SIDE_LABEL: Record<Side, string> = {
  buy: "매수",
  sell: "매도",
};

export const SIDE_COLOR: Record<Side, TremorColor> = {
  buy: "blue",
  sell: "red",
};

export const STATUS_LABEL: Record<Status, string> = {
  Active: "보유중",
  Pending: "대기",
  Close: "청산",
};

export const MARKET_LABEL: Record<"kr" | "us", string> = {
  kr: "KR",
  us: "US",
};

export const RISK_LEVEL_COLOR: Record<RiskLevel, TremorColor> = {
  warning: "amber",
  critical: "red",
};

export const RISK_TYPE_LABEL: Record<string, string> = {
  concentration: "비중 집중",
  correlation: "상관 과다",
  overheated: "과열",
  pyramid_reversal: "피라미딩 반전",
};

export const ACTION_STATUS_COLOR: Record<ActionStatus, TremorColor> = {
  pending: "slate",
  conditional: "amber",
  executed: "emerald",
  expired: "gray",
};

export const ACTION_STATUS_LABEL: Record<ActionStatus, string> = {
  pending: "대기",
  conditional: "조건부",
  executed: "체결",
  expired: "만료",
};

export const SCORE_COLOR_THRESHOLDS = [
  { min: 0, max: 50, color: "red" as TremorColor },
  { min: 50, max: 80, color: "amber" as TremorColor },
  { min: 80, max: 101, color: "emerald" as TremorColor },
];

export const scoreColor = (score: number | null | undefined): TremorColor => {
  if (score == null) return "gray";
  const hit = SCORE_COLOR_THRESHOLDS.find((t) => score >= t.min && score < t.max);
  return hit?.color ?? "gray";
};
