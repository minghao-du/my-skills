#!/usr/bin/env python3
"""
Transcript Retro Context Extractor:
Deterministically extracts a compact, high-density timeline and friction hotspots
from an agent transcript, protecting context window while exposing key facts.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Try to import find_transcript from same directory
try:
    from find_transcript import find_latest_transcript
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from find_transcript import find_latest_transcript


def clean_user_prompt(text: str) -> str:
    """Clean internal tags from user prompts like <ADDITIONAL_METADATA>."""
    if not text:
        return ""
    match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        text = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL)
        text = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", text, flags=re.DOTALL)
        text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_session_id(file_path: Path) -> str:
    """Extract human-meaningful session ID from path."""
    parts = list(file_path.parts)
    if ".system_generated" in parts:
        idx = parts.index(".system_generated")
        if idx > 0:
            return parts[idx - 1]
    if len(parts) >= 2 and parts[-2] in ("logs", "subagents", "tasks"):
        return parts[-3] if len(parts) >= 3 else parts[-2]
    return file_path.stem


def parse_transcript_compact(file_path: str) -> Dict[str, Any]:
    """Parse transcript and extract compact statistics and structured steps."""
    p = Path(file_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Transcript file not found: {file_path}")

    raw_lines = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                raw_lines.append(line_str)

    parsed_objects = []
    is_antigravity = False
    is_claude_code = False

    for line in raw_lines:
        try:
            data = json.loads(line)
            parsed_objects.append(data)
            if "step_index" in data or "source" in data:
                is_antigravity = True
            elif "sessionId" in data or "uuid" in data or "agentId" in data:
                is_claude_code = True
        except json.JSONDecodeError:
            continue

    session_id = extract_session_id(p)
    steps: List[Dict[str, Any]] = []
    friction_events: List[Dict[str, Any]] = []
    tool_counts: Dict[str, int] = {}
    total_output_chars = 0
    timestamps: List[datetime] = []

    if is_antigravity:
        i = 0
        n = len(parsed_objects)
        while i < n:
            item = parsed_objects[i]
            step_idx = item.get("step_index", len(steps))
            step_type = item.get("type", "")
            source = item.get("source", "")
            status = item.get("status", "DONE")
            created_at = item.get("created_at")
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    timestamps.append(dt)
                except Exception:
                    pass

            # Skip pure ephemeral heartbeats
            if step_type == "EPHEMERAL_MESSAGE" and status == "DONE":
                i += 1
                continue

            content = item.get("content", "")
            thinking = item.get("thinking", "")
            tool_calls = item.get("tool_calls", [])

            # Case A: User input
            if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
                clean_text = clean_user_prompt(content)
                first_line = clean_text.split("\n")[0][:100] if clean_text else "User Input"
                is_correction = any(k in clean_text.lower() for k in ["wrong", "error", "fail", "不对", "不是", "重新", "不要", "修复"])
                
                step_record = {
                    "step_idx": step_idx,
                    "kind": "USER",
                    "summary": first_line,
                    "full_content": clean_text,
                    "status": status,
                    "is_correction": is_correction,
                }
                if is_correction:
                    friction_events.append({
                        "step_idx": step_idx,
                        "type": "USER_STEERING",
                        "summary": f"User corrective input: {first_line}",
                    })
                steps.append(step_record)
                i += 1
                continue

            # Case B: Tool call & Model response
            if tool_calls:
                tool_output = ""
                # Look ahead for GENERIC tool output
                if i + 1 < n and parsed_objects[i + 1].get("type") == "GENERIC":
                    tool_output = parsed_objects[i + 1].get("content", "")
                    i += 1

                out_len = len(tool_output)
                total_output_chars += out_len

                for tc in tool_calls:
                    t_name = tc.get("name", "tool")
                    tool_counts[t_name] = tool_counts.get(t_name, 0) + 1
                    t_args = tc.get("args", {})
                    
                    # Detect tool errors or failures accurately
                    is_error = False
                    tool_out_lower = tool_output.lower()
                    if status == "ERROR":
                        is_error = True
                    elif "command exited with code" in tool_out_lower:
                        if "command exited with code 0" not in tool_out_lower:
                            is_error = True
                    elif "traceback (most recent call last)" in tool_out_lower:
                        is_error = True
                    elif t_name == "run_command" and "error:" in tool_out_lower and "command exited with code 0" not in tool_out_lower:
                        is_error = True

                    # Detect context bloat
                    is_bloated = out_len > 12000

                    # Summarize arguments
                    arg_summary = ""
                    if t_name == "run_command":
                        cmd = t_args.get("CommandLine", "")
                        if isinstance(cmd, str):
                            cmd = cmd.strip()
                            if cmd.startswith('"') and cmd.endswith('"'):
                                cmd = cmd[1:-1]
                        arg_summary = str(cmd).replace("\n", " ")[:70]
                    elif t_name in ("read_file", "write_file", "edit_file"):
                        p_arg = t_args.get("Path", "")
                        if isinstance(p_arg, str):
                            p_arg = p_arg.strip().strip('"').strip("'")
                        arg_summary = os.path.basename(p_arg) if p_arg else ""
                    elif t_name == "ask_question":
                        qs = t_args.get("questions", [])
                        if qs and isinstance(qs[0], dict):
                            arg_summary = qs[0].get("question", "")[:60]
                        elif qs and isinstance(qs[0], str):
                            arg_summary = qs[0][:60]
                        else:
                            arg_summary = "question"
                    else:
                        arg_summary = json.dumps(t_args, ensure_ascii=False)[:60]

                    if is_error:
                        friction_events.append({
                            "step_idx": step_idx,
                            "type": "TOOL_ERROR",
                            "summary": f"{t_name} failed: {arg_summary}",
                        })
                    if is_bloated:
                        friction_events.append({
                            "step_idx": step_idx,
                            "type": "CONTEXT_BLOAT",
                            "summary": f"{t_name} produced {out_len} chars output",
                        })

                    steps.append({
                        "step_idx": step_idx,
                        "kind": "TOOL",
                        "tool": t_name,
                        "args_summary": arg_summary,
                        "output_length": out_len,
                        "is_error": is_error,
                        "is_bloated": is_bloated,
                        "thinking_snippet": thinking[:150].strip() if thinking else "",
                        "output_snippet": tool_output[:250].strip() if tool_output else "",
                    })
                i += 1
                continue

            # Case C: Model text response (no tools)
            if content:
                steps.append({
                    "step_idx": step_idx,
                    "kind": "ASSISTANT",
                    "summary": content.split("\n")[0][:100],
                    "output_length": len(content),
                    "thinking_snippet": thinking[:150].strip() if thinking else "",
                })
            i += 1
    else:
        # Fallback for Claude Code or other formats
        for idx, item in enumerate(parsed_objects):
            steps.append({
                "step_idx": idx,
                "kind": item.get("type", "step"),
                "summary": str(item)[:100],
                "raw": item,
            })

    # Duration calculation
    duration_str = "unknown"
    if len(timestamps) >= 2:
        diff = (timestamps[-1] - timestamps[0]).total_seconds()
        mins, secs = divmod(int(diff), 60)
        duration_str = f"{mins}m {secs}s"

    return {
        "file_path": str(p),
        "session_id": session_id,
        "agent_harness": "antigravity" if is_antigravity else ("claude-code" if is_claude_code else "generic"),
        "total_steps": len(steps),
        "total_tool_calls": sum(tool_counts.values()),
        "tool_breakdown": tool_counts,
        "total_output_chars": total_output_chars,
        "duration": duration_str,
        "friction_events": friction_events,
        "steps": steps,
    }


def format_markdown_summary(data: Dict[str, Any], friction_only: bool = False) -> str:
    """Format parsed context into clean Markdown."""
    lines = []
    lines.append(f"# Conversation Compact Timeline: `{data['session_id']}`")
    lines.append("")
    lines.append("## Overview Metrics")
    lines.append(f"- **Transcript Path**: `{data['file_path']}`")
    lines.append(f"- **Agent Harness**: `{data['agent_harness']}`")
    lines.append(f"- **Duration**: {data['duration']}")
    lines.append(f"- **Total Steps**: {data['total_steps']}")
    lines.append(f"- **Total Tool Calls**: {data['total_tool_calls']}")
    lines.append(f"- **Friction Hotspots Detected**: {len(data['friction_events'])}")
    if data["tool_breakdown"]:
        breakdown = ", ".join(f"`{k}`: {v}" for k, v in sorted(data["tool_breakdown"].items(), key=lambda x: -x[1]))
        lines.append(f"- **Tool Distribution**: {breakdown}")
    lines.append("")

    # Friction section
    lines.append("## Friction Hotspots (High-Priority Review Targets)")
    if data["friction_events"]:
        lines.append("| Step | Type | Description |")
        lines.append("| :--- | :--- | :--- |")
        for ev in data["friction_events"]:
            lines.append(f"| Step {ev['step_idx']} | `{ev['type']}` | {ev['summary']} |")
    else:
        lines.append("> [!NOTE] No obvious friction events (errors, severe bloat, or user corrections) detected automatically.")
    lines.append("")

    # Timeline section
    lines.append("## Step-by-Step Compact Timeline")
    for s in data["steps"]:
        idx = s.get("step_idx", "?")
        kind = s.get("kind", "")
        if friction_only and not s.get("is_error") and not s.get("is_bloated") and not s.get("is_correction"):
            continue

        if kind == "USER":
            corr = " [CORRECTION]" if s.get("is_correction") else ""
            lines.append(f"### [Step {idx}] 👤 USER{corr}")
            lines.append(f"> {s.get('summary')}")
            lines.append("")
        elif kind == "TOOL":
            err_badge = " ❌ [ERROR]" if s.get("is_error") else " ✅ [OK]"
            bloat_badge = f" ⚠️ [{s.get('output_length')} chars]" if s.get("is_bloated") else ""
            lines.append(f"- **[Step {idx}]** `{s.get('tool')}` ({s.get('args_summary')}){err_badge}{bloat_badge}")
            if s.get("thinking_snippet"):
                lines.append(f"  - *Intent*: {s.get('thinking_snippet')}")
            if s.get("is_error") and s.get("output_snippet"):
                clean_snippet = s.get("output_snippet").replace("\n", " ")[:160]
                lines.append(f"  - *Error Output*: `{clean_snippet}`")
        elif kind == "ASSISTANT":
            lines.append(f"- **[Step {idx}]** 🤖 **Assistant Response**: {s.get('summary')}")
            if s.get("thinking_snippet"):
                lines.append(f"  - *Intent*: {s.get('thinking_snippet')}")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract compact retro context and friction points from transcript.")
    parser.add_argument("transcript_path", nargs="?", help="Path to transcript.jsonl (omitted to auto-detect latest)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON instead of markdown")
    parser.add_argument("--friction-only", action="store_true", help="Only show friction hotspots and related steps")
    args = parser.parse_args()

    target_path = args.transcript_path
    if not target_path:
        res = find_latest_transcript()
        if not res:
            sys.stderr.write("Error: No transcript found.\n")
            sys.exit(1)
        target_path, _ = res

    data = parse_transcript_compact(target_path)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_markdown_summary(data, friction_only=args.friction_only))


if __name__ == "__main__":
    main()
