import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { ScoreWeightDefaultsOut } from "@/types/api";

export const useScoreWeightsDefaults = () =>
  useQuery({
    queryKey: ["score-weights", "defaults"],
    queryFn: () => apiGet<ScoreWeightDefaultsOut>("/score-weights/defaults"),
    staleTime: 60 * 60 * 1000, // 1h — 거의 안 바뀜
  });
