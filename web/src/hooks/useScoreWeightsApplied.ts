import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { AppliedWeightsOut, Timeframe } from "@/types/api";

/**
 * 종목·타임프레임별 최종 적용 가중치.
 * code 또는 timeframe 미지정 시 비활성화.
 */
export const useScoreWeightsApplied = (
  code: string | null,
  timeframe: Timeframe | null,
) =>
  useQuery({
    queryKey: ["score-weights", "applied", code, timeframe],
    queryFn: () =>
      apiGet<AppliedWeightsOut>("/score-weights/applied", {
        code: code!,
        timeframe: timeframe!,
      }),
    enabled: !!code && !!timeframe,
  });
