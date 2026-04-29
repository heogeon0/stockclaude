import { Card } from "@tremor/react";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { EmptyState } from "@/components/EmptyState";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { DailyReportContent } from "@/features/today/components/DailyReportContent";
import { useSkillContent } from "@/hooks/useSkillContent";
import { useSkills } from "@/hooks/useSkills";
import type { SkillName } from "@/types/api";

const DEFAULT_SKILL: SkillName = "stock";
const VALID: readonly SkillName[] = [
  "stock",
  "stock-research",
  "stock-daily",
  "stock-momentum",
  "stock-discover",
] as const;

export const SkillsPage = () => {
  const list = useSkills();
  const [searchParams, setSearchParams] = useSearchParams();

  const selected = useMemo<SkillName>(() => {
    const raw = (searchParams.get("skill") ?? DEFAULT_SKILL) as SkillName;
    return VALID.includes(raw) ? raw : DEFAULT_SKILL;
  }, [searchParams]);

  const handleSelect = (name: SkillName) => {
    const next = new URLSearchParams(searchParams);
    if (name === DEFAULT_SKILL) {
      next.delete("skill");
    } else {
      next.set("skill", name);
    }
    setSearchParams(next, { replace: true });
  };

  const content = useSkillContent(selected);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-2xl font-semibold text-gray-900">스킬 매뉴얼</h2>
        <p className="mt-1 text-sm text-gray-500">
          <code className="rounded bg-gray-100 px-1 py-0.5 text-xs">
            ~/.claude/skills/*/SKILL.md
          </code>
          {" "}라이브 렌더. 5개 화이트리스트만 노출.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-[220px_1fr]">
        <aside>
          <Card>
            {list.isLoading ? (
              <LoadingSkeleton rows={3} />
            ) : list.error ? (
              <ErrorNotice error={list.error} title="스킬 목록 조회 실패" />
            ) : (
              <ul className="space-y-1">
                {(list.data?.skills ?? []).map((s) => {
                  const active = s.name === selected;
                  return (
                    <li key={s.name}>
                      <button
                        type="button"
                        onClick={() => handleSelect(s.name)}
                        className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                          active
                            ? "bg-blue-50 text-blue-700"
                            : "text-gray-700 hover:bg-gray-50"
                        }`}
                      >
                        <div className="font-medium">{s.name}</div>
                        {s.title && (
                          <div className="mt-0.5 text-xs text-gray-500 line-clamp-2">
                            {s.title}
                          </div>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </aside>

        <main>
          <Card>
            {content.isLoading && <LoadingSkeleton rows={6} />}
            {content.error && (
              <ErrorNotice error={content.error} title="스킬 본문 조회 실패" />
            )}
            {content.data && (
              <>
                <header className="mb-3 flex items-baseline justify-between">
                  <p className="text-xs text-gray-400 font-mono">
                    {content.data.name}/SKILL.md
                  </p>
                  {content.data.updated_at && (
                    <p className="text-xs text-gray-400">
                      업데이트{" "}
                      {new Date(content.data.updated_at).toLocaleString("ko-KR")}
                    </p>
                  )}
                </header>
                <DailyReportContent content={content.data.content} />
              </>
            )}
            {!content.data && !content.isLoading && !content.error && (
              <EmptyState title="스킬을 선택하세요" />
            )}
          </Card>
        </main>
      </div>
    </div>
  );
};
