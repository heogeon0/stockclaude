import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { WeeklyReviewListOut } from "@/types/api";

export const useWeeklyReviews = (limit = 12) =>
  useQuery({
    queryKey: ["weekly-reviews", { limit }],
    queryFn: () =>
      apiGet<WeeklyReviewListOut>("/weekly-reviews", { limit: String(limit) }),
  });
