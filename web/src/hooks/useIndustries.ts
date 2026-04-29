import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { IndustriesOut } from "@/types/api";

/**
 * industries 목록.
 * - holdingsOnly=true 면 현재 Active 포지션 업종만
 * - market 지정 시 kr|us 필터
 */
export const useIndustries = (holdingsOnly?: boolean, market?: string) =>
  useQuery({
    queryKey: ["industries", { holdingsOnly: !!holdingsOnly, market: market ?? null }],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (holdingsOnly) params.holdings_only = "true";
      if (market) params.market = market;
      return apiGet<IndustriesOut>("/industries", Object.keys(params).length ? params : undefined);
    },
  });
