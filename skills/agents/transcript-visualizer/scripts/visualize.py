#!/usr/bin/env python3
"""
Transcript Visualizer: Deterministic, zero-token parser and interactive
standalone HTML report generator for agent conversation transcripts.
"""

import os
import sys
import json
import re
import html
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Try to import find_transcript from same directory
try:
    from find_transcript import find_latest_transcript
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from find_transcript import find_latest_transcript


def clean_arg_value(val: Any) -> Any:
    """Strip redundant outer quotes from string values if present."""
    if isinstance(val, str):
        v = val.strip()
        if len(v) >= 2 and (
            (v.startswith('"') and v.endswith('"')) or
            (v.startswith("'") and v.endswith("'"))
        ):
            return v[1:-1]
        return v
    return val


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


def format_iso_timestamp(iso_str: Optional[str]) -> Tuple[str, Optional[datetime]]:
    """Format ISO timestamp into readable time and datetime object."""
    if not iso_str:
        return "-", None
    try:
        clean_str = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        return dt.strftime("%H:%M:%S"), dt
    except Exception:
        return iso_str[:19].replace("T", " "), None


def summarize_tool_call(name: str, args: Dict[str, Any]) -> Tuple[str, str, Dict[str, str]]:
    """
    Produce a concise 1-line heuristic summary and category for a tool call.
    Returns (summary, category, metadata_tags).
    """
    cleaned_args = {k: clean_arg_value(v) for k, v in args.items()}
    category = "tool"
    tags = {}

    tool_sum = cleaned_args.get("toolSummary")
    if tool_sum:
        summary = str(tool_sum).strip()
        if name in ("run_command", "bash", "execute_command"):
            category = "shell"
            cmd = cleaned_args.get("CommandLine", cleaned_args.get("command", ""))
            if cmd:
                tags["cmd"] = cmd[:60]
        elif name in ("read_file", "view_file", "cat"):
            category = "read"
            path = cleaned_args.get("Path", cleaned_args.get("file_path", ""))
            if path:
                tags["file"] = os.path.basename(path)
        elif name in ("write_file", "create_file"):
            category = "write"
            path = cleaned_args.get("Path", cleaned_args.get("file_path", ""))
            if path:
                tags["file"] = os.path.basename(path)
        elif name in ("edit_file", "patch_file"):
            category = "edit"
            path = cleaned_args.get("Path", cleaned_args.get("file_path", ""))
            if path:
                tags["file"] = os.path.basename(path)
        return summary, category, tags

    # Specific tool heuristics
    if name in ("run_command", "bash", "execute_command", "exec"):
        category = "shell"
        cmd = cleaned_args.get("CommandLine", cleaned_args.get("command", ""))
        summary = f"Run shell: {cmd[:55]}" if cmd else "Run shell command"
        if cmd:
            tags["cmd"] = cmd[:60]
    elif name in ("read_file", "view_file", "Read"):
        category = "read"
        p = cleaned_args.get("Path", cleaned_args.get("file_path", cleaned_args.get("path", "")))
        summary = f"Read: {os.path.basename(p)}" if p else "Read file"
        if p:
            tags["file"] = os.path.basename(p)
    elif name in ("write_file", "create_file", "Write"):
        category = "write"
        p = cleaned_args.get("Path", cleaned_args.get("file_path", cleaned_args.get("path", "")))
        summary = f"Create file: {os.path.basename(p)}" if p else "Write file"
        if p:
            tags["file"] = os.path.basename(p)
    elif name in ("edit_file", "patch_file", "Edit"):
        category = "edit"
        p = cleaned_args.get("Path", cleaned_args.get("file_path", cleaned_args.get("path", "")))
        summary = f"Edit: {os.path.basename(p)}" if p else "Edit file"
        if p:
            tags["file"] = os.path.basename(p)
    elif name in ("invoke_subagent", "dispatch_subagent"):
        category = "subagent"
        role = cleaned_args.get("Role", cleaned_args.get("TypeName", "subagent"))
        summary = f"Invoke subagent: {role}"
    elif name in ("ask_question", "ask_user"):
        category = "interact"
        summary = "Ask user clarification"
    elif name in ("search_web", "web_search"):
        category = "search"
        q = cleaned_args.get("query", "")
        summary = f"Web search: {q[:50]}"
    elif name in ("list_directory", "ls"):
        category = "read"
        summary = "List directory contents"
    elif name in ("schedule", "timer"):
        category = "system"
        summary = "Schedule task/timer"
    elif name in ("send_message",):
        category = "subagent"
        summary = f"Send message to {cleaned_args.get('Recipient', 'agent')}"
    else:
        clean_name = name.replace("mcp__", "").replace("_", " ").title()
        summary = f"Call {clean_name}"

    return summary, category, tags


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


