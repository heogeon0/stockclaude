import { Badge } from "@tremor/react";
import { VERDICT_COLOR } from "@/lib/constants";
import type { Verdict } from "@/types/api";

interface VerdictBadgeProps {
  verdict: Verdict | string | null;
}

export const VerdictBadge = ({ verdict }: VerdictBadgeProps) => {
  if (!verdict) {
    return (
      <Badge color="gray" size="xs">
        미판정
      </Badge>
    );
  }
  const color = VERDICT_COLOR[verdict as Verdict] ?? "gray";
  return <Badge color={color}>{verdict}</Badge>;
};
