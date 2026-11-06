#!/usr/bin/env python3
"""
Transcript Locator: Auto-detect the most recent agent transcript file
across Antigravity, Claude Code, Cline/Roo Code, and local workspace.
"""

import os
import sys
import glob
from pathlib import Path
from typing import Optional, List, Tuple


def probe_antigravity() -> List[Tuple[float, str, str]]:
    """Probe Google Antigravity transcripts."""
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
        # Search for transcript.jsonl in .system_generated/logs/
        for p in brain_dir.glob("*/.system_generated/logs/transcript.jsonl"):
            try:
                mtime = p.stat().st_mtime
                results.append((mtime, str(p), "antigravity"))
            except OSError:
                continue
    return results


def probe_claude_code() -> List[Tuple[float, str, str]]:
    """Probe Claude Code transcripts."""
    results = []
    claude_projects = Path.home() / ".claude" / "projects"
    if claude_projects.is_dir():
        for p in claude_projects.glob("**/*.jsonl"):
            try:
                mtime = p.stat().st_mtime
                results.append((mtime, str(p), "claude-code"))
            except OSError:
                continue
    return results


def probe_roo_cline() -> List[Tuple[float, str, str]]:
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
                mtime = p.stat().st_mtime
                results.append((mtime, str(p), "cline"))
            except OSError:
                continue
    return results


def probe_local_workspace() -> List[Tuple[float, str, str]]:
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
                mtime = p.stat().st_mtime
                results.append((mtime, str(p), "local"))
            except OSError:
                continue
    return results


def find_latest_transcript(explicit_path: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Find the most relevant transcript.
    Returns (file_path, agent_type) or None.
    """
    if explicit_path:
        p = Path(explicit_path).expanduser().resolve()
        if p.is_file():
            # Check content or extension to guess agent
            return str(p), "explicit"
        elif p.is_dir():
            # Check if directory contains transcript.jsonl
            candidate = p / ".system_generated" / "logs" / "transcript.jsonl"
            if candidate.is_file():
                return str(candidate), "antigravity"
            # Or newest .jsonl in that dir
            sub_jsonls = list(p.glob("**/*.jsonl"))
            if sub_jsonls:
                sub_jsonls.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return str(sub_jsonls[0]), "custom"

    candidates: List[Tuple[float, str, str]] = []
    candidates.extend(probe_antigravity())
    candidates.extend(probe_claude_code())
    candidates.extend(probe_roo_cline())
    candidates.extend(probe_local_workspace())

    if not candidates:
        return None

    # Sort descending by modification time
    candidates.sort(key=lambda item: item[0], reverse=True)
    latest_mtime, latest_path, agent_type = candidates[0]
    return latest_path, agent_type


def main():
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    result = find_latest_transcript(explicit)
    if result:
        path, agent_type = result
        print(path)
        sys.exit(0)
    else:
        sys.stderr.write("Error: No agent transcript file found.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