def parse_transcript(file_path: str) -> Dict[str, Any]:
    """Parse transcript file (Antigravity, Claude Code, or generic)."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Transcript file not found: {file_path}")

    raw_lines = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                raw_lines.append(line_str)

    is_antigravity = False
    is_claude_code = False

    parsed_objects = []
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
    timestamps: List[datetime] = []
    tool_counts: Dict[str, int] = {}
    steps: List[Dict[str, Any]] = []

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
            time_display, dt = format_iso_timestamp(created_at)
            if dt:
                timestamps.append(dt)

            # Skip ephemeral system messages unless error
            if step_type == "EPHEMERAL_MESSAGE" and status == "DONE":
                i += 1
                continue

            content = item.get("content", "")
            thinking = item.get("thinking", "")
            tool_calls = item.get("tool_calls", [])

            # Case A: User input
            if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
                clean_content = clean_user_prompt(content)
                steps.append({
                    "index": step_idx,
                    "kind": "user",
                    "badge": "User Request",
                    "time": time_display,
                    "status": status,
                    "summary": clean_content.split("\n")[0][:120] if clean_content else "User Request",
                    "tags": {},
                    "output": "",
                    "details": clean_content,
                    "raw": item,
                })
                i += 1
                continue

            # Case B: Tool Calls
            if tool_calls:
                # Look ahead: if next step is GENERIC, that is the tool execution output!
                tool_output = ""
                if i + 1 < n:
                    next_item = parsed_objects[i + 1]
                    if next_item.get("type") == "GENERIC":
                        tool_output = next_item.get("content", "")
                        # Advance past the generic tool output step so it isn't rendered separately
                        i += 1

                for idx, call in enumerate(tool_calls):
                    t_name = call.get("name", "tool")
                    raw_args = call.get("args", {})
                    t_args = {k: clean_arg_value(v) for k, v in raw_args.items()}
                    tool_counts[t_name] = tool_counts.get(t_name, 0) + 1
                    summary, category, tags = summarize_tool_call(t_name, t_args)

                    details_payload = {
                        "tool": t_name,
                        "arguments": t_args,
                    }
                    if thinking and idx == 0:
                        details_payload["thinking_before_call"] = thinking.strip()

                    steps.append({
                        "index": step_idx if len(tool_calls) == 1 else f"{step_idx}.{idx+1}",
                        "kind": category,
                        "badge": f"{t_name}",
                        "time": time_display,
                        "status": status,
                        "summary": summary,
                        "tags": tags,
                        "output": tool_output.strip(),
                        "details": json.dumps(details_payload, indent=2, ensure_ascii=False),
                        "raw": call,
                    })
                i += 1
                continue

            # Case C: Standalone Thinking
            if thinking and not content:
                steps.append({
                    "index": step_idx,
                    "kind": "thinking",
                    "badge": "Thinking",
                    "time": time_display,
                    "status": status,
                    "summary": thinking.strip().split("\n")[0][:120],
                    "tags": {},
                    "output": "",
                    "details": thinking.strip(),
                    "raw": item,
                })
                i += 1
                continue

            # Case D: Standalone Output (GENERIC not consumed by tool, or PLANNER_RESPONSE text)
            if content:
                badge = "Agent Response" if step_type == "PLANNER_RESPONSE" else "System Output"
                kind = "response" if step_type == "PLANNER_RESPONSE" else "system"
                steps.append({
                    "index": step_idx,
                    "kind": kind,
                    "badge": badge,
                    "time": time_display,
                    "status": status,
                    "summary": content.strip().split("\n")[0][:120],
                    "tags": {},
                    "output": "",
                    "details": content.strip(),
                    "raw": item,
                })

            i += 1

    elif is_claude_code:
        for idx, item in enumerate(parsed_objects):
            msg = item.get("message", {})
            role = msg.get("role", item.get("type", ""))
            ts = item.get("timestamp")
            time_display, dt = format_iso_timestamp(ts)
            if dt:
                timestamps.append(dt)

            content = msg.get("content", "")

            if role == "user":
                if isinstance(content, str):
                    clean_content = clean_user_prompt(content)
                    if clean_content:
                        steps.append({
                            "index": idx + 1,
                            "kind": "user",
                            "badge": "User Request",
                            "time": time_display,
                            "status": "DONE",
                            "summary": clean_content.split("\n")[0][:120],
                            "tags": {},
                            "output": "",
                            "details": clean_content,
                            "raw": item,
                        })
            elif role == "assistant":
                if isinstance(content, list):
                    for b_idx, block in enumerate(content):
                        b_type = block.get("type", "")
                        if b_type == "tool_use":
                            t_name = block.get("name", "tool")
                            t_input = block.get("input", {})
                            tool_counts[t_name] = tool_counts.get(t_name, 0) + 1
                            summary, category, tags = summarize_tool_call(t_name, t_input)
                            steps.append({
                                "index": f"{idx+1}.{b_idx+1}",
                                "kind": category,
                                "badge": t_name,
                                "time": time_display,
                                "status": "DONE",
                                "summary": summary,
                                "tags": tags,
                                "output": "",
                                "details": json.dumps(block, indent=2, ensure_ascii=False),
                                "raw": block,
                            })
                        elif b_type == "text":
                            t_text = block.get("text", "").strip()
                            if t_text:
                                steps.append({
                                    "index": f"{idx+1}.{b_idx+1}",
                                    "kind": "response",
                                    "badge": "Agent Response",
                                    "time": time_display,
                                    "status": "DONE",
                                    "summary": t_text.split("\n")[0][:120],
                                    "tags": {},
                                    "output": "",
                                    "details": t_text,
                                    "raw": block,
                                })
                elif isinstance(content, str) and content.strip():
                    steps.append({
                        "index": idx + 1,
                        "kind": "response",
                        "badge": "Agent Response",
                        "time": time_display,
                        "status": "DONE",
                        "summary": content.strip().split("\n")[0][:120],
                        "tags": {},
                        "output": "",
                        "details": content.strip(),
                        "raw": item,
                    })

    # Duration calculation
    duration_str = "-"
    if timestamps and len(timestamps) > 1:
        start_t = min(timestamps)
        end_t = max(timestamps)
        diff_secs = int((end_t - start_t).total_seconds())
        mins, secs = divmod(diff_secs, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            duration_str = f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            duration_str = f"{mins}m {secs}s"
        else:
            duration_str = f"{secs}s"

    return {
        "session_id": session_id,
        "file_path": file_path,
        "total_steps": len(steps),
        "steps": steps,
        "tool_counts": tool_counts,
        "total_tools": sum(tool_counts.values()),
        "duration": duration_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def render_html(data: Dict[str, Any]) -> str:
    """Generate self-contained HTML page with zero external dependencies."""
    tool_counts_sorted = sorted(data["tool_counts"].items(), key=lambda x: x[1], reverse=True)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Run Trace: {html.escape(data['session_id'])}</title>
<style>
  :root {{
    --bg-page: #f8fafc;
    --bg-card: #ffffff;
    --bg-card-hover: #f1f5f9;
    --bg-detail: #f8fafc;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #64748b;
    --border: #e2e8f0;
    --accent: #4f46e5;
    --accent-light: #6366f1;
    --user-badge: #0284c7;
    --tool-badge: #d97706;
    --shell-badge: #db2777;
    --edit-badge: #16a34a;
    --read-badge: #0891b2;
    --thinking-badge: #9333ea;
    --response-badge: #0d9488;
    --subagent-badge: #c026d3;
    --error-badge: #dc2626;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background-color: var(--bg-page);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
    padding: 24px;
  }}

  .container {{
    max-width: 1060px;
    margin: 0 auto;
  }}

  header {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
  }}

  .header-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
  }}

  .title-group h1 {{
    font-size: 24px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 10px;
  }}

  .session-sub {{
    font-size: 13px;
    color: var(--text-muted);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    margin-top: 4px;
    word-break: break-all;
  }}

  .meta-pills {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}

  .pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 9999px;
    background: #f1f5f9;
    border: 1px solid var(--border);
    color: var(--text-secondary);
  }}

  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-top: 20px;
    border-top: 1px solid var(--border);
    padding-top: 20px;
  }}

  .stat-card {{
    background: #f8fafc;
    border-radius: 8px;
    padding: 12px 16px;
    border: 1px solid var(--border);
  }}

  .stat-val {{
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
  }}

  .stat-label {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-top: 2px;
  }}

  .tools-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 14px;
  }}

  .tool-tag {{
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 6px;
    background: #fef3c7;
    color: #b45309;
    border: 1px solid #fde68a;
    font-family: monospace;
    font-weight: 500;
  }}

  /* Controls */
  .controls-bar {{
    position: sticky;
    top: 12px;
    z-index: 50;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.04);
  }}

  .filter-tabs {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }}

  .btn-filter {{
    background: #ffffff;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }}

  .btn-filter:hover {{
    background: #f1f5f9;
    color: var(--text-primary);
  }}

  .btn-filter.active {{
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
  }}

  .search-box {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .search-input {{
    background: #ffffff;
    border: 1px solid #cbd5e1;
    color: var(--text-primary);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    outline: none;
    width: 200px;
    transition: width 0.2s, border-color 0.2s;
  }}

  .search-input:focus {{
    border-color: var(--accent);
    width: 260px;
  }}

  .btn-action {{
    background: #ffffff;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
  }}
  .btn-action:hover {{
    color: var(--text-primary);
    background: #f1f5f9;
  }}

  /* Step Timeline */
  .timeline {{
    position: relative;
    padding-left: 20px;
  }}

  .timeline::before {{
    content: "";
    position: absolute;
    left: 7px;
    top: 10px;
    bottom: 20px;
    width: 2px;
    background: #cbd5e1;
  }}

  .step-node {{
    position: relative;
    margin-bottom: 16px;
    transition: opacity 0.2s;
  }}

  .step-marker {{
    position: absolute;
    left: -20px;
    top: 16px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #ffffff;
    border: 2px solid var(--text-muted);
    z-index: 2;
  }}

  .step-node[data-kind="user"] .step-marker {{ border-color: var(--user-badge); background: #e0f2fe; }}
  .step-node[data-kind="shell"] .step-marker {{ border-color: var(--shell-badge); background: #fce7f3; }}
  .step-node[data-kind="edit"] .step-marker {{ border-color: var(--edit-badge); background: #dcfce7; }}
  .step-node[data-kind="write"] .step-marker {{ border-color: var(--edit-badge); background: #dcfce7; }}
  .step-node[data-kind="read"] .step-marker {{ border-color: var(--read-badge); background: #cffafe; }}
  .step-node[data-kind="subagent"] .step-marker {{ border-color: var(--subagent-badge); background: #fae8ff; }}
  .step-node[data-kind="response"] .step-marker {{ border-color: var(--response-badge); background: #ccfbf1; }}
  .step-node[data-kind="thinking"] .step-marker {{ border-color: var(--thinking-badge); background: #f3e8ff; }}

  .step-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    transition: border-color 0.15s, box-shadow 0.15s;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  }}

  .step-card:hover {{
    border-color: #cbd5e1;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  }}

  .step-header {{
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    user-select: none;
    gap: 12px;
  }}

  .step-header-left {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    flex: 1;
  }}

  .step-index {{
    font-size: 12px;
    font-weight: 700;
    color: var(--text-muted);
    font-family: monospace;
    min-width: 24px;
  }}

  .kind-badge {{
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  .badge-user {{ background: #e0f2fe; color: #0284c7; border: 1px solid #bae6fd; }}
  .badge-shell {{ background: #fce7f3; color: #be185d; border: 1px solid #fbcfe8; }}
  .badge-edit, .badge-write {{ background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }}
  .badge-read {{ background: #cffafe; color: #0891b2; border: 1px solid #a5f3fc; }}
  .badge-tool {{ background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }}
  .badge-subagent {{ background: #fae8ff; color: #a21caf; border: 1px solid #f5d0fe; }}
  .badge-thinking {{ background: #f3e8ff; color: #7e22ce; border: 1px solid #e9d5ff; }}
  .badge-response {{ background: #ccfbf1; color: #0f766e; border: 1px solid #99f6e4; }}

  .step-summary {{
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }}

  .step-header-right {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .step-time {{
    font-size: 11px;
    color: var(--text-muted);
    font-family: monospace;
  }}

  .toggle-icon {{
    font-size: 12px;
    color: var(--text-muted);
    transition: transform 0.2s;
  }}

  .step-node.open .toggle-icon {{
    transform: rotate(90deg);
  }}

  /* Step Details */
  .step-details {{
    display: none;
    padding: 0 16px 16px 16px;
    border-top: 1px solid var(--border);
    background: #f8fafc;
  }}

  .step-node.open .step-details {{
    display: block;
  }}

  .section-label {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-top: 12px;
    margin-bottom: 4px;
  }}

  .details-box {{
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 12px;
    color: #1e293b;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 400px;
    overflow-y: auto;
  }}

  .output-box {{
    border-color: #bae6fd;
    background: #f0f9ff;
    color: #0369a1;
  }}

  .step-tags {{
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }}

  .param-tag {{
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
    font-family: monospace;
  }}

  .empty-state {{
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="header-top">
      <div class="title-group">
        <h1>Agent Run Trace</h1>
        <div class="session-sub">{html.escape(data['file_path'])}</div>
      </div>
      <div class="meta-pills">
        <span class="pill">⏱ Duration: <strong>{html.escape(data['duration'])}</strong></span>
        <span class="pill">🕒 Generated: <strong>{html.escape(data['generated_at'])}</strong></span>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-val">{data['total_steps']}</div>
        <div class="stat-label">Total Steps</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{data['total_tools']}</div>
        <div class="stat-label">Tool Invocations</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{len([s for s in data['steps'] if s['kind'] == 'user'])}</div>
        <div class="stat-label">User Prompts</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{len([s for s in data['steps'] if s['kind'] == 'response'])}</div>
        <div class="stat-label">Responses</div>
      </div>
    </div>

    <div class="tools-bar">
      {" ".join(f'<span class="tool-tag">{html.escape(name)}: {count}</span>' for name, count in tool_counts_sorted)}
    </div>
  </header>

  <div class="controls-bar">
    <div class="filter-tabs">
      <button class="btn-filter active" data-filter="all">All ({data['total_steps']})</button>
      <button class="btn-filter" data-filter="tool">Tools ({data['total_tools']})</button>
      <button class="btn-filter" data-filter="user">User</button>
      <button class="btn-filter" data-filter="response">Responses</button>
      <button class="btn-filter" data-filter="thinking">Thinking</button>
    </div>

    <div class="search-box">
      <input type="text" id="searchInput" class="search-input" placeholder="Filter steps / tools...">
      <button class="btn-action" id="btnToggleAll">Expand All</button>
    </div>
  </div>

  <div class="timeline" id="timelineContainer">
"""

    for step in data["steps"]:
        kind = step["kind"]
        badge_class = f"badge-{kind}" if f"badge-{kind}" in (
            "badge-user", "badge-shell", "badge-edit", "badge-write", "badge-read",
            "badge-tool", "badge-subagent", "badge-thinking", "badge-response"
        ) else "badge-tool"

        tags_html = ""
        if step.get("tags"):
            tag_spans = []
            for k, v in step["tags"].items():
                tag_spans.append(f'<span class="param-tag">{html.escape(k)}: {html.escape(str(v))}</span>')
            tags_html = f'<div class="step-tags">{" ".join(tag_spans)}</div>'

        output_block = ""
        if step.get("output"):
            output_block = f"""
          <div class="section-label">Execution Output</div>
          <pre class="details-box output-box">{html.escape(step['output'])}</pre>
"""

        details_block = ""
        if step.get("details"):
            label = "Input / Parameters" if kind in ("tool", "shell", "read", "write", "edit", "subagent") else "Content"
            details_block = f"""
          <div class="section-label">{label}</div>
          <pre class="details-box">{html.escape(step['details'])}</pre>
"""

        search_content = f"{step['summary']} {step.get('details', '')} {step.get('output', '')}".lower()

        html_template += f"""
    <div class="step-node" data-kind="{kind}" data-text="{html.escape(search_content)}">
      <div class="step-marker"></div>
      <div class="step-card">
        <div class="step-header">
          <div class="step-header-left">
            <span class="step-index">#{step['index']}</span>
            <span class="kind-badge {badge_class}">{html.escape(step['badge'])}</span>
            <span class="step-summary">{html.escape(step['summary'])}</span>
            {tags_html}
          </div>
          <div class="step-header-right">
            <span class="step-time">{html.escape(step['time'])}</span>
            <span class="toggle-icon">▶</span>
          </div>
        </div>
        <div class="step-details">
          {output_block}
          {details_block}
        </div>
      </div>
    </div>
"""

    html_template += """
    <div class="empty-state" id="emptyState" style="display: none;">No matching steps found.</div>
  </div>
</div>

<script>
  // Step expansion toggling
  document.querySelectorAll('.step-header').forEach(header => {
    header.addEventListener('click', () => {
      const node = header.closest('.step-node');
      node.classList.toggle('open');
    });
  });

  // Expand / Collapse all
  let allExpanded = false;
  const toggleBtn = document.getElementById('btnToggleAll');
  toggleBtn.addEventListener('click', () => {
    allExpanded = !allExpanded;
    document.querySelectorAll('.step-node').forEach(node => {
      if (allExpanded) node.classList.add('open');
      else node.classList.remove('open');
    });
    toggleBtn.textContent = allExpanded ? 'Collapse All' : 'Expand All';
  });

  // Filter tabs
  const filterBtns = document.querySelectorAll('.btn-filter');
  let currentFilter = 'all';

  function applyFilters() {
    const query = document.getElementById('searchInput').value.trim().toLowerCase();
    const nodes = document.querySelectorAll('.step-node');
    let visibleCount = 0;

    nodes.forEach(node => {
      const kind = node.getAttribute('data-kind');
      const text = node.getAttribute('data-text');

      let matchesFilter = (currentFilter === 'all');
      if (currentFilter === 'tool') {
        matchesFilter = ['tool', 'shell', 'read', 'write', 'edit', 'subagent', 'search', 'interact'].includes(kind);
      } else if (currentFilter === kind) {
        matchesFilter = true;
      }

      let matchesSearch = !query || text.includes(query);

      if (matchesFilter && matchesSearch) {
        node.style.display = 'block';
        visibleCount++;
      } else {
        node.style.display = 'none';
      }
    });

    document.getElementById('emptyState').style.display = visibleCount === 0 ? 'block' : 'none';
  }

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.getAttribute('data-filter');
      applyFilters();
    });
  });

  // Search input filter
  document.getElementById('searchInput').addEventListener('input', applyFilters);
</script>
</body>
</html>
"""
    return html_template


