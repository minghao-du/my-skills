---
name: research-codebase-architecture
description: Design, audit, or refactor a scientific research project into a reproducible stage-driven pipeline. Use when the user wants to structure a research codebase, reorganize a cluttered scientific project, create a single-command research pipeline, or audit data-to-figure workflows.
---

# Research Codebase Architecture

Structure scientific research projects for **single-command reproducibility**, clean data flow, and transparent agent navigation without the overhead of building a public Python package.

This skill is governed by five **leading words**:

- **stage-contract**: Every pipeline step in `scripts/` exposes a self-contained 4-part card (`README.md`) declaring its Purpose, Inputs, Run Command, and Outputs.
- **data-immutability**: `data/` holds only read-only raw external inputs; all generated artifacts land in `output/`.
- **summary-receipt**: Each stage writes a lightweight, text-only markdown summary into `summary/` (tracked in Git), recording execution metrics and indexing output files for agents and researchers.
- **quarantine**: All exploratory scripts, scratchpads, notebooks, and presentation drafts live exclusively in `_ignore/` (gitignored), never polluting the root or pipeline stages.
- **single-command-reproducibility**: The master runner (`run_pipeline.py`) can execute any single stage, a stage range, or regenerate the entire project end-to-end (`--all`).

---

## Canonical Layout

```text
<project-root>/
├── data/                      # [Read-only] Immutable raw inputs (genomes, trees, raw tables)
├── scripts/                   # [Tracked] Pipeline stages in strict temporal execution order
│   ├── 01_download/           # Stage 01: fetch raw data, verify checksums
│   │   ├── run.py             # Single stage entrypoint
│   │   └── README.md          # Stage contract card
│   ├── 02_preprocess/         # Stage 02: clean, filter, align, feature extraction
│   ├── 03_models/             # Stage 03: model inference (Evo2, ESM, neural nets)
│   │   ├── run.py
│   │   ├── submit.sbatch      # Optional Slurm cluster submission wrapper
│   │   └── README.md
│   ├── 04_analysis/           # Stage 04: statistical testing, regressions, metrics
│   ├── 05_figures/            # Stage 05: publication-ready plots and tables
│   └── utils/                 # Shared pure functions (no stage-specific state)
├── output/                    # [Gitignored] Generated data artifacts, mirrored by stage
│   ├── 01_download/
│   ├── 02_preprocess/
│   ├── 03_models/
│   ├── 04_analysis/
│   └── 05_figures/
├── summary/                   # [Tracked] Text-only run summaries & result index for Agent & Human
│   ├── 01_download.md         # Ingestion counts, sample manifests, integrity checks
│   ├── 02_preprocess.md       # Filtering attrition, matrix dimensions, missingness
│   ├── 03_models.md           # Model parameters, loss, perplexity, inference durations
│   ├── 04_analysis.md         # Key coefficients, p-values, hypothesis conclusions
│   └── 05_figures.md          # Index of generated figures with captions & output paths
├── _ignore/                   # [Gitignored] Quarantine for play_*, drafts, PPTX, scratch notebooks
├── run_pipeline.py            # Master pipeline orchestrator (CLI: --stage, --from/--to, --all)
├── environment.yml            # Environment dependencies (Conda / Mamba / uv / Pip)
└── README.md                  # Project overview, research hypothesis, quickstart command
```

---

## Operating Modes

Choose the branch matching the user's need:

- **Branch A: Scaffold New Research Project**: Set up the skeleton, master runner, templates, and initial READMEs from scratch.
- **Branch B: Audit & Refactor Existing Project**: Diagnose an existing cluttered repository (e.g. ad-hoc `task.sh`, loose `play_*` folders, unindexed outputs) and systematically migrate it to the canonical architecture.

---

### Branch A: Scaffolding a New Project

Execute these steps in sequence:

1. **Initialize Directory Skeleton**
   Create the canonical tree: `data/`, `scripts/`, `output/`, `summary/`, `_ignore/`.
   *Completion criterion*: All 5 top-level directories exist, and `.gitignore` ignores `output/` and `_ignore/`.

2. **Generate Stage Directories & Contracts**
   Under `scripts/`, create numbered stage directories (defaulting to `01_download`, `02_preprocess`, `03_models`, `04_analysis`, `05_figures`). In each stage folder, write a standard `README.md` using the 4-part contract from [TEMPLATES.md](TEMPLATES.md#stage-readmemd-template).
   *Completion criterion*: Every stage directory contains an initial `run.py` (or main execution script) and a non-empty `README.md`.

3. **Install Master Pipeline Runner**
   Write `run_pipeline.py` in the project root based on [TEMPLATES.md](TEMPLATES.md#master-pipeline-runner-run_pipelinepy).
   *Completion criterion*: Running `python run_pipeline.py --help` exits with code 0 and exposes `--stage`, `--from`, `--to`, and `--all`.

4. **Initialize Summary Index**
   Under `summary/`, create initial markdown files matching each stage number using the template in [TEMPLATES.md](TEMPLATES.md#summary-template).
   *Completion criterion*: Each `summary/0X_*.md` file exists and is tracked by Git.

---

### Branch B: Auditing & Refactoring an Existing Project

Follow the systematic 5-step migration loop (detailed in [AUDIT_CHECKLIST.md](AUDIT_CHECKLIST.md)):

1. **Inventory & Triage**
   - Identify all live execution scripts (e.g., scan monster shell scripts like `task.sh` or loose Python files).
   - Flag all exploratory folders (`play_*`, `tmp_*`, ad-hoc test scripts, presentations `.pptx`, test images).
   *Completion criterion*: A written inventory distinguishing live pipeline code from exploratory scratch work.

2. **Quarantine Pass**
   Move all exploratory scripts, throwaway notebooks, and presentation materials directly into `_ignore/`.
   *Completion criterion*: Root directory contains no loose notebooks, experimental `play_*` directories, or binary assets.

3. **Data & Output Separation**
   - Audit all file paths in existing scripts.
   - Separate immutable source inputs into `data/`.
   - Redirect all script write targets to `output/<stage_number>/`.
   *Completion criterion*: No script modifies files inside `data/`, and all intermediate/final outputs write strictly to `output/`.

4. **Stage Binning & Script Consolidation**
   - Group scripts into sequential numbered stages under `scripts/01_...` through `05_...`.
   - Replace repetitive shell script loops (e.g., hundreds of `python script.py --id X` lines) with parameterized loops or vectorized arguments inside that stage's `run.py`.
   - Write the 4-part `README.md` for every stage.
   *Completion criterion*: Each numbered stage folder has one definitive entrypoint and a complete 4-part `README.md`.

5. **Wire Pipeline Runner & Generate Receipts**
   - Configure `run_pipeline.py` with stage definitions and execution commands.
   - Run each stage sequentially with `python run_pipeline.py --stage <XX>` and verify each stage outputs its text-only summary into `summary/<XX>.md`.
   *Completion criterion*: `python run_pipeline.py --all` executes end-to-end cleanly, all output artifacts land in `output/`, and all summary receipts are committed to Git.

---

## Progressive Disclosure

- For the complete code of the pipeline orchestrator, the 4-part README contract, and `.gitignore` configs, see [TEMPLATES.md](TEMPLATES.md).
- For step-by-step diagnostic checklists and the refactoring case study based on `GLM-PhyloG2P-Bird`, see [AUDIT_CHECKLIST.md](AUDIT_CHECKLIST.md).
