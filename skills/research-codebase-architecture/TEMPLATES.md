# Architecture Templates & Specifications

This document provides production-ready templates for the `research-codebase-architecture` skill.

---

## 1. Master Pipeline Runner (`run_pipeline.py`)

A pure Python orchestrator with zero external dependencies (uses standard library `argparse` and `subprocess`), supporting stage-by-stage execution, ranges, full reproduction, and argument forwarding.

```python
#!/usr/bin/env python3
"""
Master Pipeline Runner for Scientific Research
==============================================
Provides single-command execution and precise stage-wise reproduction.

Usage:
    python run_pipeline.py --help
    python run_pipeline.py --all
    python run_pipeline.py --stage 03_models
    python run_pipeline.py --from 02 --to 04
    python run_pipeline.py --stage 03_models -- --batch-size 64 --device cuda:0
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Define the ordered stages: (stage_prefix, stage_dir, default_script)
STAGES: List[Dict[str, str]] = [
    {
        "id": "01",
        "name": "01_download",
        "cmd": [sys.executable, "scripts/01_download/run.py"],
        "desc": "Fetch raw data and verify checksums",
    },
    {
        "id": "02",
        "name": "02_preprocess",
        "cmd": [sys.executable, "scripts/02_preprocess/run.py"],
        "desc": "Clean, filter, and align sequences/features",
    },
    {
        "id": "03",
        "name": "03_models",
        "cmd": [sys.executable, "scripts/03_models/run.py"],
        "desc": "Run model inference and representation extraction",
    },
    {
        "id": "04",
        "name": "04_analysis",
        "cmd": [sys.executable, "scripts/04_analysis/run.py"],
        "desc": "Execute downstream statistics and hypothesis tests",
    },
    {
        "id": "05",
        "name": "05_figures",
        "cmd": [sys.executable, "scripts/05_figures/run.py"],
        "desc": "Generate publication-ready figures and tables",
    },
]


def match_stage(query: str) -> Optional[Dict[str, str]]:
    """Match a stage by id (e.g., '01') or full name (e.g., '01_download')."""
    query = query.strip().lower()
    for stage in STAGES:
        if stage["id"] == query or stage["name"].lower() == query:
            return stage
        if query in stage["name"].lower():
            return stage
    return None


def run_single_stage(stage: Dict[str, str], extra_args: List[str]) -> bool:
    """Execute a single pipeline stage."""
    print("\n" + "=" * 70)
    print(f"▶ [STAGE {stage['id']}] {stage['name']}: {stage['desc']}")
    print("=" * 70)

    # Ensure output directory exists
    out_dir = Path("output") / stage["name"]
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = list(stage["cmd"]) + extra_args
    print(f"Running command: {' '.join(cmd)}\n")

    start_time = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start_time

    if result.returncode != 0:
        print(f"\n❌ [STAGE {stage['id']} FAILED] (Exit code: {result.returncode}, Elapsed: {elapsed:.2f}s)")
        return False

    print(f"\n✅ [STAGE {stage['id']} COMPLETED] (Elapsed: {elapsed:.2f}s)")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Master Pipeline Runner for Scientific Research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all stages from start to finish")
    group.add_argument("--stage", type=str, help="Run a specific stage (e.g. '03' or '03_models')")
    group.add_argument("--list", action="store_true", help="List all defined pipeline stages")
    group.add_argument("--from", dest="from_stage", type=str, help="Start stage for range execution")

    parser.add_argument("--to", dest="to_stage", type=str, help="End stage for range execution (used with --from)")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER, help="Arguments passed directly to stage script")

    args = parser.parse_args()

    # Pass-through args: strip leading '--' if present
    extra_args = args.extra_args
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    if args.list:
        print("\nConfigured Pipeline Stages:")
        print("-" * 50)
        for s in STAGES:
            print(f"  [{s['id']}] {s['name']:<18} : {s['desc']}")
        print()
        return

    # Determine execution targets
    stages_to_run: List[Dict[str, str]] = []

    if args.all:
        stages_to_run = STAGES
    elif args.stage:
        target = match_stage(args.stage)
        if not target:
            print(f"Error: Unknown stage '{args.stage}'. Use --list to see available stages.", file=sys.stderr)
            sys.exit(1)
        stages_to_run = [target]
    elif args.from_stage:
        start_stage = match_stage(args.from_stage)
        if not start_stage:
            print(f"Error: Unknown start stage '{args.from_stage}'.", file=sys.stderr)
            sys.exit(1)

        end_stage = match_stage(args.to_stage) if args.to_stage else STAGES[-1]
        if not end_stage:
            print(f"Error: Unknown end stage '{args.to_stage}'.", file=sys.stderr)
            sys.exit(1)

        start_idx = STAGES.index(start_stage)
        end_idx = STAGES.index(end_stage)
        if start_idx > end_idx:
            print(f"Error: Start stage '{args.from_stage}' comes after end stage '{args.to_stage}'.", file=sys.stderr)
            sys.exit(1)

        stages_to_run = STAGES[start_idx : end_idx + 1]

    # Execute selected stages
    total_start = time.time()
    for s in stages_to_run:
        success = run_single_stage(s, extra_args)
        if not success:
            print("\nPipeline aborted due to stage failure.", file=sys.stderr)
            sys.exit(1)

    total_elapsed = time.time() - total_start
    print("\n" + "=" * 70)
    print(f"🎉 Pipeline execution finished successfully in {total_elapsed:.2f}s!")
    print("=" * 70)


if __name__ == "__main__":
    main()
```

