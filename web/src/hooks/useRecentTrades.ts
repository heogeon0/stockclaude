import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { TradeOut } from "@/types/api";

export const useRecentTrades = (limit = 5) =>
  useQuery({
    queryKey: ["trades", { limit }],
    queryFn: () => apiGet<TradeOut[]>("/trades", { limit }),
  });
