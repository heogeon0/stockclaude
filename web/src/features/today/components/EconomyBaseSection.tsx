import { Card } from "@tremor/react";
import type { EconomyBaseOut } from "@/types/api";
import { DailyReportContent } from "./DailyReportContent";

interface EconomyBaseSectionProps {
  base: EconomyBaseOut | null;
}

export const EconomyBaseSection = ({ base }: EconomyBaseSectionProps) => {
  if (!base) {
    return (
      <Card>
        <p className="text-sm text-gray-500">경제 기본 리포트가 없습니다.</p>
      </Card>
    );
  }
  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h3 className="text-base font-semibold text-gray-900">거시 기본 (Base)</h3>
        <span className="text-xs text-gray-500">
          업데이트 {new Date(base.updated_at).toLocaleDateString("ko-KR")}
        </span>
      </div>
      <div className="mt-3">
        <DailyReportContent content={base.content} />
      </div>
    </Card>
  );
};
