import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { ScoreWeightOverridesOut } from "@/types/api";

export const useScoreWeightsOverrides = (activeOnly: boolean = true) =>
  useQuery({
    queryKey: ["score-weights", "overrides", { activeOnly }],
    queryFn: () =>
      apiGet<ScoreWeightOverridesOut>("/score-weights/overrides", {
        active_only: activeOnly ? "true" : "false",
      }),
  });