def main():
    explicit_path = None
    output_path = None
    auto_open = True

    # Parse arguments
    args = sys.argv[1:]
    idx = 0
    while idx < len(args):
        arg = args[idx]
        if arg == "--no-open":
            auto_open = False
        elif arg in ("-o", "--output"):
            idx += 1
            if idx < len(args):
                output_path = args[idx]
        elif not explicit_path:
            explicit_path = arg
        idx += 1

    result = find_latest_transcript(explicit_path)
    if not result:
        sys.stderr.write("Error: Could not find any agent transcript file.\n")
        sys.exit(1)

    transcript_path, agent_type = result
    print(f"[*] Parsing transcript ({agent_type}): {transcript_path}")

    parsed_data = parse_transcript(transcript_path)
    rendered_html = render_html(parsed_data)

    if not output_path:
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        safe_session_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', parsed_data["session_id"][:12])
        output_path = str(reports_dir / f"agent-run-{safe_session_id}.html")

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print(f"[✓] Trace report generated: {out_file} ({parsed_data['total_steps']} steps)")

    if auto_open:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(out_file)], check=False)
            elif sys.platform.startswith("linux"):
                subprocess.run(["xdg-open", str(out_file)], check=False)
            elif sys.platform in ("win32", "cygwin"):
                os.startfile(str(out_file))
        except Exception as e:
            print(f"[!] Could not auto-open browser: {e}")


if __name__ == "__main__":
    main()
