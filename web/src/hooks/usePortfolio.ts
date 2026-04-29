import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { PortfolioOut } from "@/types/api";

type Status = "active" | "all";

export const usePortfolio = (status: Status = "active") =>
  useQuery({
    queryKey: ["portfolio", status],
    queryFn: () => apiGet<PortfolioOut>("/portfolio", { status }),
  });
