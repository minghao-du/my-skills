---
name: transcript-retro
description: Retrospectively analyze an agent conversation transcript to extract improvements for existing skills, AGENTS.md, new skills, scripts, and context hygiene.
disable-model-invocation: true
---

# Transcript Retro

Conduct an objective, evidence-based postmortem on an agent conversation transcript. Extract actionable improvements across existing skills, workspace conventions (`AGENTS.md`), new skill opportunities, deterministic tooling, context hygiene, and user prompt ergonomics.

## Execution Topology (Zero Context Contamination)

Running retro inside a heavily polluted conversation burns tokens and introduces hindsight bias. To preserve zero-contamination and save tokens:

- **Primary Mode (Subagent Delegation)**: When invoked inside an active conversation, the parent agent acts as a thin dispatcher. It resolves the transcript and dispatches a fresh, isolated subagent (`Role: Transcript Auditor`). The subagent executes with zero parent context, writes the report, and reports back.
- **Direct Mode**: When invoked in a clean session or in harnesses lacking subagent support, the agent executes the audit directly.

---

## Inputs

- **Transcript path** (optional): path to a `transcript.jsonl` or directory. If omitted, the locator auto-detects the target session.
- **`--offset N`** (optional): analyze the N-th previous session (`--offset 1` for previous session, etc.).
- **Output path** (optional): destination `.md` file path (defaults to `./reports/retro-<session_id>.md`).
- **`--friction-only`** (optional): focus review strictly on steps where errors, bloat, or user corrections occurred.

---

## Workflow

### 1. Resolve Target Transcript

Run the locator to find the target transcript:

```bash
python3 <skill-dir>/scripts/find_transcript.py [optional-path] [--offset N]
```

Done when: A valid transcript file path is verified on disk. If multiple candidates exist or the path is ambiguous, run with `--list` to inspect recent sessions.

### 2. Determine Dispatch Path

