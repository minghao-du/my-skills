---
name: transcript-retro
description: Retrospectively analyze an agent conversation transcript to extract improvements for existing skills, AGENTS.md, new skills, scripts, and context hygiene.
disable-model-invocation: true
---

# Transcript Retro

Conduct an evidence-based postmortem on an agent conversation transcript. Extract actionable improvements across existing skills, workspace conventions (`AGENTS.md`), new skill opportunities, deterministic tooling, context hygiene, and user prompt ergonomics.

## Inputs

- **Transcript path** (optional): path to a `transcript.jsonl` or directory containing the conversation history. If omitted, the locator script auto-detects the most recent session across Antigravity, Claude Code, Cline/Roo Code, or local workspace.
- **Output path** (optional): destination `.md` file path (defaults to `./reports/retro-<session_id>.md`).
- **`--friction-only`** (optional): focus review strictly on steps where errors, bloat, or user corrections occurred.

---

## Steps

### 1. Resolve transcript location

Locate the target conversation transcript using the bundled locator:

```bash
python3 <skill-dir>/scripts/find_transcript.py [optional-path]
```

Done when: A valid transcript file path is resolved and verified on disk. If unresolvable, list searched directories and ask the user for an explicit path before proceeding.

### 2. Extract compact timeline & friction hotspots

Run the deterministic extractor to inspect the run without blowing up your context window:

```bash
python3 <skill-dir>/scripts/extract_retro_context.py <resolved-transcript-path>
```

Done when:
- Session overview metrics (total steps, duration, tool distribution) are established.
- All friction hotspots (tool errors, user steering turns, context bloat) are identified by step index.

### 3. Deep-dive across the 6 review dimensions

Examine the conversation log against the 6 core pillars below. For every observation, cite the specific `[Step N]` evidence.

1. **Existing Skills Audit**:
   - Was an active skill triggered? Did it experience **premature completion** (stopping before genuine completion), **sprawl** (unfocused, wandering steps), or **sediment** (outdated rules causing friction)?
   - Were completion criteria checkable and binary, or fuzzy?
   - Did the skill's description or leading words trigger cleanly, or did the agent miss it?
2. **AGENTS.md & Workspace Rules**:
   - Did the agent repeatedly fumble project conventions (build commands, directory locations, testing tools)?
   - What positive, actionable constraint should be added to `AGENTS.md` to prevent this failure?
3. **New Skills Induction**:
   - Did the agent manually perform a multi-step, repeatable procedure (e.g. specialized debugging, data migration, domain setup)?
   - Does it meet splitting criteria: a clear sequence of steps with a distinct leading word and checkable completion criteria?
4. **Deterministic Tooling & Scripts Extraction**:
   - Did the agent improvise complex, fragile bash or python one-liners across turns?
   - Should this logic be hardened into a deterministic script under `scripts/`?
5. **Context Hygiene & Progressive Disclosure**:
   - Did any step dump giant files (>10KB) or raw logs directly into context?
   - Could progressive disclosure (grep, summarizing script, paginated read) have kept the context tight?
6. **User Prompt Ergonomics & Clarification**:
   - Was the user's prompt ambiguous or overloaded?
   - Did the agent assume answers to critical forks instead of pausing to ask (`ask_question`)?

Done when: Each of the 6 dimensions has at least one concrete finding backed by step evidence (or an explicit statement explaining why no changes are warranted).

### 4. Write structured retro report

Write the final retrospective artifact to `./reports/retro-<session_id>.md` (create parent directory if missing) using the template in [Report Template](#report-template).

Done when: The markdown file is written, verified non-empty (`test -s <output-path>`), and contains concrete code/diff proposals for suggested changes.

### 5. Deliver executive summary in chat

Output a concise summary in chat:
- Key metrics (session ID, duration, steps, tool breakdown).
- Top 3 highest-leverage **Action Items** (with concrete files to touch).
- Clickable link to the full report file (`file:///...`).

Done when: The artifact path and high-priority recommendations are presented to the user.

---

## Report Template

Use this format when writing `reports/retro-<session_id>.md`:

```markdown
# Agent Conversation Retrospective: `<session_id>`

- **Transcript**: `<transcript_path>`
- **Harness**: `<antigravity | claude-code | cline>`
- **Steps**: `<total_steps>` | **Tool Calls**: `<total_tool_calls>` | **Duration**: `<duration>`

---

## Executive Summary
<2-3 sentences summarizing the session intent, outcome, and primary friction observed>

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
