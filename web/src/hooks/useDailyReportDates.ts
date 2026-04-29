import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { DailyReportDatesOut } from "@/types/api";

export const useDailyReportDates = () =>
  useQuery({
    queryKey: ["daily-reports", "dates"],
    queryFn: () => apiGet<DailyReportDatesOut>("/daily-reports/dates"),
  });
