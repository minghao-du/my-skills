---
name: teaching-slides
description: Distill reference materials into minimal, vector-rich Marp teaching slides.
disable-model-invocation: true
---

**Distill** dense reference material into clean Marp slides. The user provides detailed input — text, code, file paths, images — and specifies the target language. The user may also specify a target page count and output file path.

## Steps

### 1. Scaffold

Read all reference material the user provides. Design the **teaching arc**: what the audience starts not knowing, and the sequence of revelations that builds understanding — not the order the material was given, but the order that teaches.

Present a numbered outline. Each line states:
- the slide's core teaching point
- the planned visual form: `mermaid`, `svg`, `code`, or `text`

Include target language and estimated slide count. If the user specified a page count, honor it.

**Done when**: the user explicitly approves the outline.

### 2. Generate

Produce the full Marp Markdown file following the approved scaffold.

Each slide carries:
- One teaching point, expressed as a visual whenever a visual teaches faster than text.
- Speaker notes (`<!-- ... -->`) with what the presenter says aloud: detailed explanation, transition to the next slide, anticipated questions.

Apply the base CSS from [`theme.css`](theme.css) in the frontmatter `style` block.

Write the `.md` file to the user-specified path (default: working directory), named descriptively (e.g. `intro-to-transformers.md`).

**Done when**: the file is written with valid Marp structure — frontmatter has `marp: true`, slides separated by `---`, no malformed fenced blocks.

## Visuals

Prefer vectors, in this order:

1. **Mermaid** — flowcharts, sequence diagrams, state diagrams, class diagrams, ER diagrams. First choice for relational or procedural content.
2. **Inline SVG** — spatial layouts, custom graphics, anything Mermaid cannot express.
3. **Bitmap** — only for inherently photographic content. When a user-provided bitmap can be redrawn as vector, redraw it. Discard or adapt user images freely when they serve the teaching goal poorly.

## Code

Choose the form that teaches fastest:

- **Key fragment** with annotations — when real syntax matters.
- **Pseudocode** — when the algorithm matters more than the language.
- **Diagram** — when control flow or data flow is the point.

Omit code entirely when a diagram or plain statement teaches the concept better.

## Marp format

Frontmatter and slide structure:

```
---
marp: true
theme: default
paginate: true
style: |
  /* paste theme.css contents here */
---

# Slide title

Content

<!-- Speaker notes go here -->

---

# Next slide
```

- `---` alone on a line separates slides.
- `<!-- ... -->` after slide content becomes speaker notes (visible only in presenter view).
- Mermaid: fenced ` ```mermaid ``` ` blocks render as diagrams.
- Inline `<svg>` elements render directly in slide content.
