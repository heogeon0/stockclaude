import { Badge, Card } from "@tremor/react";
import { useMemo, useState } from "react";
import {
  ALL_TAGS,
  ANALYSIS_MODULES,
  TAG_LABEL,
  type AnalysisModule,
  type ModuleTag,
} from "@/lib/analysisModules";

type FilterKey = ModuleTag | "all";

const TAG_COLOR: Record<ModuleTag, "blue" | "violet" | "emerald" | "amber"> = {
  technical: "blue",
  fundamental: "violet",
  portfolio: "emerald",
  macro: "amber",
};

export const AnalysisModulesSection = () => {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return ANALYSIS_MODULES.filter((m) => {
      const tagMatch = filter === "all" || m.tags.includes(filter);
      if (!tagMatch) return false;
      if (!q) return true;
      return (
        m.name_ko.toLowerCase().includes(q) ||
        m.name_en.toLowerCase().includes(q) ||
        m.summary.toLowerCase().includes(q)
      );
    });
  }, [filter, search]);

  return (
    <Card>
      <header className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">분석 모듈 카탈로그</h3>
        <p className="mt-1 text-sm text-gray-500">
          server/analysis/*.py 16개. 클릭(펼침)해서 입출력·MCP 툴·DB 테이블 확인.
        </p>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-md border border-gray-200 bg-white p-0.5">
          {ALL_TAGS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setFilter(t.key)}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                filter === t.key
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="검색 (모듈명·요약)"
          className="flex-1 min-w-[200px] rounded border border-gray-200 px-3 py-1.5 text-sm"
        />
        <span className="text-xs text-gray-400">
          {filtered.length} / {ANALYSIS_MODULES.length}
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((m) => (
          <ModuleCard key={m.id} module={m} />
        ))}
      </div>
    </Card>
  );
};

const ModuleCard = ({ module: m }: { module: AnalysisModule }) => (
  <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
    <div className="flex items-start justify-between gap-2">
      <div>
        <h4 className="text-sm font-semibold text-gray-900">{m.name_ko}</h4>
        <p className="text-xs font-mono text-gray-400">{m.name_en}</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {m.tags.map((t) => (
          <Badge key={t} color={TAG_COLOR[t]} size="xs">
            {TAG_LABEL[t]}
          </Badge>
        ))}
      </div>
    </div>
    <p className="mt-2 text-xs text-gray-700">{m.summary}</p>

    <details className="mt-2">
      <summary className="cursor-pointer text-xs font-medium text-blue-700">
        자세히
      </summary>
      <div className="mt-2 space-y-2 text-xs text-gray-700">
        <p>{m.description}</p>
        <KeyValueList label="입력" items={m.inputs} />
        <KeyValueList label="출력" items={m.outputs} />
        {m.mcp_tools.length > 0 && (
          <KeyValueList label="MCP 툴" items={m.mcp_tools} mono />
        )}
        {m.db_tables.length > 0 && (
          <KeyValueList label="DB 테이블" items={m.db_tables} mono />
        )}
        {m.notes && (
          <p className="rounded bg-amber-50 px-2 py-1 text-amber-800">
            ⚠ {m.notes}
          </p>
        )}
      </div>
    </details>
  </div>
);

interface KeyValueListProps {
  label: string;
  items: string[];
  mono?: boolean;
}

const KeyValueList = ({ label, items, mono }: KeyValueListProps) => (
  <div>
    <p className="text-xs font-medium text-gray-600">{label}</p>
    <div className="mt-0.5 flex flex-wrap gap-1">
      {items.map((it) => (
        <span
          key={it}
          className={`rounded bg-white px-1.5 py-0.5 text-xs ${
            mono ? "font-mono text-gray-700" : "text-gray-600"
          } border border-gray-200`}
        >
          {it}
        </span>
      ))}
    </div>
  </div>
);
