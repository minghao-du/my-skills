#!/usr/bin/env python3
"""
Transcript Locator: Auto-detect the most relevant agent transcript file
across Antigravity, Claude Code, Cline/Roo Code, and local workspace.
Supports intelligent skipping of stub/empty sessions and session offset selection.
"""

import os
import sys
import glob
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple


def probe_antigravity() -> List[Tuple[float, int, str, str]]:
    """Probe Google Antigravity transcripts (mtime, size, path, type)."""
    results = []
    base_dirs = [
        Path.home() / ".gemini" / "antigravity",
    ]
    env_dir = os.environ.get("ANTIGRAVITY_APP_DATA")
    if env_dir:
        base_dirs.insert(0, Path(env_dir))

    for base in base_dirs:
        brain_dir = base / "brain"
        if not brain_dir.is_dir():
            continue
        for p in brain_dir.glob("*/.system_generated/logs/transcript.jsonl"):
            try:
                st = p.stat()
                results.append((st.st_mtime, st.st_size, str(p), "antigravity"))
            except OSError:
                continue
    return results


def probe_claude_code() -> List[Tuple[float, int, str, str]]:
    """Probe Claude Code transcripts."""
    results = []
    claude_projects = Path.home() / ".claude" / "projects"
    if claude_projects.is_dir():
        for p in claude_projects.glob("**/*.jsonl"):
            try:
                st = p.stat()
                results.append((st.st_mtime, st.st_size, str(p), "claude-code"))
            except OSError:
                continue
    return results


def probe_roo_cline() -> List[Tuple[float, int, str, str]]:
    """Probe Roo Code / Cline task conversation files."""
    results = []
    app_support = Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage"
    if not app_support.is_dir():
        return results

    patterns = [
        "rooveterinaryinc.roo-cline/tasks/*/api_conversation_history.json",
        "rooveterinaryinc.roo-cline/tasks/*/ui_messages.json",
        "saoudrizwan.claude-dev/tasks/*/api_conversation_history.json",
    ]
    for pattern in patterns:
        for p in app_support.glob(pattern):
            try:
                st = p.stat()
                results.append((st.st_mtime, st.st_size, str(p), "cline"))
            except OSError:
                continue
    return results


def probe_local_workspace() -> List[Tuple[float, int, str, str]]:
    """Probe current working directory and subdirectories for transcript files."""
    results = []
    cwd = Path.cwd()
    patterns = [
        "transcript*.jsonl",
        "*.jsonl",
        "logs/*.jsonl",
        ".logs/*.jsonl",
    ]
    for pat in patterns:
        for p in cwd.glob(pat):
            try:
                st = p.stat()
                results.append((st.st_mtime, st.st_size, str(p), "local"))
            except OSError:
                continue
    return results


def get_all_candidates() -> List[Tuple[float, int, str, str]]:
    """Collect and sort all transcript candidates descending by mtime."""
    candidates: List[Tuple[float, int, str, str]] = []
    candidates.extend(probe_antigravity())
    candidates.extend(probe_claude_code())
    candidates.extend(probe_roo_cline())
    candidates.extend(probe_local_workspace())
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def find_latest_transcript(
    explicit_path: Optional[str] = None,
    min_size: int = 1500,
    offset: int = 0
) -> Optional[Tuple[str, str]]:
    """
    Find the most relevant transcript.
    min_size: ignore tiny stub files created when starting a brand new conversation.
    offset: 0 = latest non-empty, 1 = previous non-empty, etc.
    """
    if explicit_path:
        p = Path(explicit_path).expanduser().resolve()
        if p.is_file():
            return str(p), "explicit"
        elif p.is_dir():
            candidate = p / ".system_generated" / "logs" / "transcript.jsonl"
            if candidate.is_file():
                return str(candidate), "antigravity"
            sub_jsonls = list(p.glob("**/*.jsonl"))
            if sub_jsonls:
                sub_jsonls.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return str(sub_jsonls[0]), "custom"

    candidates = get_all_candidates()
    if not candidates:
        return None

    # Filter out empty or tiny stubs if requested
    filtered = [c for c in candidates if c[1] >= min_size]
    pool = filtered if filtered else candidates

    if offset < len(pool):
        item = pool[offset]
        return item[2], item[3]
    return pool[0][2], pool[0][3]


def main():
    parser = argparse.ArgumentParser(description="Find the latest or specific agent conversation transcript.")
    parser.add_argument("path", nargs="?", help="Explicit path to transcript file or directory")
    parser.add_argument("--offset", type=int, default=0, help="Offset index (0=latest non-empty, 1=previous, etc.)")
    parser.add_argument("--min-size", type=int, default=1500, help="Minimum file size in bytes to ignore empty/stub sessions (default: 1500)")
    parser.add_argument("--list", action="store_true", help="List recent candidate transcripts and exit")
    args = parser.parse_args()

    if args.list:
        candidates = get_all_candidates()
        print(f"Found {len(candidates)} candidate transcripts:")
        for idx, (mtime, size, path, agent_type) in enumerate(candidates[:10]):
            dt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            kb = size / 1024
            print(f"[{idx}] {dt_str} | {agent_type:11s} | {kb:6.1f} KB | {path}")
        sys.exit(0)

    result = find_latest_transcript(args.path, min_size=args.min_size, offset=args.offset)
    if result:
        path, agent_type = result
        print(path)
        sys.exit(0)
    else:
        sys.stderr.write("Error: No agent transcript file found.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
