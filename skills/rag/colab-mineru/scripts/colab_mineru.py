#!/usr/bin/env python3
"""Run MinerU PDF-to-Markdown parsing on a Google Colab GPU runtime."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Sequence
import unicodedata
import uuid

DEFAULT_GPU = "T4"
DEFAULT_TIER = "standard"
DEFAULT_EXTRA = "full"
DEFAULT_CHUNK_SIZE = 40
DEFAULT_POLL_INTERVAL = 15
DEFAULT_SERVER_TIMEOUT = 600
DEFAULT_PARSE_TIMEOUT = 600
REMOTE_PATH_PREFIX = 'export PATH="/root/.local/bin:$PATH"'

MANAGED_TIER_MAP: dict[str, str | None] = {
    "flash": None,
    "basic": "basic",
    "standard": "standard",
    "advanced": "standard",
}

EXTRA_SPEC_MAP: dict[str, str] = {
    "base": "mineru>=4.0,<5",
    "torch": "mineru[torch]>=4.0,<5",
    "full": "mineru[full]>=4.0,<5",
}


class ColabMineruError(RuntimeError):
    """Raised when Colab provisioning, MinerU setup, or parsing fails."""


@dataclass(frozen=True)
class Config:
    pdf_path: Path
    output_path: Path
    force: bool
    session: str | None
    keep: bool
    keep_on_error: bool
    gpu: str
    allow_cpu: bool
    tier: str
    extra: str
    pages: str
    chunk_size: int
    poll_interval: int
    server_timeout: int
    parse_timeout: int
    colab_bin: str
    dry_run: bool


def slugify_pdf_stem(stem: str) -> str:
    """Convert a PDF filename stem into a clean kebab-case filename stem."""
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text.lower()).strip("-")
    if slug:
        return slug
    fallback = re.sub(r"[^\w\-]+", "-", stem.strip()).strip("-_")
    return fallback or "output"


def resolve_output_path(pdf_path: Path, output_arg: str | None) -> Path:
    """Resolve explicit .md file path or target directory to a final .md path."""
    auto_name = f"{slugify_pdf_stem(pdf_path.stem)}.md"
    if output_arg is None:
        return Path.cwd() / auto_name

    candidate = Path(output_arg).expanduser()
    if candidate.exists() and candidate.is_dir():
        return candidate.resolve() / auto_name
    if candidate.suffix.lower() == ".md" and not str(output_arg).endswith(("/", os.sep)):
        return candidate.resolve()
    return candidate.resolve() / auto_name


def managed_tier_for(tier: str) -> str | None:
    """Map a requested MinerU parsing tier to the required local managed server tier."""
    if tier not in MANAGED_TIER_MAP:
        raise ColabMineruError(f"Unsupported tier: {tier}")
    return MANAGED_TIER_MAP[tier]


def compute_page_chunks(total_pages: int, chunk_size: int) -> list[str]:
    """Split 1..total_pages into inclusive page range strings of at most chunk_size."""
    if total_pages < 1:
        raise ColabMineruError(f"Invalid total page count: {total_pages}")
    if chunk_size < 1:
        raise ColabMineruError(f"Invalid chunk size: {chunk_size}")
    ranges: list[str] = []
    start = 1
    while start <= total_pages:
        end = min(start + chunk_size - 1, total_pages)
        ranges.append(f"{start}" if start == end else f"{start}-{end}")
        start = end + 1
    return ranges


def log(msg: str) -> None:
    print(f"[colab-mineru] {msg}", file=sys.stderr, flush=True)


class ColabRunner:
    """Thin wrapper over the local `colab` CLI."""

    def __init__(self, colab_bin: str = "colab", run_fn: Callable[..., subprocess.CompletedProcess[str]] | None = None):
        self.colab_bin = colab_bin
        self._run_fn = run_fn or subprocess.run

    def run_cli(self, args: Sequence[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = [self.colab_bin, *args]
        proc = self._run_fn(cmd, input=input_text, text=True, capture_output=True)
        if check and proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise ColabMineruError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{detail}")
        return proc

    def new_session(self, session: str, gpu: str | None) -> None:
        args = ["new", "-s", session]
        if gpu:
            args.extend(["--gpu", gpu])
        self.run_cli(args)

    def stop_session(self, session: str) -> None:
        self.run_cli(["stop", "-s", session])

    def upload(self, session: str, local_path: Path, remote_path: str) -> None:
        self.run_cli(["upload", "-s", session, str(local_path), remote_path])

    def download(self, session: str, remote_path: str, local_path: Path) -> None:
        self.run_cli(["download", "-s", session, remote_path, str(local_path)])

    def exec_python(self, session: str, code: str, *, timeout: int = 180) -> str:
        proc = self.run_cli(
            ["exec", "-s", session, "--timeout", str(timeout)],
            input_text=code,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise ColabMineruError(f"colab exec failed ({proc.returncode}):\n{detail}")
        return proc.stdout

    def exec_json(self, session: str, code: str, *, timeout: int = 180) -> dict:
        out = self.exec_python(session, code, timeout=timeout)
        marker = "__COLAB_MINERU_JSON__:"
        for line in reversed(out.splitlines()):
            if line.startswith(marker):
                return json.loads(line[len(marker):])
        raise ColabMineruError(f"Missing JSON marker in colab exec output:\n{out[-1500:]}")


def _remote_shell_json_script(shell_cmd: str) -> str:
    """Build a short Python snippet executed in Colab that runs a shell command and emits JSON."""
    return (
        "import json, os, subprocess\n"
        'os.environ["PATH"] = f"/root/.local/bin:{os.environ.get(\'PATH\', \'\')}"\n'
        f"cmd = {shell_cmd!r}\n"
        "p = subprocess.run(cmd, shell=True, text=True, capture_output=True)\n"
        "payload = {'rc': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}\n"
        "print('__COLAB_MINERU_JSON__:' + json.dumps(payload))\n"
    )


def provision_session(runner: ColabRunner, cfg: Config) -> tuple[str, bool]:
    """Return (session_name, created_here)."""
    if cfg.session:
        # Check if session already exists; if not, create it with the requested name.
        sessions_out = runner.run_cli(["sessions"], check=False)
        pattern = rf"(?:^|\s){re.escape(cfg.session)}(?=\s|$)"
        if sessions_out.returncode == 0 and re.search(pattern, sessions_out.stdout, re.MULTILINE):
            log(f"Reusing existing Colab session '{cfg.session}'")
            return cfg.session, False
        session_name = cfg.session
    else:
        session_name = f"mineru-{uuid.uuid4().hex[:8]}"

    log(f"Creating Colab session '{session_name}' (gpu={cfg.gpu})...")
    try:
        runner.new_session(session_name, cfg.gpu)
        return session_name, True
    except ColabMineruError as exc:
        if not cfg.allow_cpu:
            raise ColabMineruError(
                f"Failed to allocate Colab --gpu {cfg.gpu} session (pass --allow-cpu to fall back to CPU): {exc}"
            ) from exc
        log(f"GPU {cfg.gpu} unavailable; falling back to CPU runtime (--allow-cpu)...")
        runner.new_session(session_name, None)
        return session_name, True


def ensure_mineru_installed(runner: ColabRunner, session: str, extra: str) -> None:
    """Install uv + MinerU >=4.0,<5 in Python 3.12 if not already installed."""
    probe = runner.exec_json(
        session,
        _remote_shell_json_script("command -v mineru && mineru version --json"),
        timeout=60,
    )
    if probe["rc"] == 0:
        try:
            ver = json.loads(probe["stdout"].strip().splitlines()[-1])
            log(f"MinerU already installed in Colab: {ver.get('mineru_version')} (Python {ver.get('python_version')})")
            return
        except json.JSONDecodeError:
            pass

    pkg_spec = EXTRA_SPEC_MAP[extra]
    log(f"Installing {pkg_spec} on Python 3.12 in Colab...")
    install_cmd = (
        f"{REMOTE_PATH_PREFIX}; "
        "command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh; "
        "uv python find 3.12 >/dev/null 2>&1 || uv python install 3.12; "
        f"uv tool install --python 3.12 {shlex.quote(pkg_spec)} && mineru version --json"
    )
    res = runner.exec_json(session, _remote_shell_json_script(install_cmd), timeout=300)
    if res["rc"] != 0:
        raise ColabMineruError(f"Failed to install {pkg_spec} in Colab:\n{res['stdout']}\n{res['stderr']}")
    log("MinerU installation complete.")


def ensure_server_and_models(runner: ColabRunner, cfg: Config, session: str) -> None:
    """Download/verify models if needed, start mineru server, and wait until managed tier is healthy."""
    target_managed_tier = managed_tier_for(cfg.tier)

    status_res = runner.exec_json(session, _remote_shell_json_script("mineru server status --json"), timeout=60)
    if _is_server_ready(status_res, target_managed_tier):
        log(f"MinerU server already healthy for tier '{cfg.tier}'.")
        return

    if target_managed_tier is not None:
        verify_res = runner.exec_json(
            session,
            _remote_shell_json_script(f"mineru-kit models verify --tier {shlex.quote(target_managed_tier)}"),
            timeout=120,
        )
        if verify_res["rc"] != 0:
            log(f"Downloading and verifying '{target_managed_tier}' models...")
            dl_cmd = (
                f"mineru-kit models download --tier {shlex.quote(target_managed_tier)} && "
                f"mineru-kit models verify --tier {shlex.quote(target_managed_tier)}"
            )
            dl_res = runner.exec_json(session, _remote_shell_json_script(dl_cmd), timeout=300)
            if dl_res["rc"] != 0:
                raise ColabMineruError(
                    f"Model download/verify failed for tier '{target_managed_tier}':\n{dl_res['stdout']}\n{dl_res['stderr']}"
                )

    setup_cmds = ["mineru server status --json >/dev/null 2>&1 || mineru server start"]
    if target_managed_tier is not None:
        setup_cmds.append(f"mineru config set parse_server.local.managed_tier {shlex.quote(target_managed_tier)}")
        setup_cmds.append("mineru config set parse_server.local.mode managed")
    setup_res = runner.exec_json(session, _remote_shell_json_script(" && ".join(setup_cmds)), timeout=120)
    if setup_res["rc"] != 0:
        raise ColabMineruError(
            f"Failed to start/configure MinerU server:\n{setup_res['stdout']}\n{setup_res['stderr']}"
        )

    if target_managed_tier is None:
        return

    log(f"Waiting for MinerU managed '{target_managed_tier}' server to become healthy...")
    deadline = time.monotonic() + cfg.server_timeout
    while time.monotonic() < deadline:
        poll = runner.exec_json(session, _remote_shell_json_script("mineru server status --json"), timeout=60)
        if _is_server_ready(poll, target_managed_tier):
            log(f"MinerU managed '{target_managed_tier}' server is healthy.")
            return
        time.sleep(cfg.poll_interval)

    raise ColabMineruError(f"Timed out after {cfg.server_timeout}s waiting for MinerU '{target_managed_tier}' server.")


def _is_server_ready(status_res: dict, target_managed_tier: str | None) -> bool:
    if status_res.get("rc") != 0:
        return False
    try:
        data = json.loads(status_res.get("stdout", ""))
    except json.JSONDecodeError:
        return False
    if not data.get("running"):
        return False
    if target_managed_tier is None:
        return True
    local = (data.get("parse_server") or {}).get("local") or {}
    tiers = local.get("supported_tiers") or []
    return bool(local.get("healthy")) and local.get("managed_tier") == target_managed_tier and target_managed_tier in tiers


def submit_and_wait_parse(
    runner: ColabRunner,
    session: str,
    remote_pdf: str,
    tier: str,
    pages: str,
    *,
    poll_interval: int,
    parse_timeout: int,
) -> int:
    """Submit a non-blocking MinerU parse job and poll until completion."""
    cmd = (
        f"mineru parse {shlex.quote(remote_pdf)} "
        f"--tier {shlex.quote(tier)} --pages {shlex.quote(pages)} --no-wait --json"
    )
    res = runner.exec_json(session, _remote_shell_json_script(cmd), timeout=120)
    if res["rc"] != 0:
        raise ColabMineruError(f"mineru parse submission failed ({pages}):\n{res['stdout']}\n{res['stderr']}")

    try:
        payload = json.loads(res["stdout"])
    except json.JSONDecodeError as exc:
        raise ColabMineruError(f"Invalid JSON from mineru parse ({pages}):\n{res['stdout']}") from exc

    if "error" in payload:
        raise ColabMineruError(f"mineru parse error ({pages}): {json.dumps(payload['error'])}")

    parse_info = payload.get("parse") or {}
    parse_ids = parse_info.get("wait_parse_ids") or parse_info.get("created_parse_ids") or parse_info.get("reused_parse_ids") or []
    if not parse_ids:
        if parse_info.get("status") == "done":
            return 0
        raise ColabMineruError(f"No parse ID returned for {pages}: {payload}")

    parse_id = int(parse_ids[0])
    if parse_info.get("status") == "done":
        return parse_id

    log(f"Submitted parse job id={parse_id} (pages={pages}, tier={tier}); polling...")
    deadline = time.monotonic() + parse_timeout
    while time.monotonic() < deadline:
        check = runner.exec_json(session, _remote_shell_json_script(f"mineru show parse {parse_id} --json"), timeout=60)
        if check["rc"] == 0:
            try:
                info = json.loads(check["stdout"])
                status = info.get("status")
                if status == "done":
                    log(f"Parse job id={parse_id} (pages={pages}) completed.")
                    return parse_id
                if status in ("failed", "error", "cancelled"):
                    raise ColabMineruError(
                        f"Parse job id={parse_id} ({pages}) {status}: "
                        f"code={info.get('error_code')} msg={info.get('error_msg')}"
                    )
            except json.JSONDecodeError:
                pass
        time.sleep(poll_interval)

    raise ColabMineruError(f"Parse job id={parse_id} ({pages}) timed out after {parse_timeout}s.")


def export_markdown_range(runner: ColabRunner, session: str, remote_pdf: str, tier: str, pages: str, remote_md: str) -> int:
    """Export a cached parse range to remote_md and return its byte size."""
    cmd = (
        f"mineru parse {shlex.quote(remote_pdf)} --tier {shlex.quote(tier)} "
        f"--pages {shlex.quote(pages)} --no-marker --output {shlex.quote(remote_md)}"
    )
    code = (
        "import json, os, subprocess\n"
        'os.environ["PATH"] = f"/root/.local/bin:{os.environ.get(\'PATH\', \'\')}"\n'
        f"p = subprocess.run({cmd!r}, shell=True, text=True, capture_output=True)\n"
        f"size = os.path.getsize({remote_md!r}) if p.returncode == 0 and os.path.exists({remote_md!r}) else -1\n"
        "print('__COLAB_MINERU_JSON__:' + json.dumps({'rc': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'size': size}))\n"
    )
    res = runner.exec_json(session, code, timeout=180)
    if res["rc"] != 0 or res["size"] <= 0:
        raise ColabMineruError(
            f"Failed to export markdown ({pages}) to {remote_md} (size={res.get('size')}):\n"
            f"{res['stdout']}\n{res['stderr']}"
        )
    return int(res["size"])


def get_remote_pdf_page_count(runner: ColabRunner, session: str, remote_pdf: str) -> int:
    """Read total PDF page count inside the Colab mineru environment."""
    inner_code = (
        "import json, pypdf\n"
        f"reader = pypdf.PdfReader({remote_pdf!r})\n"
        "print('__COLAB_MINERU_JSON__:' + json.dumps({'pages': len(reader.pages)}))\n"
    )
    code = (
        "import json, os, shutil, subprocess\n"
        'os.environ["PATH"] = f"/root/.local/bin:{os.environ.get(\'PATH\', \'\')}"\n'
        "mineru_bin = shutil.which('mineru')\n"
        "py = os.path.join(os.path.dirname(os.path.realpath(mineru_bin)), 'python') if mineru_bin else 'python3'\n"
        f"p = subprocess.run([py, '-c', {inner_code!r}], text=True, capture_output=True)\n"
        "if p.returncode != 0:\n"
        "    raise RuntimeError(p.stderr or p.stdout)\n"
        "print(p.stdout.strip())\n"
    )
    res = runner.exec_json(session, code, timeout=60)
    return int(res["pages"])


def parse_and_export_with_fallback(
    runner: ColabRunner,
    cfg: Config,
    session: str,
    remote_dir: str,
    remote_pdf: str,
    remote_final_md: str,
) -> int:
    """Parse requested pages (falling back to chunked pagination if full-doc parse fails) and export."""
    try:
        submit_and_wait_parse(
            runner,
            session,
            remote_pdf,
            cfg.tier,
            cfg.pages,
            poll_interval=cfg.poll_interval,
            parse_timeout=cfg.parse_timeout,
        )
        return export_markdown_range(runner, session, remote_pdf, cfg.tier, cfg.pages, remote_final_md)
    except ColabMineruError as full_err:
        if cfg.pages != "all":
            raise
        log(f"Full-document parse failed ({full_err}); retrying with chunk size {cfg.chunk_size}...")

    total_pages = get_remote_pdf_page_count(runner, session, remote_pdf)
    ranges = compute_page_chunks(total_pages, cfg.chunk_size)
    log(f"PDF has {total_pages} pages; parsing in {len(ranges)} chunks: {', '.join(ranges)}")

    chunk_files: list[str] = []
    for idx, page_range in enumerate(ranges, start=1):
        chunk_md = f"{remote_dir}/chunk_{idx:03d}.md"
        submit_and_wait_parse(
            runner,
            session,
            remote_pdf,
            cfg.tier,
            page_range,
            poll_interval=cfg.poll_interval,
            parse_timeout=cfg.parse_timeout,
        )
        export_markdown_range(runner, session, remote_pdf, cfg.tier, page_range, chunk_md)
        chunk_files.append(chunk_md)

    merge_code = (
        "import json, os\n"
        f"parts = []\n"
        f"for p in {chunk_files!r}:\n"
        "    with open(p, 'r', encoding='utf-8') as f:\n"
        "        txt = f.read().strip()\n"
        "        if txt:\n"
        "            parts.append(txt)\n"
        "merged = '\\n\\n'.join(parts) + ('\\n' if parts else '')\n"
        f"with open({remote_final_md!r}, 'w', encoding='utf-8') as out:\n"
        "    out.write(merged)\n"
        f"print('__COLAB_MINERU_JSON__:' + json.dumps({{'size': os.path.getsize({remote_final_md!r})}}))\n"
    )
    merged = runner.exec_json(session, merge_code, timeout=120)
    size = int(merged["size"])
    if size <= 0:
        raise ColabMineruError("Merged chunked markdown is empty.")
    return size


def collect_remote_diagnostics(runner: ColabRunner, session: str) -> str:
    """Fetch bounded MinerU status, parse list, and recent logs for troubleshooting."""
    code = (
        "import json, os, subprocess\n"
        'os.environ["PATH"] = f"/root/.local/bin:{os.environ.get(\'PATH\', \'\')}"\n'
        "status = subprocess.run('mineru server status --json', shell=True, text=True, capture_output=True)\n"
        "parses = subprocess.run('mineru list parses --json', shell=True, text=True, capture_output=True)\n"
        "summary = {'parses': parses.stdout[-3000:], 'parses_err': parses.stderr[-1000:]}\n"
        "try:\n"
        "    st = json.loads(status.stdout)\n"
        "    summary['parse_server'] = st.get('parse_server')\n"
        "    summary['error_summary'] = st.get('error_summary')\n"
        "    summary['recent_logs'] = (st.get('recent_logs') or [])[-20:]\n"
        "    summary['parse_server_stderr_logs'] = (st.get('parse_server_stderr_logs') or [])[-20:]\n"
        "except Exception:\n"
        "    summary['status_raw'] = status.stdout[-2000:]\n"
        "    summary['status_err'] = status.stderr[-1000:]\n"
        "print('__COLAB_MINERU_JSON__:' + json.dumps(summary, ensure_ascii=False))\n"
    )
    try:
        diag = runner.exec_json(session, code, timeout=60)
        return json.dumps(diag, indent=2, ensure_ascii=False)
    except Exception as exc:  # best-effort diagnostic capture
        return f"<failed to collect remote diagnostics: {exc}>"


def download_and_verify(runner: ColabRunner, session: str, remote_md: str, output_path: Path, expected_bytes: int) -> None:
    """Download remote_md to a staging file in output_path.parent, verify byte size, and replace atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".colab-mineru-", suffix=".md.tmp", dir=str(output_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        runner.download(session, remote_md, tmp_path)
        actual_bytes = tmp_path.stat().st_size
        if actual_bytes != expected_bytes or actual_bytes <= 0:
            raise ColabMineruError(
                f"Downloaded size mismatch for {output_path}: expected {expected_bytes} bytes, got {actual_bytes}"
            )
        os.replace(tmp_path, output_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def cleanup_remote_run_dir(runner: ColabRunner, session: str, remote_dir: str) -> None:
    try:
        runner.exec_json(session, _remote_shell_json_script(f"rm -rf {shlex.quote(remote_dir)}"), timeout=30)
    except Exception as exc:
        log(f"Warning: failed to remove temporary remote dir {remote_dir}: {exc}")


def run_pipeline(cfg: Config, runner: ColabRunner | None = None) -> Path:
    """Execute the full PDF -> Colab MinerU -> local Markdown pipeline."""
    if not cfg.pdf_path.is_file():
        raise ColabMineruError(f"Input PDF not found: {cfg.pdf_path}")
    if cfg.output_path.exists() and not cfg.force:
        raise ColabMineruError(f"Output already exists (pass --force to overwrite): {cfg.output_path}")

    if cfg.dry_run:
        print(
            json.dumps(
                {
                    "pdf_path": str(cfg.pdf_path),
                    "output_path": str(cfg.output_path),
                    "session": cfg.session or "<auto>",
                    "gpu": cfg.gpu,
                    "allow_cpu": cfg.allow_cpu,
                    "tier": cfg.tier,
                    "extra": cfg.extra,
                    "pages": cfg.pages,
                    "chunk_size": cfg.chunk_size,
                    "keep": cfg.keep,
                    "keep_on_error": cfg.keep_on_error,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return cfg.output_path

    runner = runner or ColabRunner(cfg.colab_bin)
    if shutil.which(cfg.colab_bin) is None and runner._run_fn is subprocess.run:
        raise ColabMineruError(f"Colab CLI not found on PATH: {cfg.colab_bin}")

    session: str | None = None
    run_id = uuid.uuid4().hex[:8]
    remote_dir = f"/content/colab_mineru/{run_id}"
    remote_pdf = f"{remote_dir}/input.pdf"
    remote_md = f"{remote_dir}/output.md"
    failed = False

    try:
        session, _ = provision_session(runner, cfg)
        runner.exec_json(session, _remote_shell_json_script(f"mkdir -p {shlex.quote(remote_dir)}"), timeout=30)
        log(f"Uploading {cfg.pdf_path} -> {remote_pdf}...")
        runner.upload(session, cfg.pdf_path, remote_pdf)

        ensure_mineru_installed(runner, session, cfg.extra)
        ensure_server_and_models(runner, cfg, session)
        expected_bytes = parse_and_export_with_fallback(runner, cfg, session, remote_dir, remote_pdf, remote_md)
        log(f"Downloading {expected_bytes} bytes -> {cfg.output_path}...")
        download_and_verify(runner, session, remote_md, cfg.output_path, expected_bytes)
        if cfg.keep:
            cleanup_remote_run_dir(runner, session, remote_dir)
        log(f"Done: {cfg.output_path} ({expected_bytes} bytes)")
        return cfg.output_path
    except Exception:
        failed = True
        if session:
            log(f"Collecting diagnostics from session '{session}' before cleanup...")
            print(collect_remote_diagnostics(runner, session), file=sys.stderr, flush=True)
        raise
    finally:
        if session:
            should_keep = cfg.keep or (failed and cfg.keep_on_error)
            if should_keep:
                log(f"Keeping Colab session '{session}' alive; stop manually with: colab stop -s {session}")
            else:
                try:
                    log(f"Stopping Colab session '{session}'...")
                    runner.stop_session(session)
                except Exception as stop_exc:
                    log(f"Warning: failed to stop Colab session '{session}': {stop_exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="colab-mineru",
        description="Parse a local PDF to Markdown via MinerU on a Google Colab GPU session.",
    )
    parser.add_argument("pdf", help="Path to the local input PDF file.")
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Target .md file path or output directory (auto-generates kebab-case .md if directory or omitted).",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite target .md if it already exists.")
    parser.add_argument("-s", "--session", default=None, help="Colab session name to create or reuse.")
    parser.add_argument("--keep", action="store_true", help="Keep Colab session running after completion.")
    parser.add_argument(
        "--keep-on-error",
        action="store_true",
        help="Keep Colab session running if parsing fails (default: dump diagnostics and stop session).",
    )
    parser.add_argument("--gpu", default=DEFAULT_GPU, help=f"Colab GPU accelerator (default: {DEFAULT_GPU}).")
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Allow falling back to a CPU Colab runtime if GPU allocation fails.",
    )
    parser.add_argument(
        "--tier",
        choices=sorted(MANAGED_TIER_MAP.keys()),
        default=DEFAULT_TIER,
        help=f"MinerU parsing tier (default: {DEFAULT_TIER}).",
    )
    parser.add_argument(
        "--extra",
        choices=sorted(EXTRA_SPEC_MAP.keys()),
        default=DEFAULT_EXTRA,
        help=f"MinerU package extra to install (default: {DEFAULT_EXTRA}).",
    )
    parser.add_argument("--pages", default="all", help="PDF page range (default: all).")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Pages per chunk when falling back after full-document failure (default: {DEFAULT_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between status polls (default: {DEFAULT_POLL_INTERVAL}).",
    )
    parser.add_argument(
        "--server-timeout",
        type=int,
        default=DEFAULT_SERVER_TIMEOUT,
        help=f"Max seconds to wait for MinerU server readiness (default: {DEFAULT_SERVER_TIMEOUT}).",
    )
    parser.add_argument(
        "--parse-timeout",
        type=int,
        default=DEFAULT_PARSE_TIMEOUT,
        help=f"Max seconds to wait per parse job (default: {DEFAULT_PARSE_TIMEOUT}).",
    )
    parser.add_argument("--colab-bin", default="colab", help="Path to colab CLI executable.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved paths/options and exit.")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> Config:
    ns = build_parser().parse_args(argv)
    pdf_path = Path(ns.pdf).expanduser().resolve()
    output_path = resolve_output_path(pdf_path, ns.output)
    return Config(
        pdf_path=pdf_path,
        output_path=output_path,
        force=ns.force,
        session=ns.session,
        keep=ns.keep,
        keep_on_error=ns.keep_on_error,
        gpu=ns.gpu,
        allow_cpu=ns.allow_cpu,
        tier=ns.tier,
        extra=ns.extra,
        pages=ns.pages,
        chunk_size=ns.chunk_size,
        poll_interval=ns.poll_interval,
        server_timeout=ns.server_timeout,
        parse_timeout=ns.parse_timeout,
        colab_bin=ns.colab_bin,
        dry_run=ns.dry_run,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        cfg = parse_args(argv)
        run_pipeline(cfg)
        return 0
    except ColabMineruError as exc:
        print(f"[colab-mineru] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
