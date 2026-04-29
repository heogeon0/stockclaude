import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { EconomyBaseOut, Market } from "@/types/api";

export const useEconomyBase = (market: Market) =>
  useQuery({
    queryKey: ["economy-base", market],
    queryFn: () =>
      apiGet<EconomyBaseOut | null>("/economy/base", { market }),
  });
