import { Badge, Card } from "@tremor/react";
import { SKILL_CATALOG, SKILL_ROLE_LABEL } from "@/lib/skillCatalog";
import { SkillWorkflowDiagram } from "./SkillWorkflowDiagram";

const ROLE_BADGE_COLOR = {
  hub: "slate",
  entry: "blue",
  module: "violet",
  base: "emerald",
  deprecated: "gray",
} as const;

export const WorkflowSection = () => (
  <Card>
    <header className="mb-4">
      <h3 className="text-lg font-semibold text-gray-900">스킬 워크플로우 (v17)</h3>
      <p className="mt-1 text-sm text-gray-500">
        8 skill — 1 허브 + 6 active + 1 DEPRECATED. 점선 화살표는 base 만기 시 자동 연쇄 갱신.
        stock-research 가 공통 6차원 분석 모듈로 daily/discover 가 호출.
      </p>
    </header>

    <div className="overflow-x-auto">
      <SkillWorkflowDiagram />
    </div>

    <ul className="mt-4 space-y-2 text-sm">
      {SKILL_CATALOG.map((s) => {
        const isDeprecated = s.role === "deprecated";
        return (
          <li key={s.name} className="flex items-start gap-3">
            <Badge color={ROLE_BADGE_COLOR[s.role]} size="xs" className="mt-0.5 shrink-0">
              {SKILL_ROLE_LABEL[s.role]}
            </Badge>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-2">
                <span
                  className={`font-mono text-xs ${
                    isDeprecated ? "text-gray-400 line-through" : "text-blue-700"
                  }`}
                >
                  /{s.name}
                </span>
                {s.expiry && (
                  <span className="text-xs text-emerald-700">만기 {s.expiry}</span>
                )}
                {s.deprecatedAt && (
                  <span className="text-xs text-amber-700">
                    {s.deprecatedAt} — {s.replacedBy} 로 흡수
                  </span>
                )}
              </div>
              <p className={`text-xs ${isDeprecated ? "text-gray-400" : "text-gray-700"}`}>
                {s.summary}
              </p>
              {s.triggers && s.triggers.length > 0 && (
                <p className="mt-0.5 text-xs text-gray-500">
                  트리거: {s.triggers.join(" · ")}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  </Card>
);