- **If `invoke_subagent` (or equivalent child agent tool) is available**:
  Dispatch a dedicated subagent to perform the audit in an isolated context window. Do NOT load or analyze the transcript in the parent conversation.
  
  Call `invoke_subagent` with:
  - **TypeName**: `"self"` (or `"research"`)
  - **Role**: `"Transcript Auditor"`
  - **Prompt**:
    ```text
    You are an objective, third-party Transcript Auditor. Perform a retrospective review of the conversation transcript at:
    <resolved-transcript-path>

    Instructions:
    1. Run: python3 <skill-dir>/scripts/extract_retro_context.py "<resolved-transcript-path>"
    2. Deep-dive into the 6 core review dimensions:
       - 1. Existing Skills (premature completion, sprawl, sediment, fuzzy completion criteria)
       - 2. AGENTS.md & Workspace Conventions (positive rules to prevent repeated stumbling)
       - 3. New Skills Induction (repeatable procedures meeting skill criteria)
       - 4. Deterministic Scripts & Tooling (fragile bash/python logic to harden into scripts/)
       - 5. Context Hygiene (detecting >10KB dumps or missing progressive disclosure)
       - 6. User Prompt & Clarification Ergonomics (ambiguity or missed agent confirmations)
    3. Write the structured report to: <output-path> (default: ./reports/retro-<session_id>.md)
    4. Reply with an executive summary, top 3 prioritized action items, and the file link.
    ```
  Done when: Subagent finishes and replies with the report path and summary. Skip to [Step 5](#5-deliver-executive-summary).

- **If running directly (subagent tool unavailable or already in fresh session)**:
  Proceed through Steps 3 and 4 locally.

### 3. Extract Timeline & Friction Hotspots (Direct Mode)

Run the deterministic extractor to review the run with zero context bloat:

```bash
python3 <skill-dir>/scripts/extract_retro_context.py <resolved-transcript-path> [--friction-only]
```

Done when: Session metrics (steps, duration, tool breakdown) and friction events (`TOOL_ERROR`, `CONTEXT_BLOAT`, `USER_STEERING`) are loaded.

### 4. Deep-Dive Across the 6 Dimensions & Write Report (Direct Mode)

Examine the conversation log against the 6 pillars. Cite specific `[Step N]` evidence for every observation:

1. **Existing Skills Audit**:
   - Did an active skill suffer **premature completion** (stopping before genuine completion), **sprawl** (unfocused, wandering steps), or **sediment** (outdated rules causing friction)?
   - Were completion criteria checkable and binary, or fuzzy?
2. **AGENTS.md & Workspace Rules**:
   - Did the agent repeatedly fumble conventions (build commands, directory locations, testing tools)?
   - What positive, actionable constraint should be added to `AGENTS.md`?
3. **New Skills Induction**:
   - Did the agent perform a multi-step, repeatable procedure manually?
   - Does it meet splitting criteria: a clear sequence with a distinct leading word and checkable criteria?
4. **Deterministic Tooling & Scripts Extraction**:
   - Did the agent improvise complex, fragile bash or python one-liners across turns?
   - Should this logic be hardened into a deterministic script under `scripts/`?
5. **Context Hygiene & Progressive Disclosure**:
   - Did any step dump giant files (>10KB) or raw logs directly into context?
   - Could progressive disclosure (grep, summarizing script, paginated read) have kept the context tight?
6. **User Prompt Ergonomics & Clarification**:
   - Was the user's prompt ambiguous or overloaded?
   - Did the agent assume answers to critical forks instead of pausing to clarify (`ask_question`)?

Write the markdown report to `./reports/retro-<session_id>.md` using the [Report Template](#report-template).

Done when: The report file is written, verified non-empty (`test -s <output-path>`), and contains concrete code/diff proposals.

### 5. Deliver Executive Summary

Output a concise summary in chat:
- Key metrics (session ID, duration, steps, tool breakdown).
- Top 3 highest-leverage **Action Items** (with concrete files to touch).
- Clickable local link to the full report (`file:///...`).

Done when: The artifact path and high-priority recommendations are presented in chat.

---

## Report Template

Use this format for `./reports/retro-<session_id>.md`:

```markdown
# Agent Conversation Retrospective: `<session_id>`

- **Transcript**: `<transcript_path>`
- **Harness**: `<antigravity | claude-code | cline>`
- **Steps**: `<total_steps>` | **Tool Calls**: `<total_tool_calls>` | **Duration**: `<duration>`

---

## Executive Summary
<2-3 sentences summarizing session intent, outcome, and primary friction observed>

## Friction Hotspots
| Step | Type | What Happened | Root Cause |
| :--- | :--- | :--- | :--- |
| Step X | Tool Error / Churn / Bloat | ... | ... |

---

## Actionable Recommendations (6-Dimension Review)

### 1. Existing Skills
- **Skill**: `<skill-name>` (or "None")
- **Issue**: <premature completion / sprawl / sediment / fuzzy criteria>
- **Proposed Edit**:
  ```diff
  ...
  ```

### 2. AGENTS.md & Workspace Conventions
- **Observation**: <where the agent fumbled conventions>
- **Proposed Rule**:
  > [!TIP]
  > <Clear positive rule statement to add to AGENTS.md>

### 3. New Skills Opportunities
- **Proposed Name**: `<skill-name>`
- **Trigger**: <When to invoke>
- **Core Sequence**: <Summary of steps>

### 4. Deterministic Scripts & Tooling
- **Candidate Logic**: <ad-hoc command or repeated logic>
- **Proposed Script**: `scripts/<script_name>.py`

### 5. Context Hygiene & Progressive Disclosure
- **Hotspots**: <Steps with large payloads>
- **Remediation**: <Filtering, truncation flags, or intermediate summary scripts>

### 6. User Prompt & Clarification Ergonomics
- **Observation**: <Ambiguities or missed clarifications>
- **Takeaway**: <Recommended prompt structure or agent pausing checkpoint>

---

## Prioritized Action Checklist
- [ ] **P0**: <Most critical fix>
- [ ] **P1**: <Second priority>
- [ ] **P2**: <Long-term improvement>
```
