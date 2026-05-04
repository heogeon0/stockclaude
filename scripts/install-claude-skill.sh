#!/usr/bin/env bash
# install-claude-skill.sh
# Claude Code 의 ~/.claude/skills/stock/ 와 ~/.claude/commands/ 에 본 레포의 스킬/커맨드를 설치한다.
#
# 사용법:
#   bash scripts/install-claude-skill.sh           # symlink (권장 — 레포 갱신이 즉시 반영)
#   bash scripts/install-claude-skill.sh --copy    # cp (독립 사본 — 레포 변경 영향 X)
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_SRC="$REPO_ROOT/.claude/skills/stock"
COMMANDS_SRC="$REPO_ROOT/.claude/commands"

CLAUDE_DIR="$HOME/.claude"
SKILL_DEST="$CLAUDE_DIR/skills/stock"
COMMANDS_DEST="$CLAUDE_DIR/commands"

mode="${1:-symlink}"
case "$mode" in
  --copy) mode=copy ;;
  *) mode=symlink ;;
esac

echo "→ install mode: $mode"
echo "→ source skill: $SKILL_SRC"
echo "→ source commands: $COMMANDS_SRC"
echo "→ destination: $CLAUDE_DIR"

mkdir -p "$CLAUDE_DIR/skills" "$COMMANDS_DEST"

# 기존 stock skill 백업
if [ -e "$SKILL_DEST" ] || [ -L "$SKILL_DEST" ]; then
  backup="$SKILL_DEST.bak.$(date +%Y%m%d-%H%M%S)"
  echo "  ! 기존 $SKILL_DEST → $backup 로 백업"
  mv "$SKILL_DEST" "$backup"
fi

# skill 설치
if [ "$mode" = "symlink" ]; then
  ln -s "$SKILL_SRC" "$SKILL_DEST"
  echo "  ✓ skill symlink 생성: $SKILL_DEST → $SKILL_SRC"
else
  cp -R "$SKILL_SRC" "$SKILL_DEST"
  echo "  ✓ skill 복사: $SKILL_DEST"
fi

# commands 설치 (각 .md 별로)
for cmd_file in "$COMMANDS_SRC"/*.md; do
  [ -e "$cmd_file" ] || continue
  base="$(basename "$cmd_file")"
  dest="$COMMANDS_DEST/$base"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    backup="$dest.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$dest" "$backup"
    echo "  ! 기존 $dest → $backup"
  fi
  if [ "$mode" = "symlink" ]; then
    ln -s "$cmd_file" "$dest"
    echo "  ✓ command symlink: $base"
  else
    cp "$cmd_file" "$dest"
    echo "  ✓ command 복사: $base"
  fi
done

echo
echo "✅ 설치 완료. Claude Code 새 세션에서 /stock-daily 등 슬래시 커맨드 사용 가능."
