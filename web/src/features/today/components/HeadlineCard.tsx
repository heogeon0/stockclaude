import { Card } from "@tremor/react";
import { DailyReportContent } from "./DailyReportContent";

interface HeadlineCardProps {
  headline: string | null;
  summaryContent: string | null;
  date: string;
}

export const HeadlineCard = ({
  headline,
  summaryContent,
  date,
}: HeadlineCardProps) => {
  return (
    <Card>
      <p className="text-xs text-gray-500">{date}</p>
      <p className="mt-1 text-xl font-semibold leading-snug text-gray-900">
        {headline ?? "헤드라인이 설정되지 않았습니다."}
      </p>
      {summaryContent && (
        <details className="mt-4 rounded-md border border-gray-100 bg-gray-50 p-3">
          <summary className="cursor-pointer text-sm font-medium text-gray-700">
            전체 서술 보기
          </summary>
          <div className="mt-3">
            <DailyReportContent content={summaryContent} />
          </div>
        </details>
      )}
    </Card>
  );
};
