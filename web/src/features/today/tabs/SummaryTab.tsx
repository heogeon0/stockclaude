import { useMemo } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { usePortfolio } from "@/hooks/usePortfolio";
import { usePortfolioDailySummary } from "@/hooks/usePortfolioDailySummary";
import type { Market } from "@/types/api";
import { ActionPlanTable } from "../components/ActionPlanTable";
import type { MarketFilter } from "../components/MarketToggle";
import { HeadlineCard } from "../components/HeadlineCard";
import { PerStockSummaryTable } from "../components/PerStockSummaryTable";
import { RiskFlagsList } from "../components/RiskFlagsList";

interface SummaryTabProps {
  date: string | null;
  market: MarketFilter;
}

/**
 * portfolio_snapshots.per_stock_summary / risk_flags / action_plan 의 code 를
 * usePortfolio.positions code→market 맵으로 룩업해 클라이언트 필터.
 * market="all" 이면 통과.
 */
export const SummaryTab = ({ date, market }: SummaryTabProps) => {
  const query = usePortfolioDailySummary(date);
  const portfolio = usePortfolio("all");

  const codeToMarket = useMemo(() => {
    const map = new Map<string, Market>();
    for (const p of portfolio.data?.positions ?? []) {
      if (p.market) map.set(p.code, p.market);
    }
    return map;
  }, [portfolio.data]);

  const matchesMarket = (code?: string): boolean => {
    if (market === "all") return true;
    if (!code) return false;
    return codeToMarket.get(code) === market;
  };

  if (query.isLoading) return <LoadingSkeleton rows={4} />;
  if (query.error) return <ErrorNotice error={query.error} title="종합 리포트 조회 실패" />;

  const data = query.data;
  if (!data) {
    return (
      <EmptyState
        title="해당 날짜 종합 리포트가 없습니다"
        description={
          date
            ? `${date} 자 portfolio_snapshots 레코드가 존재하지 않습니다.`
            : "종합 리포트가 아직 생성되지 않았습니다."
        }
      />
    );
  }

  const filteredStocks =
    market === "all"
      ? data.per_stock_summary
      : data.per_stock_summary.filter((s) => matchesMarket(s.code));
  const filteredRisks =
    market === "all"
      ? data.risk_flags
      : data.risk_flags.filter((r) => !r.code || matchesMarket(r.code));
  const filteredActions =
    market === "all"
      ? data.action_plan
      : data.action_plan.filter((a) => matchesMarket(a.code));

  return (
    <div className="space-y-4">
      <HeadlineCard
        headline={data.headline}
        summaryContent={data.summary_content}
        date={data.date}
      />
      <ActionPlanTable actions={filteredActions} />
      <RiskFlagsList flags={filteredRisks} />
      <PerStockSummaryTable rows={filteredStocks} />
    </div>
  );
};
