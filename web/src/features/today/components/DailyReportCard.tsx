import { Card } from "@tremor/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MARKET_LABEL } from "@/lib/constants";
import type { DailyReportOut } from "@/types/api";
import { VerdictBadge } from "./VerdictBadge";

interface DailyReportCardProps {
  report: DailyReportOut;
}

export const DailyReportCard = ({ report }: DailyReportCardProps) => {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3 border-b border-gray-100 pb-3">
        <div>
          <div className="flex items-baseline gap-2">
            <h3 className="text-lg font-semibold text-gray-900">
              {report.name ?? report.code}
            </h3>
            <span className="text-xs text-gray-400">{report.code}</span>
            {report.market && (
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                {MARKET_LABEL[report.market]}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-500">{report.date}</p>
        </div>
        <VerdictBadge verdict={report.verdict} />
      </div>

      {report.content ? (
        <div className="markdown-body prose prose-sm mt-4 max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report.content}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="mt-4 text-sm text-gray-400">리포트 본문이 없습니다.</p>
      )}
    </Card>
  );
};
