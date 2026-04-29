import {
  Accordion,
  AccordionBody,
  AccordionHeader,
  AccordionList,
} from "@tremor/react";
import { useMemo } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useDailyReports } from "@/hooks/useDailyReports";
import { usePortfolioDailySummary } from "@/hooks/usePortfolioDailySummary";
import { MARKET_LABEL } from "@/lib/constants";
import type { DailyReportOut, PerStockSummary, Verdict } from "@/types/api";
import type { MarketFilter } from "../components/MarketToggle";
import { StockBaseExpanded } from "../components/StockBaseExpanded";
import { VerdictBadge } from "../components/VerdictBadge";

interface StockDailyTabProps {
  date: string | null;
  market: MarketFilter;
}

const formatSignedPct = (v: number | null | undefined): string => {
  if (v == null) return "";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
};

const pctColorClass = (v: number | null | undefined): string => {
  if (v == null) return "text-gray-500";
  if (v > 0) return "text-emerald-600";
  if (v < 0) return "text-red-600";
  return "text-gray-500";
};

export const StockDailyTab = ({ date, market }: StockDailyTabProps) => {
  const serverMarket = market === "all" ? null : market;
  const reports = useDailyReports(date, serverMarket);
  const summary = usePortfolioDailySummary(date);

  const summaryByCode = useMemo(() => {
    const map = new Map<string, PerStockSummary>();
    for (const s of summary.data?.per_stock_summary ?? []) {
      map.set(s.code, s);
    }
    return map;
  }, [summary.data]);

  if (reports.isLoading) return <LoadingSkeleton rows={6} />;
  if (reports.error) return <ErrorNotice error={reports.error} title="리포트 조회 실패" />;

  const rows = reports.data?.reports ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState
        title="해당 날짜의 종목 리포트가 없습니다"
        description={
          date
            ? `${date} 자 보유 종목별 분석 리포트가 존재하지 않습니다.`
            : "리포트가 아직 생성되지 않았습니다."
        }
      />
    );
  }

  return (
    <AccordionList>
      {rows.map((r) => (
        <Accordion key={`${r.code}-${r.date}`}>
          <AccordionHeader>
            <StockRowHeader report={r} summary={summaryByCode.get(r.code)} />
          </AccordionHeader>
          <AccordionBody>
            <StockBaseExpanded
              code={r.code}
              market={r.market}
              dailyContent={r.content}
            />
          </AccordionBody>
        </Accordion>
      ))}
    </AccordionList>
  );
};

interface StockRowHeaderProps {
  report: DailyReportOut;
  summary: PerStockSummary | undefined;
}

const StockRowHeader = ({ report, summary }: StockRowHeaderProps) => {
  const verdict: Verdict | string | null =
    (summary?.verdict as Verdict | undefined) ?? report.verdict ?? null;
  return (
    <div className="flex flex-1 items-center justify-between gap-3 pr-3 text-left">
      <div className="flex items-baseline gap-2 min-w-0">
        <span className="font-semibold text-gray-900 truncate">
          {report.name ?? report.code}
        </span>
        <span className="text-xs text-gray-400">{report.code}</span>
        {report.market && (
          <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
            {MARKET_LABEL[report.market]}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 whitespace-nowrap text-sm">
        {summary?.close != null && (
          <span className="tabular-nums text-gray-700">
            {summary.close.toLocaleString("ko-KR")}
          </span>
        )}
        {summary?.change_pct != null && (
          <span className={`tabular-nums ${pctColorClass(summary.change_pct)}`}>
            {formatSignedPct(summary.change_pct)}
          </span>
        )}
        {summary?.pnl_pct != null && (
          <span className={`tabular-nums ${pctColorClass(summary.pnl_pct)}`}>
            손익 {formatSignedPct(summary.pnl_pct)}
          </span>
        )}
        <VerdictBadge verdict={verdict} />
      </div>
    </div>
  );
};
