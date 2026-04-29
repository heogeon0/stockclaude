import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { EconomyDailyOut, Market } from "@/types/api";

export const useEconomyDaily = (market: Market, date?: string | null) =>
  useQuery({
    queryKey: ["economy-daily", market, { date: date ?? "latest" }],
    queryFn: () => {
      const params: Record<string, string> = { market };
      if (date) params.date = date;
      return apiGet<EconomyDailyOut | null>("/economy/daily", params);
    },
  });
