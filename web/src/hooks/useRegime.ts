import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { Market, RegimeOut } from "@/types/api";

const FIVE_MIN = 5 * 60 * 1000;
const THIRTY_MIN = 30 * 60 * 1000;

/** 시장 국면 — 백엔드 5~30초 비용. staleTime 5분 + gcTime 30분. */
export const useRegime = (market: Market) =>
  useQuery({
    queryKey: ["regime", market],
    queryFn: () => apiGet<RegimeOut>("/regime", { market }),
    staleTime: FIVE_MIN,
    gcTime: THIRTY_MIN,
  });
