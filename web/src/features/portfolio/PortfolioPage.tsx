import { usePortfolio } from "@/hooks/usePortfolio";
import { useConcentrationAlerts } from "@/hooks/useConcentrationAlerts";
import { useRecentTrades } from "@/hooks/useRecentTrades";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { AssetSummaryCards } from "./components/AssetSummaryCards";
import { ConcentrationBanner } from "./components/ConcentrationBanner";
import { PositionsTable } from "./components/PositionsTable";
import { RecentTradesCard } from "./components/RecentTradesCard";

export const PortfolioPage = () => {
  const portfolioQuery = usePortfolio("all");
  const alertsQuery = useConcentrationAlerts();
  const recentTradesQuery = useRecentTrades(5);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-2xl font-semibold text-gray-900">포트폴리오</h2>
        <p className="mt-1 text-sm text-gray-500">
          보유 종목 현황과 최근 매매를 한눈에 확인합니다.
        </p>
      </header>

      {portfolioQuery.isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : portfolioQuery.error ? (
        <ErrorNotice error={portfolioQuery.error} title="포트폴리오 조회 실패" />
      ) : portfolioQuery.data ? (
        <AssetSummaryCards portfolio={portfolioQuery.data} />
      ) : (
        <EmptyState />
      )}

      {alertsQuery.data && alertsQuery.data.alerts.length > 0 && (
        <ConcentrationBanner
          alerts={alertsQuery.data.alerts}
          thresholdPct={alertsQuery.data.threshold_pct}
        />
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          {portfolioQuery.isLoading ? (
            <LoadingSkeleton rows={6} />
          ) : portfolioQuery.data ? (
            <PositionsTable positions={portfolioQuery.data.positions} />
          ) : null}
        </div>
        <div>
          {recentTradesQuery.isLoading ? (
            <LoadingSkeleton rows={5} />
          ) : recentTradesQuery.error ? (
            <ErrorNotice
              error={recentTradesQuery.error}
              title="최근 매매 조회 실패"
            />
          ) : (
            <RecentTradesCard trades={recentTradesQuery.data ?? []} />
          )}
        </div>
      </div>
    </div>
  );
};
