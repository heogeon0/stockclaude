import { Card } from "@tremor/react";
import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { DailyReportContent } from "@/features/today/components/DailyReportContent";
import { useWeeklyReview } from "@/hooks/useWeeklyReview";
import { useWeeklyReviews } from "@/hooks/useWeeklyReviews";
import { HighlightsList } from "./components/HighlightsList";
import { NextWeekActionsList } from "./components/NextWeekActionsList";
import { ReviewPnLCards } from "./components/ReviewPnLCards";
import { RuleEvaluationsTable } from "./components/RuleEvaluationsTable";
import { WeekListSidebar } from "./components/WeekListSidebar";
import { WinRateCard } from "./components/WinRateCard";

export const ReviewPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const list = useWeeklyReviews(20);
  const queryWeek = searchParams.get("week");

  const defaultWeek = useMemo(
    () => list.data?.reviews[0]?.week_start ?? null,
    [list.data],
  );
  const selectedWeek = queryWeek ?? defaultWeek;

  // URL 동기화: 데이터 로드 후 ?week 미지정 시 최신으로 채움
  useEffect(() => {
    if (!queryWeek && defaultWeek) {
      setSearchParams({ week: defaultWeek }, { replace: true });
    }
  }, [queryWeek, defaultWeek, setSearchParams]);

  const detail = useWeeklyReview(selectedWeek);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold text-gray-900">주간 회고</h2>
        <p className="mt-1 text-sm text-gray-500">
          주간 실현·미실현 PnL · 룰별 승률 · 룰 평가 · 하이라이트 · 다음 주 액션. `save_weekly_review` MCP 툴이 채움.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <aside>
          <Card className="p-3">
            <h3 className="mb-3 px-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
              주차 ({list.data?.count ?? 0}건)
            </h3>
            {list.isLoading && <LoadingSkeleton rows={4} />}
            {list.error && <ErrorNotice error={list.error} title="목록 조회 실패" />}
            {list.data && list.data.reviews.length === 0 && (
              <EmptyState title="회고 없음" description="save_weekly_review 로 시작하세요" />
            )}
            {list.data && list.data.reviews.length > 0 && (
              <WeekListSidebar
                items={list.data.reviews}
                selectedWeekStart={selectedWeek}
                onSelect={(w) => setSearchParams({ week: w }, { replace: true })}
              />
            )}
          </Card>
        </aside>

        <section className="space-y-4">
          {detail.isLoading && <LoadingSkeleton rows={6} />}
          {detail.error && <ErrorNotice error={detail.error} title="회고 조회 실패" />}
          {detail.data && (
            <>
              <Card>
                <p className="text-xs font-mono text-gray-500">
                  {detail.data.week_start} ~ {detail.data.week_end} · 거래 {detail.data.trade_count}건
                </p>
                <h3 className="mt-1 text-lg font-semibold text-gray-900">
                  {detail.data.headline ?? "(headline 없음)"}
                </h3>
              </Card>

              <ReviewPnLCards review={detail.data} />

              <div className="grid gap-4 md:grid-cols-2">
                <WinRateCard winRate={detail.data.win_rate} />
                <HighlightsList highlights={detail.data.highlights} />
              </div>

              <RuleEvaluationsTable rows={detail.data.rule_evaluations} />
              <NextWeekActionsList actions={detail.data.next_week_actions} />

              {detail.data.content && (
                <Card>
                  <h4 className="mb-3 text-sm font-semibold text-gray-700">서술</h4>
                  <DailyReportContent content={detail.data.content} />
                </Card>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
};
