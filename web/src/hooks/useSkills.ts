import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { SkillListOut } from "@/types/api";

export const useSkills = () =>
  useQuery({
    queryKey: ["skills", "list"],
    queryFn: () => apiGet<SkillListOut>("/skills"),
    staleTime: 60 * 1000,
  });
