import { useMemo, useState } from "react";
import { useTrades } from "@/hooks/useTrades";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { TradesFilter, type TradesFilterValue } from "./components/TradesFilter";
import { TradesTable } from "./components/TradesTable";

const INITIAL_FILTER: TradesFilterValue = {
  code: "",
  since: "",
  side: "all",
  market: "all",
};

export const TradesPage = () => {
  const [filter, setFilter] = useState<TradesFilterValue>(INITIAL_FILTER);

  const tradesQuery = useTrades({
    code: filter.code.trim(),
    since: filter.since ? new Date(filter.since).toISOString() : undefined,
    limit: 200,
  });

  const visibleTrades = useMemo(() => {
    const all = tradesQuery.data ?? [];
    return all.filter((t) => {
      if (filter.side !== "all" && t.side !== filter.side) return false;
      if (filter.market !== "all" && t.market !== filter.market) return false;
      return true;
    });
  }, [tradesQuery.data, filter.side, filter.market]);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold text-gray-900">매매 기록</h2>
        <p className="mt-1 text-sm text-gray-500">
          기록된 전체 매매 내역 · 종목/기간/구분 필터.
        </p>
      </header>

      <TradesFilter
        value={filter}
        onChange={setFilter}
        onReset={() => setFilter(INITIAL_FILTER)}
      />

      {tradesQuery.isLoading ? (
        <LoadingSkeleton rows={8} />
      ) : tradesQuery.error ? (
        <ErrorNotice error={tradesQuery.error} title="매매 기록 조회 실패" />
      ) : (
        <TradesTable trades={visibleTrades} />
      )}
    </div>
  );
};
