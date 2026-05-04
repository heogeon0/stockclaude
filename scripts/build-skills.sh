#!/usr/bin/env bash
# build-skills.sh
# .claude/skills/<name>/ 의 내용을 dist/<name>.zip 으로 패키징한다.
# Anthropic Claude skill 업로드 포맷: SKILL.md + 하위 디렉토리가 zip 루트에 위치.
#
# 사용법:
#   bash scripts/build-skills.sh           # 전체 스킬 빌드
#   bash scripts/build-skills.sh stock     # 특정 스킬만
#
# 산출물 이름 매핑: 스킬 폴더명 → zip 파일명
#   stock → stockclaude.zip   (외부 배포용 식별 이름)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/.claude/skills"
DIST_DIR="$REPO_ROOT/dist"

# 스킬 폴더명 → zip 파일명 매핑 (없으면 폴더명 그대로)
zip_name_for() {
  case "$1" in
    stock) echo "stockclaude" ;;
    *)     echo "$1" ;;
  esac
}

zip_skill() {
  local skill_dir="$1"
  local skill_name
  skill_name="$(basename "$skill_dir")"
  local out_name
  out_name="$(zip_name_for "$skill_name")"
  local out_zip="$DIST_DIR/${out_name}.zip"

  if [ ! -f "$skill_dir/SKILL.md" ]; then
    echo "  ! skip $skill_name — SKILL.md 없음"
    return
  fi

  rm -f "$out_zip"
  ( cd "$skill_dir" && zip -rq "$out_zip" . -x "*.DS_Store" -x ".env" -x ".env.*" )
  local size
  size="$(du -h "$out_zip" | cut -f1)"
  echo "  ✓ $skill_name → $out_zip ($size)"
}

mkdir -p "$DIST_DIR"

if [ $# -gt 0 ]; then
  for name in "$@"; do
    target="$SKILLS_DIR/$name"
    if [ ! -d "$target" ]; then
      echo "  ! skip $name — $target 없음"
      continue
    fi
    zip_skill "$target"
  done
else
  for skill_dir in "$SKILLS_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    zip_skill "${skill_dir%/}"
  done
fi

echo
echo "✅ 빌드 완료: $DIST_DIR"
