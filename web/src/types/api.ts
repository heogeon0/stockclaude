/**
 * FastAPI (server/schemas/*) 응답 타입 수기 미러.
 * Pydantic `Decimal` 는 JSON 문자열로 나오므로 전부 `string` 으로 받고,
 * 표시·연산 시 `lib/decimal.ts` 의 `toNum` 사용.
 */

export type Market = "kr" | "us";
export type Currency = "KRW" | "USD";
export type Side = "buy" | "sell";
export type Grade = "Premium" | "Standard" | "Cautious" | "Defensive";
export type Status = "Active" | "Pending" | "Close";
export type Style = "day-trade" | "swing" | "long-term" | "momentum";
export type Verdict =
  | "강한매수"
  | "매수우세"
  | "중립"
  | "관망"
  | "매도우세"
  | "강한매도";
export type Severity = "warning" | "critical";
export type RiskLevel = "warning" | "critical";
export type ActionStatus = "pending" | "conditional" | "executed" | "expired";

export interface PositionOut {
  code: string;
  name: string | null;
  market: Market | null;
  currency: Currency | null;
  qty: string;
  avg_price: string;
  cost_basis: string | null;
  status: Status;
  style: Style | null;
  stop_loss_pct: string | null;
  trailing_method: string | null;
  tags: string[];
}

export interface PortfolioOut {
  positions: PositionOut[];
  cash: Record<string, string>;
  kr_total_krw: string;
  us_total_usd: string;
  realized_pnl: Record<string, string>;
}

export interface ConcentrationAlertOut {
  code: string;
  name: string | null;
  weight_pct: number;
  threshold_pct: number;
  severity: Severity;
  message: string;
}

export interface ConcentrationAlertsOut {
  alerts: ConcentrationAlertOut[];
  count: number;
  threshold_pct: number;
}

export interface TradeOut {
  id: number;
  code: string;
  name: string | null;
  market: Market | null;
  side: Side;
  qty: string;
  price: string;
  executed_at: string;
  trigger_note: string | null;
  fees: string;
  realized_pnl: string | null;
  created_at: string;
}

export interface DailyReportOut {
  code: string;
  name: string | null;
  market: Market | null;
  date: string;
  verdict: Verdict | null;
  signals: Array<Record<string, unknown>>;
  content: string | null;
}

export interface DailyReportsOut {
  date: string | null;
  reports: DailyReportOut[];
}

export interface DailyReportDatesOut {
  dates: string[];
}

/** portfolio_snapshots v11 narrative 응답 — 중첩은 JSONB 통과. */
export interface PerStockSummary {
  code: string;
  name?: string;
  close?: number;
  change_pct?: number;
  pnl_pct?: number;
  verdict?: Verdict | string;
  note?: string;
  [k: string]: unknown;
}

export interface RiskFlag {
  type: string;
  level: RiskLevel;
  code?: string;
  scope?: string;
  detail?: string;
  weight_pct?: number;
  [k: string]: unknown;
}

export interface ActionPlanItem {
  priority?: number;
  code: string;
  name?: string;
  action: Side;
  qty?: number;
  price_hint?: number;
  trigger?: string;
  condition?: string;
  reason?: string;
  status: ActionStatus;
  executed_trade_id?: number | null;
  expires_at?: string;
  [k: string]: unknown;
}

export interface PortfolioDailySummaryOut {
  date: string;
  headline: string | null;
  per_stock_summary: PerStockSummary[];
  risk_flags: RiskFlag[];
  action_plan: ActionPlanItem[];
  summary_content: string | null;
}

export interface IndustryOut {
  code: string;
  name: string;
  name_en: string | null;
  market: Market | null;
  parent_code: string | null;
  score: number | null;
  content: string | null;
  updated_at: string;
}

export interface IndustriesOut {
  industries: IndustryOut[];
  count: number;
}

export interface EconomyBaseOut {
  market: Market;
  context: Record<string, unknown>;
  content: string | null;
  updated_at: string;
}

export interface EconomyDailyOut {
  market: Market;
  date: string;
  index_values: Record<string, unknown>;
  foreign_net: number | null;
  institution_net: number | null;
  events: Array<Record<string, unknown>>;
  content: string | null;
}

export type Timeframe = "day-trade" | "swing" | "long-term" | "momentum";
export type Dim = "재무" | "산업" | "경제" | "기술" | "밸류에이션";
export type WeightSource = "default" | "user" | "claude" | "backtest";

export interface RegimeOut {
  market: Market;
  label: string;
  momentum_on: boolean;
  conditions_met: number;
  total_conditions: number;
  checks: Record<string, boolean>;
  details: Record<string, unknown>;
  interpretation: string | null;
  error: string | null;
  computed_at: string;
}

