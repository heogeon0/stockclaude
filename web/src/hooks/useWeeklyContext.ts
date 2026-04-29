import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { WeeklyContextOut } from "@/types/api";

export const useWeeklyContext = (weeks = 4) =>
  useQuery({
    queryKey: ["weekly-context", weeks],
    queryFn: () =>
      apiGet<WeeklyContextOut>("/weekly-reviews/context", { weeks: String(weeks) }),
  });
