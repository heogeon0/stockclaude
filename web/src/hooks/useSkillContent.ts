import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { SkillContentOut, SkillName } from "@/types/api";

export const useSkillContent = (name: SkillName | null) =>
  useQuery({
    queryKey: ["skills", "content", name],
    queryFn: () => apiGet<SkillContentOut>(`/skills/${name}`),
    enabled: !!name,
    staleTime: 60 * 1000,
  });
