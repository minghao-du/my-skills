---
name: colab-mineru
description: Parse a local PDF into Markdown via MinerU on a Google Colab GPU session.
disable-model-invocation: true
---

Convert local PDFs into clean Markdown by provisioning a Google Colab GPU runtime, running MinerU (`standard` tier by default), downloading the result locally, and tearing down the VM.

Resolve `<skill_dir>` to the directory containing this file. The runnable CLI is `<skill_dir>/scripts/colab_mineru.py` (also symlinked on `PATH` as `colab-mineru`). Run `<skill_dir>/scripts/colab_mineru.py --help` for full option defaults.

## Workflow

1. **Confirm inputs**: Verify the local PDF path exists and determine the target `.md` file path or target directory.
   - Passing a directory (or omitting the output argument) writes `<kebab-case-stem>.md` into that directory.
   - Existing target files are rejected unless `--force` is passed.
2. **Run the pipeline**:
   - Single PDF:
     ```bash
     colab-mineru "<local.pdf>" "<output.md or dir>"
     ```
   - Multiple PDFs in one batch (avoids repeating the ~9.5 min Colab + vLLM warmup): pass `-s <session-name> --keep` on every PDF except the last, and omit `--keep` on the final PDF so it stops the VM on exit.
3. **Handle failure branches** (never silently switch to CPU or MinerU `--remote` cloud API):
   - **GPU quota rejected (`--gpu T4` fails)**: Stop and report the error. Only re-run with `--allow-cpu` if the user explicitly agrees to a CPU runtime.
   - **Colab auth failure**: Run `colab whoami` to inspect credentials and ask the user to re-authenticate before retrying.
   - **Chunked parse still fails**: The script automatically retries `--pages all` failures by splitting into page chunks (`--chunk-size`, default `40`), then prints MinerU server/parse diagnostics and stops the VM (unless `--keep-on-error` was passed). Present the printed diagnostics to the user before taking further action; if `--keep-on-error` kept the VM alive, run `colab stop -s <session>` once troubleshooting finishes.

## Completion

Verify the target `.md` file exists locally, is non-empty, and matches the expected page scope. Confirm no unintended Colab session remains running via `colab sessions`.
