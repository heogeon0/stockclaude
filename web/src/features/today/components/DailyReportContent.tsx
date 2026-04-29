import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface DailyReportContentProps {
  content: string | null | undefined;
  /** 본문이 비어있을 때 표시할 placeholder. */
  emptyPlaceholder?: string;
}

/** stock_daily.content · industries.content · economy_*.content 공용 마크다운 렌더러. */
export const DailyReportContent = ({
  content,
  emptyPlaceholder = "본문이 없습니다.",
}: DailyReportContentProps) => {
  if (!content) {
    return <p className="text-sm text-gray-400">{emptyPlaceholder}</p>;
  }
  return (
    <div className="markdown-body prose prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
};
