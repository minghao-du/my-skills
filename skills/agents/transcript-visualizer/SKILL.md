---
name: transcript-visualizer
description: Review and visualize an agent conversation history as an interactive standalone web page.
disable-model-invocation: true
---

# Transcript Visualizer

Convert an agent conversation log into an interactive, zero-dependency standalone HTML report that visually highlights every step, tool invocation, and outcome.

## Inputs

The user may provide:
- **Transcript path** (optional): path to a `.jsonl` or directory containing the conversation history. If omitted, the locator script auto-detects the most recent session across Antigravity, Claude Code, Cline/Roo Code, or the current workspace.
- **Output path** (optional): destination `.html` file path (defaults to `./reports/agent-run-<session_id>.html`).
- **`--no-open` flag** (optional): suppress automatic browser launching.

## Steps

### 1. Resolve transcript location

Locate the target conversation transcript using the bundled locator:

```bash
python3 <skill-dir>/scripts/find_transcript.py [optional-path]
```

Done when: a valid transcript file path is resolved and verified on disk. If no transcript is found, report the search locations and ask the user for an explicit path before proceeding.

### 2. Generate interactive report

Run the deterministic visualizer script to parse events, extract heuristic summaries, and compile the self-contained HTML report:

```bash
python3 <skill-dir>/scripts/visualize.py <resolved-transcript-path> [-o <output-path>]
```

Done when:
- The target `.html` file is generated and verified non-empty (`test -s <output-path>`).
- The report includes total steps, tool counts, duration, and step cards with collapsible parameter/output details.
- The report opens in the default system browser (unless `--no-open` was specified).

### 3. Report completion

Output the generated HTML file path, session ID, total steps, and tool distribution summary in chat. Provide a clickable local file link (`file:///...`) for easy re-opening.

Done when: the artifact path and execution metrics are delivered to the user.
