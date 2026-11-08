#!/usr/bin/env python3
"""
Transcript Retro Context Extractor:
Deterministically extracts a compact, high-density timeline, multi-agent metrics landscape,
and friction hotspots across parent sessions and all descendant subagents.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set

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


def discover_subagents_from_parsed_objects(
    parsed_objects: List[Dict[str, Any]],
    parent_file_path: Path
) -> List[Dict[str, Any]]:
    """Discover subagents invoked via invoke_subagent tool calls and resolve their transcripts."""
    subagents = []
    n = len(parsed_objects)

    for i, item in enumerate(parsed_objects):
        tool_calls = item.get("tool_calls", [])
        for tc in tool_calls:
            if tc.get("name") == "invoke_subagent":
                args = tc.get("args", {})
                role = args.get("Role", "Subagent")
                if isinstance(role, str):
                    role = role.strip().strip('"').strip("'")
                
                prompt_raw = args.get("Prompt", "")
                if isinstance(prompt_raw, str):
                    prompt_raw = prompt_raw.strip().strip('"').strip("'")
                prompt_summary = prompt_raw.split("\n")[0][:120] if prompt_raw else ""

                step_idx = item.get("step_index", i)
                cid = None
                log_path = None

                # Look ahead for GENERIC tool response with conversationId / logAbsoluteUri
                for j in range(i + 1, min(i + 6, n)):
                    nxt = parsed_objects[j]
                    content = nxt.get("content", "")
                    if "conversationId" in content:
                        m_id = re.search(r'"conversationId":\s*"([^"]+)"', content)
                        if m_id:
                            cid = m_id.group(1)
                        m_uri = re.search(r'"logAbsoluteUri":\s*"file://([^"]+)"', content)
                        if m_uri:
                            log_path = m_uri.group(1)
                        break

                # Resolve fallback transcript path if not explicitly found in URI
                if cid and not log_path:
                    # Check relative to parent brain directory
                    try:
                        brain_dir = parent_file_path.parents[3]
                        candidate = brain_dir / cid / ".system_generated" / "logs" / "transcript.jsonl"
                        if candidate.is_file():
                            log_path = str(candidate)
                    except Exception:
                        pass

                    if not log_path:
                        candidate = Path.home() / ".gemini" / "antigravity" / "brain" / cid / ".system_generated" / "logs" / "transcript.jsonl"
                        if candidate.is_file():
                            log_path = str(candidate)

                if cid:
                    subagents.append({
                        "conversation_id": cid,
                        "role": role,
                        "step_index": step_idx,
                        "prompt_summary": prompt_summary,
                        "log_path": log_path,
                    })

    return subagents


def parse_transcript_compact(
    file_path: str,
    include_subagents: bool = True,
    max_depth: int = 2,
    visited_paths: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """Parse transcript and extract compact statistics, structured steps, and subagent traces."""
    p = Path(file_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Transcript file not found: {file_path}")

    if visited_paths is None:
        visited_paths = set()
    visited_paths.add(str(p))

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
                    elif t_name == "invoke_subagent":
                        sub_role = t_args.get("Role", "subagent")
                        if isinstance(sub_role, str):
                            sub_role = sub_role.strip().strip('"').strip("'")
                        arg_summary = f"Role: {sub_role}"
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
                        clean_err_snippet = tool_output.replace("\n", " ")[:160] if tool_output else "Unknown error"
                        friction_events.append({
                            "step_idx": step_idx,
                            "type": "TOOL_ERROR",
                            "summary": f"{t_name} failed: {arg_summary}",
                            "error_snippet": clean_err_snippet,
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

    # Subagents discovery & recursive extraction
    subagents_data: List[Dict[str, Any]] = []
    if include_subagents and max_depth > 0:
        discovered = discover_subagents_from_parsed_objects(parsed_objects, p)
        for sa_meta in discovered:
            sa_log = sa_meta.get("log_path")
            if sa_log and Path(sa_log).is_file() and sa_log not in visited_paths:
                try:
                    sa_parsed = parse_transcript_compact(
                        sa_log,
                        include_subagents=True,
                        max_depth=max_depth - 1,
                        visited_paths=visited_paths
                    )
                    sa_parsed["role"] = sa_meta["role"]
                    sa_parsed["invoked_at_step"] = sa_meta["step_index"]
                    sa_parsed["prompt_summary"] = sa_meta["prompt_summary"]
                    subagents_data.append(sa_parsed)
                except Exception as e:
                    subagents_data.append({
                        "role": sa_meta["role"],
                        "session_id": sa_meta["conversation_id"],
                        "file_path": sa_log,
                        "error": str(e),
                        "total_steps": 0,
                        "total_tool_calls": 0,
                        "friction_events": [],
                    })

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
        "subagents": subagents_data,
    }


def format_markdown_summary(
    data: Dict[str, Any],
    friction_only: bool = False,
    full_subagents: bool = False
) -> str:
    """Format parsed context into clean Markdown with hierarchical multi-agent layout."""
    lines = []
    subagents = data.get("subagents", [])
    is_multi_agent = bool(subagents)

    title_prefix = "Multi-Agent" if is_multi_agent else "Conversation"
    lines.append(f"# {title_prefix} Compact Timeline: `{data['session_id']}`")
    lines.append("")

    # 1. Overview Metrics
    lines.append("## Overview Metrics")
    lines.append(f"- **Primary Transcript**: `{data['file_path']}`")
    lines.append(f"- **Agent Harness**: `{data['agent_harness']}`")
    lines.append(f"- **Primary Duration**: {data['duration']}")
    lines.append(f"- **Primary Steps**: {data['total_steps']} | **Primary Tool Calls**: {data['total_tool_calls']}")

    if is_multi_agent:
        agg_steps = data["total_steps"] + sum(sa.get("total_steps", 0) for sa in subagents)
        agg_tool_calls = data["total_tool_calls"] + sum(sa.get("total_tool_calls", 0) for sa in subagents)
        agg_frictions = len(data["friction_events"]) + sum(len(sa.get("friction_events", [])) for sa in subagents)
        lines.append(f"- **Total Multi-Agent Steps**: **{agg_steps}**")
        lines.append(f"- **Total Multi-Agent Tool Calls**: **{agg_tool_calls}**")
        lines.append(f"- **Total Friction Hotspots**: **{agg_frictions}** (Parent: {len(data['friction_events'])}, Subagents: {agg_frictions - len(data['friction_events'])})")
        lines.append(f"- **Total Subagents Evaluated**: **{len(subagents)}**")
    else:
        lines.append(f"- **Friction Hotspots Detected**: {len(data['friction_events'])}")

    if data["tool_breakdown"]:
        breakdown = ", ".join(f"`{k}`: {v}" for k, v in sorted(data["tool_breakdown"].items(), key=lambda x: -x[1]))
        lines.append(f"- **Primary Tool Breakdown**: {breakdown}")
    lines.append("")

    # 2. Multi-Agent Metrics Landscape Table (if subagents exist)
    if is_multi_agent:
        lines.append("## Multi-Agent Metrics Landscape")
        lines.append("| Agent / Role | Level | Session ID | Steps | Tool Calls | Duration | Frictions | Top Tools |")
        lines.append("| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |")
        
        # Parent row
        p_top_tools = ", ".join(f"`{k}`: {v}" for k, v in sorted(data["tool_breakdown"].items(), key=lambda x: -x[1])[:3])
        lines.append(f"| **Parent (Orchestrator)** | Control Plane | `{data['session_id'][:8]}...` | {data['total_steps']} | {data['total_tool_calls']} | {data['duration']} | {len(data['friction_events'])} | {p_top_tools} |")

        for idx, sa in enumerate(subagents, 1):
            sa_role = sa.get("role", f"Subagent {idx}")
            sa_id = sa.get("session_id", "unknown")[:8] + "..."
            sa_steps = sa.get("total_steps", 0)
            sa_tools = sa.get("total_tool_calls", 0)
            sa_dur = sa.get("duration", "N/A")
            sa_frictions = len(sa.get("friction_events", []))
            sa_top_tools = ", ".join(f"`{k}`: {v}" for k, v in sorted(sa.get("tool_breakdown", {}).items(), key=lambda x: -x[1])[:3])
            lines.append(f"| **{sa_role}** | Subagent {idx} | `{sa_id}` | {sa_steps} | {sa_tools} | {sa_dur} | {sa_frictions} | {sa_top_tools} |")

        # Aggregate row
        lines.append(f"| **Multi-Agent Total** | **All Ecosystem** | **{len(subagents) + 1} Agents** | **{agg_steps}** | **{agg_tool_calls}** | **Wall Clock** | **{agg_frictions}** | **All Tools** |")
        lines.append("")

    # 3. Friction Hotspots Section
    lines.append("## Friction Hotspots (High-Priority Review Targets)")
    
    # Parent Frictions
    if data["friction_events"]:
        lines.append(f"### 🎯 Parent Session (Control Plane) [{len(data['friction_events'])} Events]")
        lines.append("| Step | Type | Description |")
        lines.append("| :--- | :--- | :--- |")
        for ev in data["friction_events"]:
            lines.append(f"| Step {ev['step_idx']} | `{ev['type']}` | {ev['summary']} |")
        lines.append("")
    elif not is_multi_agent:
        lines.append("> [!NOTE] No obvious friction events detected in parent session.")
        lines.append("")

    # Subagent Frictions
    if is_multi_agent:
        sa_friction_count = 0
        for sa in subagents:
            evs = sa.get("friction_events", [])
            if evs:
                sa_friction_count += len(evs)
                lines.append(f"### 🛠️ Subagent: **{sa.get('role', 'Specialist')}** (`{sa.get('session_id', '')}`) [{len(evs)} Events]")
                lines.append("| Step | Type | Description |")
                lines.append("| :--- | :--- | :--- |")
                for ev in evs:
                    lines.append(f"| Step {ev['step_idx']} | `{ev['type']}` | {ev['summary']} |")
                lines.append("")
        if sa_friction_count == 0:
            lines.append("> [!NOTE] No friction events detected across subagents.")
            lines.append("")

    # 4. Timeline Section
    lines.append("## Step-by-Step Compact Timeline")
    
    # Parent Timeline
    lines.append("### 👤 Parent Session Execution Timeline")
    for s in data["steps"]:
        idx = s.get("step_idx", "?")
        kind = s.get("kind", "")
        if friction_only and not s.get("is_error") and not s.get("is_bloated") and not s.get("is_correction"):
            continue

        if kind == "USER":
            corr = " [CORRECTION]" if s.get("is_correction") else ""
            lines.append(f"- **[Step {idx}]** 👤 USER{corr}: {s.get('summary')}")
        elif kind == "TOOL":
            err_badge = " ❌ [ERROR]" if s.get("is_error") else " ✅ [OK]"
            bloat_badge = f" ⚠️ [{s.get('output_length')} chars]" if s.get("is_bloated") else ""
            lines.append(f"- **[Step {idx}]** `{s.get('tool')}` ({s.get('args_summary')}){err_badge}{bloat_badge}")
            if s.get("is_error") and s.get("output_snippet"):
                clean_snippet = s.get("output_snippet").replace("\n", " ")[:140]
                lines.append(f"  - *Error Snippet*: `{clean_snippet}`")
        elif kind == "ASSISTANT":
            lines.append(f"- **[Step {idx}]** 🤖 Assistant: {s.get('summary')}")

    lines.append("")

    # Subagent Timelines
    if is_multi_agent:
        lines.append("### 🤖 Subagent Delegated Sessions Summary")
        for idx, sa in enumerate(subagents, 1):
            sa_role = sa.get("role", f"Subagent {idx}")
            lines.append(f"#### Subagent {idx}: {sa_role} (`{sa.get('session_id')}`)")
            lines.append(f"- **Invoked at Parent Step**: `[Step {sa.get('invoked_at_step', '?')}]`")
            lines.append(f"- **Objective**: {sa.get('prompt_summary', 'N/A')}")
            lines.append(f"- **Metrics**: {sa.get('total_steps', 0)} steps, {sa.get('total_tool_calls', 0)} tool calls, {len(sa.get('friction_events', []))} friction events")
            
            # If full_subagents flag is active, render subagent timeline
            if full_subagents and sa.get("steps"):
                lines.append("  *Detailed Timeline:*")
                for s in sa["steps"]:
                    s_idx = s.get("step_idx", "?")
                    s_kind = s.get("kind", "")
                    if friction_only and not s.get("is_error") and not s.get("is_bloated"):
                        continue
                    if s_kind == "TOOL":
                        badge = " ❌ [ERROR]" if s.get("is_error") else " ✅"
                        lines.append(f"  - `[Step {s_idx}]` `{s.get('tool')}` ({s.get('args_summary')}){badge}")
            lines.append("")

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract compact retro context, multi-agent metrics, and friction points from transcript.")
    parser.add_argument("transcript_path", nargs="?", help="Path to transcript.jsonl (omitted to auto-detect latest)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON instead of markdown")
    parser.add_argument("--friction-only", action="store_true", help="Only show friction hotspots and related steps")
    parser.add_argument("--no-subagents", action="store_true", help="Disable subagent automatic discovery and recursion")
    parser.add_argument("--full", action="store_true", help="Include full step-by-step timelines for all subagents")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum subagent recursion depth (default: 2)")
    args = parser.parse_args()

    target_path = args.transcript_path
    if not target_path:
        res = find_latest_transcript()
        if not res:
            sys.stderr.write("Error: No transcript found.\n")
            sys.exit(1)
        target_path, _ = res

    include_subagents = not args.no_subagents
    data = parse_transcript_compact(
        target_path,
        include_subagents=include_subagents,
        max_depth=args.max_depth
    )

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_markdown_summary(
            data,
            friction_only=args.friction_only,
            full_subagents=args.full
        ))


if __name__ == "__main__":
    main()
