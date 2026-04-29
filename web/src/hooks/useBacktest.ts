import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { BacktestCacheRow, BacktestListOut } from "@/types/api";

export const useBacktest = () =>
  useQuery({
    queryKey: ["backtest", "all"],
    queryFn: () => apiGet<BacktestListOut>("/backtest"),
  });

export const useBacktestOne = (code: string | null) =>
  useQuery({
    queryKey: ["backtest", "one", code],
    queryFn: () => apiGet<BacktestCacheRow>(`/backtest/${encodeURIComponent(code!)}`),
    enabled: !!code,
  });
