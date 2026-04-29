import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { PortfolioDailySummaryOut } from "@/types/api";

/**
 * portfolio_snapshots (v11 narrative) 단건.
 * date 생략 시 최신. 스냅샷 없으면 서버가 null 반환.
 */
export const usePortfolioDailySummary = (date?: string | null) =>
  useQuery({
    queryKey: ["portfolio-daily-summary", { date: date ?? "latest" }],
    queryFn: () =>
      apiGet<PortfolioDailySummaryOut | null>(
        "/portfolio/daily-summary",
        date ? { date } : undefined,
      ),
  });
