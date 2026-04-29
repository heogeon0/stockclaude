import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { StockBaseOut } from "@/types/api";

/**
 * 종목 기본 분석(score/grade/FV/밸류에이션/narrative·risks·scenarios·content) 단건.
 * enabled=false 면 쿼리 안 돌림 — 아코디언 펼침 시만 lazy fetch 용도.
 */
export const useStockBase = (code: string, enabled: boolean = true) =>
  useQuery({
    queryKey: ["stock-base", code],
    queryFn: () => apiGet<StockBaseOut>(`/stocks/${encodeURIComponent(code)}/base`),
    enabled,
  });
