---
name: reviewer-response
description: Revise paper and draft rebuttal for one reviewer/editor comment.
disable-model-invocation: true
---

Address one reviewer or editor comment: revise the paper first, then draft the rebuttal entry. One comment per invocation.

## Input

The user provides:

- One reviewer/editor comment (verbatim)
- The paper — full `.tex` source or the relevant sections, with indication of which part the comment targets
- The response letter file path to append the rebuttal entry to

## Steps

### 1. Understand the comment

Read the comment and the targeted paper section. Decompose the comment into every atomic point the reviewer raises — a comment that says "X, and also Y" is two points.

Done when every distinct point is identified.

### 2. Plan modifications

List every `.tex` location you intend to modify and what each modification does. Present this plan in chat before editing.

A single comment may require changes across multiple sections (a claim in the introduction inconsistent with results means both locations need revision). List all of them.

Done when every atomic point from step 1 has a planned modification or an explicit reason it needs no paper change.

### 3. Revise the paper

Edit the `.tex` files according to the plan. No change markers — git diff tracks what changed.

Done when all planned modifications are applied.

### 4. Write the rebuttal entry

Append a response to the response letter file. Read the existing file first to match its formatting conventions (LaTeX commands, sectioning, styling). If the file is empty or new, use a sensible default structure.

**Response structure** (English, address the reviewer as *you*):

1. **Gratitude** — thank you for the specific observation
2. **Substance** — address each point with what was done and why
3. **Changes** — list the exact paper locations modified (section, page, paragraph)

For tone calibration, read [`references/tone-guidelines.md`](references/tone-guidelines.md).
For example responses, read [`references/rebuttal-templates.md`](references/rebuttal-templates.md).

Done when the entry is appended, covers every atomic point, and each point references the corresponding modification from step 3.