export interface ScoreWeightDefaultsRow {
  timeframe: Timeframe;
  dim: Dim;
  weight: string;
}

export interface ScoreWeightDefaultsOut {
  rows: ScoreWeightDefaultsRow[];
}

export interface ScoreWeightOverrideRow {
  code: string;
  name: string | null;
  timeframe: Timeframe;
  dim: Dim;
  weight: string;
  source: "user" | "claude" | "backtest" | null;
  reason: string | null;
  expires_at: string | null;
  updated_at: string;
}

export interface ScoreWeightOverridesOut {
  overrides: ScoreWeightOverrideRow[];
  count: number;
}

export interface AppliedWeightsRow {
  dim: Dim;
  weight: string;
  source: WeightSource;
}

export interface AppliedWeightsOut {
  code: string;
  timeframe: Timeframe;
  rows: AppliedWeightsRow[];
}

export interface BacktestCacheRow {
  code: string;
  name: string | null;
  market: Market | null;
  raw_md: string | null;
  computed_at: string;
  expires_at: string | null;
}

export interface BacktestListOut {
  rows: BacktestCacheRow[];
  count: number;
}

export type SkillName =
  | "stock"
  | "stock-research"
  | "stock-daily"
  | "stock-discover"
  | "base-economy"
  | "base-industry"
  | "base-stock"
  | "stock-momentum"; // DEPRECATED (v17, 2026-04-27) — stock-research 의 모멘텀 차원으로 흡수

export interface SkillListItem {
  name: SkillName;
  title: string | null;
  summary: string | null;
  updated_at: string | null;
  bytes: number;
}

export interface SkillListOut {
  skills: SkillListItem[];
}

export interface SkillContentOut {
  name: SkillName;
  title: string | null;
  content: string;
  updated_at: string | null;
}

export interface WeeklyReviewListItem {
  week_start: string;
  week_end: string;
  trade_count: number;
  realized_pnl_kr: string | null;
  realized_pnl_us: string | null;
  unrealized_pnl_kr: string | null;
  unrealized_pnl_us: string | null;
  headline: string | null;
  created_at: string;
}

export interface WeeklyReviewListOut {
  reviews: WeeklyReviewListItem[];
  count: number;
}

export interface WinRateStats {
  tries: number;
  wins: number;
  pct: number;
}

export interface RuleEvaluation {
  rule?: string;
  trade_id?: number;
  code?: string;
  name?: string;
  foregone_pnl?: number | string;
  smart_or_early?: "smart" | "early" | string;
  pre_decision?: string;
  post_outcome?: string;
  note?: string;
  [k: string]: unknown;
}

export interface Highlight {
  type: "insight" | "pattern" | "warning" | string;
  detail: string;
  [k: string]: unknown;
}

export interface WeeklyReviewOut {
  week_start: string;
  week_end: string;
  trade_count: number;
  realized_pnl_kr: string | null;
  realized_pnl_us: string | null;
  unrealized_pnl_kr: string | null;
  unrealized_pnl_us: string | null;
  win_rate: Record<string, WinRateStats>;
  rule_evaluations: RuleEvaluation[];
  highlights: Highlight[];
  next_week_actions: ActionPlanItem[];
  headline: string | null;
  content: string | null;
  created_at: string;
  updated_at: string;
}

export interface WeeklyContextLatest {
  week_start: string | null;
  week_end: string | null;
  headline: string | null;
  highlights: Highlight[];
  pending_actions: ActionPlanItem[];
}

export interface WeeklyRollingStats {
  weeks_count: number;
  rule_win_rates: Record<string, WinRateStats>;
  total_realized_pnl_kr: number;
  avg_weekly_pnl_kr: number;
  trade_count_total: number;
}

export interface WeeklyContextOut {
  latest_review: WeeklyContextLatest | null;
  rolling_stats: WeeklyRollingStats;
  carryover_actions: Array<ActionPlanItem & { from_week?: string }>;
}

export interface StockBaseOut {
  code: string;
  total_score: number | null;
  financial_score: number | null;
  industry_score: number | null;
  economy_score: number | null;
  grade: Grade | null;
  fair_value_min: string | null;
  fair_value_avg: string | null;
  fair_value_max: string | null;
  analyst_target_avg: string | null;
  analyst_target_max: string | null;
  analyst_consensus_count: number | null;
  per: string | null;
  pbr: string | null;
  psr: string | null;
  roe: string | null;
  op_margin: string | null;
  narrative: string | null;
  risks: string | null;
  scenarios: string | null;
  content: string | null;
  updated_at: string | null;
}
