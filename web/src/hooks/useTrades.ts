import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { TradeOut } from "@/types/api";

export interface UseTradesParams {
  code?: string;
  since?: string;
  limit?: number;
}

export const useTrades = (params: UseTradesParams = {}) => {
  const limit = params.limit ?? 100;
  return useQuery({
    queryKey: ["trades", { code: params.code, since: params.since, limit }],
    queryFn: () =>
      apiGet<TradeOut[]>("/trades", {
        code: params.code || undefined,
        since: params.since || undefined,
        limit,
      }),
  });
};