---

## 2. Stage `README.md` Template (The 4-Part Contract)

Save this file in every stage folder (e.g., `scripts/03_models/README.md`):

```markdown
# Stage <XX>: <Stage Name>

## 1. Purpose (目标与职责)
Brief 1-2 sentence description explaining the scientific problem addressed by this stage and what transformations take place.

## 2. Inputs (前置输入)
List all external inputs and upstream stage dependencies required for execution:
- `data/<raw_file>`: Description of immutable input data
- `output/<previous_stage>/<artifact>`: Upstream dependency from prior stage

## 3. Run Command (独立执行命令)
The exact, self-contained single-line command to run this stage independently:
\`\`\`bash
# Run locally
python scripts/<stage_folder>/run.py --config config.yaml

# Run via pipeline runner
python run_pipeline.py --stage <stage_id>

# Run on Slurm cluster (if applicable)
sbatch scripts/<stage_folder>/submit.sbatch
\`\`\`

## 4. Outputs (产物说明)
List all files produced by this stage in `output/<stage_folder>/`:
| File Path | Format | Description |
| :--- | :--- | :--- |
| `output/<stage>/summary.tsv` | TSV table | Consolidated metrics per species |
| `output/<stage>/embeddings/*.npy` | NumPy float32 | Extracted model representations |
```

---

## 3. Summary Receipt Template (`summary/0X_*.md`)

Each stage automatically or manually appends its run receipt to a Git-tracked text summary. This gives AI agents and researchers an instant view of the scientific results without loading multi-gigabyte binary files.

```markdown
# Stage Summary: <XX> - <Stage Name>

- **Execution Date**: `2026-10-14 16:30:00`
- **Command Run**: `python scripts/03_models/run.py --model evo2_7b --layer 19`
- **Runtime**: `4h 12m 35s` (Cluster GPU: 4x NVIDIA A100 80GB)

---

## Key Metrics & Results (核心定量指标)

| Metric | Value | Baseline / Target | Notes |
| :--- | :--- | :--- | :--- |
| Total Processed Samples | 363 species | 363 species | 100% completion |
| Mean Perplexity | 4.82 ± 0.31 | 5.41 (random baseline) | Statistically significant drop |
| Embedding Dim | 4096 | Layer 19 hidden dim | Float32 normalized |

---

## Generated Artifacts Index (产物索引)

All artifact files are located in `output/03_models/`:
- `output/03_models/embeddings_layer_19.npy`: [Matrix: 363 x 4096] Extracted mean embeddings per species.
- `output/03_models/species_order.tsv`: Species row ordering for embedding matrix.
- `output/03_models/perplexity_summary.tsv`: Detailed per-transcript perplexity table.

---

## Observations & Notes (观察与异常记录)
- 2 species (Species_A, Species_B) contained ambiguous bases (`N > 5%`) in CDS, masked out during evaluation.
- No out-of-memory errors encountered.
```

---

## 4. Standard Scientific `.gitignore` Template

```gitignore
# Python & Bytecode
__pycache__/
*.py[cod]
*$py.class
.venv/
env/
venv/

# Interactive Notebook Checkpoints
.ipynb_checkpoints/

# Research Artifacts & Data Isolation
output/
_ignore/
scratch/
play*/

# Large Scientific Data Formats (Safety Net)
*.npy
*.npz
*.h5
*.hdf5
*.pt
*.pth
*.ckpt
*.fasta
*.fa
*.bam
*.sam
*.vcf
*.vcf.gz
*.tar.gz
*.zip

# OS & IDE Cache
.DS_Store
.vscode/
.idea/
.ruff_cache/
.pytest_cache/
```
