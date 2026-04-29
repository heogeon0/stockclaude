import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { WeeklyReviewOut } from "@/types/api";

export const useLatestWeeklyReview = () =>
  useQuery({
    queryKey: ["weekly-review", "latest"],
    queryFn: () => apiGet<WeeklyReviewOut | null>("/weekly-reviews/latest"),
  });
