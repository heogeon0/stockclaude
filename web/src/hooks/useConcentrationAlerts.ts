import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { ConcentrationAlertsOut } from "@/types/api";

export const useConcentrationAlerts = (thresholdPct = 25.0) =>
  useQuery({
    queryKey: ["concentration-alerts", thresholdPct],
    queryFn: () =>
      apiGet<ConcentrationAlertsOut>("/portfolio/concentration-alerts", {
        threshold_pct: thresholdPct,
      }),
  });
