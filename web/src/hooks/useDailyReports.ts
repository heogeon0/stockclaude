import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { DailyReportsOut, Market } from "@/types/api";

export const useDailyReports = (
  date?: string | null,
  market?: Market | null,
) =>
  useQuery({
    queryKey: ["daily-reports", { date: date ?? "latest", market: market ?? "all" }],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (date) params.date = date;
      if (market) params.market = market;
      return apiGet<DailyReportsOut>(
        "/daily-reports",
        Object.keys(params).length > 0 ? params : undefined,
      );
    },
  });
