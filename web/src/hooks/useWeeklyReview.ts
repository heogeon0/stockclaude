import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { WeeklyReviewOut } from "@/types/api";

export const useWeeklyReview = (weekStart: string | null | undefined) =>
  useQuery({
    queryKey: ["weekly-review", weekStart],
    queryFn: () => apiGet<WeeklyReviewOut>(`/weekly-reviews/${weekStart}`),
    enabled: !!weekStart,
  });
