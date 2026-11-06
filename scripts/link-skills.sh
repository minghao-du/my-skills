#!/usr/bin/env bash
set -euo pipefail

# Links skills in the repository into skill directories used by agent harnesses:
# Default destinations (when not specified):
#   - ~/.claude/skills: Claude Code
#   - ~/.agents/skills: Codex and other Agent Skills-compatible harnesses
#
# Usage:
#   link-skills.sh [SKILL_PATH] [DEST_DIR]
#   link-skills.sh [-s|--skill <path>] [-d|--dest <dir>]

REPO="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS] [SKILL_PATH] [DEST_DIR]

Links skills from this repository to target skill directories.

Arguments:
  SKILL_PATH          Path to a specific skill directory containing SKILL.md (relative or absolute)
  DEST_DIR            Target directory to place skill symlinks into

Options:
  -s, --skill PATH    Path to a specific skill directory containing SKILL.md
  -d, --dest DIR      Target directory to place skill symlinks into
  -h, --help          Show this help message and exit

Defaults:
  - If neither SKILL_PATH nor DEST_DIR is provided:
      Links ALL skills to ~/.claude/skills and ~/.agents/skills
  - If only SKILL_PATH is provided:
      Links that skill to ~/.claude/skills and ~/.agents/skills
  - If only DEST_DIR is provided:
      Links ALL skills to DEST_DIR
EOF
}

SKILL_ARG=""
DEST_ARG=""
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -s|--skill)
      if [[ $# -lt 2 ]]; then
        echo "error: -s/--skill requires an argument" >&2
        exit 1
      fi
      SKILL_ARG="$2"
      shift 2
      ;;
    -d|--dest)
      if [[ $# -lt 2 ]]; then
        echo "error: -d/--dest requires an argument" >&2
        exit 1
      fi
      DEST_ARG="$2"
      shift 2
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        POSITIONAL_ARGS+=("$1")
        shift
      done
      break
      ;;
    -*)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$SKILL_ARG" && ${#POSITIONAL_ARGS[@]} -ge 1 ]]; then
  SKILL_ARG="${POSITIONAL_ARGS[0]}"
  if [[ -z "$DEST_ARG" && ${#POSITIONAL_ARGS[@]} -ge 2 ]]; then
    DEST_ARG="${POSITIONAL_ARGS[1]}"
  fi
  if [[ ${#POSITIONAL_ARGS[@]} -gt 2 ]]; then
    echo "error: too many positional arguments (expected at most 2: [SKILL_PATH] [DEST_DIR])" >&2
    usage >&2
    exit 1
  fi
elif [[ -z "$DEST_ARG" && ${#POSITIONAL_ARGS[@]} -ge 1 ]]; then
  DEST_ARG="${POSITIONAL_ARGS[0]}"
  if [[ ${#POSITIONAL_ARGS[@]} -gt 1 ]]; then
    echo "error: too many positional arguments" >&2
    usage >&2
    exit 1
  fi
elif [[ ${#POSITIONAL_ARGS[@]} -gt 0 ]]; then
  echo "error: unexpected positional arguments when options are already provided: ${POSITIONAL_ARGS[*]}" >&2
  usage >&2
  exit 1
fi

# Expand tilde if passed as quoted string
SKILL_ARG="${SKILL_ARG/#\~/$HOME}"
DEST_ARG="${DEST_ARG/#\~/$HOME}"

# Determine skills to link
names=()
srcs=()

if [[ -n "$SKILL_ARG" ]]; then
  if [[ ! -d "$SKILL_ARG" ]]; then
    echo "error: skill directory not found: '$SKILL_ARG'" >&2
    exit 1
  fi
  if [[ ! -f "$SKILL_ARG/SKILL.md" ]]; then
    echo "error: not a valid skill directory (missing SKILL.md): '$SKILL_ARG'" >&2
    exit 1
  fi

  skill_src="$(cd "$SKILL_ARG" && pwd)"
  names+=("$(basename "$skill_src")")
  srcs+=("$skill_src")
else
  # Collect every skill directory that contains a SKILL.md.
  while IFS= read -r -d '' skill_md; do
    src="$(dirname "$skill_md")"
    names+=("$(basename "$src")")
    srcs+=("$src")
  done < <(find "$REPO/skills" -name SKILL.md -not -path '*/node_modules/*' -print0)
fi

# Determine target destinations
if [[ -n "$DEST_ARG" ]]; then
  DESTS=("$DEST_ARG")
else
  DESTS=("$HOME/.claude/skills" "$HOME/.agents/skills")
fi

for DEST in "${DESTS[@]}"; do
  # If $DEST is a symlink that resolves into this repo, we'd end up writing the
  # per-skill symlinks back into the repo's own skills/ tree. Detect and bail
  # out instead of polluting the working copy.
  if [ -L "$DEST" ]; then
    resolved="$(readlink -f "$DEST")"
    case "$resolved" in
      "$REPO"|"$REPO"/*)
        echo "error: $DEST is a symlink into this repo ($resolved)." >&2
        echo "Remove it (rm \"$DEST\") and re-run; the script will recreate it as a real dir." >&2
        exit 1
        ;;
    esac
  fi

  mkdir -p "$DEST"

  for i in "${!names[@]}"; do
    name="${names[$i]}"
    src="${srcs[$i]}"
    target="$DEST/$name"

    # Avoid symlinking a directory to itself if target equals source
    if [ "$src" = "$target" ]; then
      echo "warning: skipping $name (target is same as source: $src)" >&2
      continue
    fi

    if [ -e "$target" ] && [ ! -L "$target" ]; then
      rm -rf "$target"
    fi

    ln -sfn "$src" "$target"
    echo "linked $name -> $src ($DEST)"
  done
done
