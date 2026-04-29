import { Badge, Card, ProgressBar } from "@tremor/react";
import { GRADE_COLOR } from "@/lib/constants";
import type { Grade } from "@/types/api";

interface StockScoreCardProps {
  totalScore: number | null;
  grade: Grade | null;
  financialScore: number | null;
  industryScore: number | null;
  economyScore: number | null;
}

interface SubScoreRowProps {
  label: string;
  value: number | null;
}

const SubScoreRow = ({ label, value }: SubScoreRowProps) => (
  <div className="flex items-center gap-3">
    <span className="w-16 text-xs text-gray-500">{label}</span>
    <div className="flex-1">
      <ProgressBar value={value ?? 0} color="blue" />
    </div>
    <span className="w-8 text-right tabular-nums text-xs font-medium text-gray-700">
      {value ?? "-"}
    </span>
  </div>
);

export const StockScoreCard = ({
  totalScore,
  grade,
  financialScore,
  industryScore,
  economyScore,
}: StockScoreCardProps) => {
  return (
    <Card>
      <p className="text-xs text-gray-500">종합 스코어</p>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums text-gray-900">
          {totalScore ?? "-"}
        </span>
        {grade && (
          <Badge color={GRADE_COLOR[grade]} size="xs">
            {grade}
          </Badge>
        )}
      </div>
      <div className="mt-3 space-y-1.5">
        <SubScoreRow label="재무" value={financialScore} />
        <SubScoreRow label="산업" value={industryScore} />
        <SubScoreRow label="거시" value={economyScore} />
      </div>
    </Card>
  );
};
