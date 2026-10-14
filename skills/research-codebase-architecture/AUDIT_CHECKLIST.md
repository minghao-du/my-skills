# Research Codebase Audit & Migration Guide

This checklist guides the diagnostic evaluation of existing scientific codebases and provides a step-by-step migration workflow, featuring a concrete case study based on `GLM-PhyloG2P-Bird`.

---

## The 10-Point Health Audit Checklist

Run this audit against any research project to measure architectural health:

| # | Check Item | Pass Criterion | Common Smell in Failing Repos |
| :- | :--- | :--- | :--- |
| **1** | **Root Cleanliness** | Root contains only orchestrator, env config, main README, and canonical folders (`data/`, `scripts/`, `output/`, `summary/`, `_ignore/`). | Loose test images (`*.png`), slides (`*.pptx`), scratch markdown notes (`task.md`, `prob.md`), or ad-hoc test scripts in root. |
| **2** | **Quarantine Isolation** | All scratchpads, exploratory tests, and temporary play directories are strictly inside `_ignore/`. | Directories like `play/`, `play_NCBI/`, `play_evo2/`, `scratch/` sitting directly in the root or mixed with production scripts. |
| **3** | **Immutable Data Boundary** | Raw downloaded data in `data/` is strictly read-only and never overwritten by any pipeline step. | Scripts directly mutating source FASTA files or writing intermediate outputs back into raw data folders. |
| **4** | **Stage Execution Ordering** | All pipeline steps under `scripts/` are strictly prefixed with sequential numbers (`01_`, `02_`, etc.). | Arbitrary topic-based folder trees (e.g., `scripts/models`, `scripts/tools`) where execution sequence cannot be deduced. |
| **5** | **Subfolder Self-Description** | Every stage folder under `scripts/` has a 4-part `README.md` (Purpose, Inputs, Run Command, Outputs). | Undocumented scripts requiring line-by-line code inspection to understand CLI arguments and dependencies. |
| **6** | **Artifact Mirroring** | Generated artifacts live in `output/<stage_number>/`, mirroring the exact stage names in `scripts/`. | Scattered output files across arbitrary subdirectories or mixed into code folders. |
| **7** | **Agent-Readable Summary Receipts** | `summary/` contains git-committed text-only markdown receipts for each stage recording run metrics and artifact paths. | Zero textual record of execution results; agents and humans must write Python scripts to inspect binary `.npy`/`.pt` outputs. |
| **8** | **Single-Command Pipeline** | A single master runner (`run_pipeline.py`) can reproduce any single stage or the entire project (`--all`). | Giant brittle bash scripts (`task.sh`) containing hundreds of copy-pasted, hardcoded execution lines. |
| **9** | **Cluster/HPC Decoupling** | Heavy compute stages decouple algorithm logic (`run.py`) from cluster scheduling (`submit.sbatch`). | Hardcoded cluster paths (`/g12318240xjq/...`) and node-specific flags hardcoded into Python application logic. |
| **10**| **Clean Version Control** | Large binaries (`*.npy`, `*.npz`, `*.fasta`, `*.bam`) and scratch workspaces (`output/`, `_ignore/`) are strictly gitignored. | Git repository bloat from committed checkpoint files, embeddings, or transient output plots. |

---

## Case Study: Refactoring `GLM-PhyloG2P-Bird`

### 1. Diagnosis of Current Friction

In `/Users/Minghao/Research/GLM-PhyloG2P-Bird`, inspection reveals:
1. **Root Pollution**: Files like `W020200908616221420875.png`, `phylo-g2p.pptx`, `PGLS.md`, `prob.md`, `prom.md`, `self.md`, and directories `play/`, `play_NCBI/`, `play_evo2/`, `play_g2p/`, `play_genome/` sit directly in the root.
2. **Brittle Shell Loop**: `task.sh` consists of 202 lines of copy-pasted commands:
   ```bash
   python3 scripts/embedding/esm/esm_embedding/esm_embedding.py --ortho-id 2 --model-type msa;
   python3 scripts/embedding/esm/esm_embedding/esm_embedding.py --ortho-id 4 --model-type msa;
   ...
   ```
   If step 55 fails, manual inspection and command re-editing is required; no range execution or unified timing exists.
3. **Implicit Data Dependencies**: `scripts/` is categorized into 5 topic folders (`b10k_data`, `fine-tuning`, `embedding`, `g2p`, `simulation`), but the temporal execution order between `fine-tuning` and `embedding` is non-obvious without studying `file_structure.md`.

---

### 2. Target Architecture Mapping

| Existing Location in `GLM-PhyloG2P-Bird` | Target Canonical Location | Nature of Change |
| :--- | :--- | :--- |
| `play*`, `*.pptx`, `*.png`, `prob.md`, `prom.md`, `self.md` | `_ignore/` | **Quarantine**: Gitignored, keeps root clean while retaining exploratory notes and slides. |
| `scripts/b10k_data/` | `scripts/01_b10k_data/` | **Stage 01**: GFF curation, ortholog mRNA sequence extraction. |
| `scripts/fine-tuning/` & `scripts/embedding/` | `scripts/02_embeddings/` | **Stage 02**: Evo2 7B & ESM-2/MSA representation extraction. |
| `scripts/g2p/` | `scripts/03_g2p_modeling/` | **Stage 03**: Phenotype prediction models (Ridge, BM, LassoNet, PhylogNN). |
| `scripts/simulation/` | `scripts/04_simulation/` | **Stage 04**: Synthetic epistasis and phylogenetic drift simulation. |
| Loose plot scripts in `fine-tuning/evo2-mrna-*/plot_*.py` | `scripts/05_figures/` | **Stage 05**: Centralized publication figures and statistical tables. |
| 202-line `task.sh` | Parameterized `scripts/02_embeddings/run.py` | **Consolidation**: Replace copy-paste with `--ortho-ids 2,4,5...` or `--ortho-all`. |
| Scattered `output/` | Mirrored `output/01_...` to `output/05_...` | **Mirroring**: Clean isolation of heavy `.npy` embeddings and tables. |
| New addition | `summary/01_...md` to `05_...md` | **Receipts**: Agent-readable text summaries of sample counts, R2 scores, and output file indexes. |

---

### 3. Step-by-Step Refactoring Workflow

To migrate `GLM-PhyloG2P-Bird` (or any similar research repo):

#### Step 1: Create the Quarantine Zone
```bash
mkdir -p _ignore
mv play* _ignore/ 2>/dev/null || true
mv *.pptx *.png prob.md prom.md self.md task.md _ignore/ 2>/dev/null || true
```

#### Step 2: Establish Canonical Directories & `.gitignore`
```bash
mkdir -p data output summary scripts
# Ensure .gitignore includes output/ and _ignore/
```

#### Step 3: Consolidate Parameter Loops
Transform hardcoded loops like `task.sh` into Python batching:
```python
# Inside scripts/02_embeddings/run.py
parser.add_argument("--ortho-ids", nargs="*", type=int, help="Target ortholog IDs (default: all)")
# If not specified, load ortholog list from summary or config, then loop with progress bar
```

#### Step 4: Write the Subfolder Contract
In each `scripts/0X_*/`, create the standard `README.md` following the 4-part card format.

#### Step 5: Wire into `run_pipeline.py`
Place `run_pipeline.py` at the root and define the `STAGES` list to point to each stage's `run.py`. Test individual execution:
```bash
python run_pipeline.py --stage 01
python run_pipeline.py --stage 02 -- --model-type msa
```
