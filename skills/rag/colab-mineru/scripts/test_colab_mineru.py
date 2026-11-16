#!/usr/bin/env python3
"""Offline unit tests for colab_mineru.py (mocking Colab CLI subprocesses)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import colab_mineru as cm  # noqa: E402


class FakeColabHarness:
    """In-memory fake `colab` CLI state machine for testing run_pipeline."""

    def __init__(
        self,
        *,
        existing_sessions: list[str] | None = None,
        gpu_available: bool = True,
        mineru_preinstalled: bool = False,
        server_prehealthy: bool = False,
        fail_full_parse: bool = False,
        fail_all_parses: bool = False,
        total_pages: int = 90,
        corrupt_download: bool = False,
    ) -> None:
        self.sessions = list(existing_sessions or [])
        self.gpu_available = gpu_available
        self.mineru_installed = mineru_preinstalled
        self.models_ready = server_prehealthy
        self.server_healthy = server_prehealthy
        self.fail_full_parse = fail_full_parse
        self.fail_all_parses = fail_all_parses
        self.total_pages = total_pages
        self.corrupt_download = corrupt_download

        self.calls: list[list[str]] = []
        self.remote_files: dict[str, bytes] = {}
        self.next_parse_id = 1
        self.parses: dict[int, dict] = {}
        self.stopped_sessions: list[str] = []

    def __call__(self, cmd: list[str], *, input: str | None = None, text: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        sub = cmd[1]

        if sub == "sessions":
            out = "\n".join(f"{s}  T4  RUNNING" for s in self.sessions) or "No active sessions found on server."
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

        if sub == "new":
            s_idx = cmd.index("-s") + 1
            name = cmd[s_idx]
            has_gpu = "--gpu" in cmd
            if has_gpu and not self.gpu_available:
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="400: No GPU quota available")
            self.sessions.append(name)
            return subprocess.CompletedProcess(cmd, 0, stdout="Session READY.", stderr="")

        if sub == "stop":
            s_idx = cmd.index("-s") + 1
            name = cmd[s_idx]
            if name in self.sessions:
                self.sessions.remove(name)
            self.stopped_sessions.append(name)
            return subprocess.CompletedProcess(cmd, 0, stdout="Session terminated.", stderr="")

        if sub == "upload":
            local_p, remote_p = Path(cmd[4]), cmd[5]
            self.remote_files[remote_p] = local_p.read_bytes()
            return subprocess.CompletedProcess(cmd, 0, stdout="Uploaded.", stderr="")

        if sub == "download":
            remote_p, local_p = cmd[4], Path(cmd[5])
            data = self.remote_files[remote_p]
            if self.corrupt_download:
                data = data[:-5]
            local_p.write_bytes(data)
            return subprocess.CompletedProcess(cmd, 0, stdout="Downloaded.", stderr="")

        if sub == "exec":
            assert input is not None
            return self._handle_exec(cmd, input)

        raise AssertionError(f"Unexpected colab subcommand: {cmd}")

    def _emit_json(self, cmd: list[str], payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="__COLAB_MINERU_JSON__:" + json.dumps(payload) + "\n", stderr="")

    def _handle_exec(self, cmd: list[str], code: str) -> subprocess.CompletedProcess[str]:
        if "mkdir -p" in code or "rm -rf" in code:
            return self._emit_json(cmd, {"rc": 0, "stdout": "", "stderr": ""})

        if "command -v mineru && mineru version --json" in code:
            if self.mineru_installed:
                return self._emit_json(cmd, {"rc": 0, "stdout": json.dumps({"mineru_version": "4.2.2", "python_version": "3.12.3"}), "stderr": ""})
            return self._emit_json(cmd, {"rc": 1, "stdout": "", "stderr": "not found"})

        if "uv tool install" in code:
            self.mineru_installed = True
            return self._emit_json(cmd, {"rc": 0, "stdout": json.dumps({"mineru_version": "4.2.2", "python_version": "3.12.3"}), "stderr": ""})

        if "mineru-kit models verify" in code and "models download" not in code:
            return self._emit_json(cmd, {"rc": 0 if self.models_ready else 1, "stdout": "", "stderr": ""})

        if "mineru-kit models download" in code:
            self.models_ready = True
            return self._emit_json(cmd, {"rc": 0, "stdout": "ok", "stderr": ""})

        if "mineru server start" in code:
            self.server_healthy = True
            return self._emit_json(cmd, {"rc": 0, "stdout": "started", "stderr": ""})

        if "mineru server status --json" in code and "mineru list parses --json" not in code:
            status = {
                "running": self.server_healthy,
                "parse_server": {
                    "local": {
                        "healthy": self.server_healthy,
                        "managed_tier": "standard",
                        "supported_tiers": ["flash", "basic", "standard"] if self.server_healthy else [],
                    }
                },
            }
            return self._emit_json(cmd, {"rc": 0 if self.server_healthy else 1, "stdout": json.dumps(status), "stderr": ""})

        if "mineru list parses --json" in code:
            return self._emit_json(cmd, {"parse_server": {"local": {"healthy": self.server_healthy}}, "parses": "[]"})

        if "--no-wait --json" in code:
            pid = self.next_parse_id
            self.next_parse_id += 1
            pages = "all"
            if "--pages " in code:
                pages = code.split("--pages ")[1].split(" ")[0].strip("'\"")
            self.parses[pid] = {"id": pid, "pages": pages, "polls": 0}
            return self._emit_json(
                cmd,
                {
                    "rc": 0,
                    "stdout": json.dumps({"parse": {"status": "pending", "wait_parse_ids": [pid]}}),
                    "stderr": "",
                },
            )

        if "mineru show parse " in code:
            pid = int(code.split("mineru show parse ")[1].split(" ")[0])
            rec = self.parses[pid]
            rec["polls"] += 1
            if self.fail_all_parses or (self.fail_full_parse and rec["pages"] == "all"):
                return self._emit_json(
                    cmd,
                    {"rc": 0, "stdout": json.dumps({"id": pid, "status": "failed", "error_code": "parse_oom", "error_msg": "OOM"}), "stderr": ""},
                )
            return self._emit_json(
                cmd,
                {"rc": 0, "stdout": json.dumps({"id": pid, "status": "done", "error_code": None}), "stderr": ""},
            )

        if "--no-marker --output" in code:
            remote_md = code.split("--output ")[1].split("'")[0].split('"')[0].strip()
            pages = code.split("--pages ")[1].split(" ")[0].strip("'\"")
            content = f"# Section {pages}\n\nParsed body for pages {pages}.\n".encode("utf-8")
            self.remote_files[remote_md] = content
            return self._emit_json(cmd, {"rc": 0, "stdout": f"Written to {remote_md}", "stderr": "", "size": len(content)})

        if "pypdf.PdfReader" in code:
            return self._emit_json(cmd, {"pages": self.total_pages})

        if "merged = " in code:
            chunk_paths = [p for p in sorted(self.remote_files) if "/chunk_" in p]
            parts = [self.remote_files[p].decode("utf-8").strip() for p in chunk_paths]
            merged = ("\n\n".join(parts) + "\n").encode("utf-8")
            target = [line for line in code.splitlines() if "open(" in line and "'w'" in line][0].split("open(")[1].split(",")[0].strip("'\"")
            self.remote_files[target] = merged
            return self._emit_json(cmd, {"size": len(merged)})

        raise AssertionError(f"Unhandled exec payload:\n{code}")


class ColabMineruTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "Ousterhout - 2018 - A philosophy of software design.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 dummy content")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_slugify_and_output_resolution(self) -> None:
        self.assertEqual(
            cm.slugify_pdf_stem("Ousterhout - 2018 - A philosophy of software design"),
            "ousterhout-2018-a-philosophy-of-software-design",
        )
        self.assertEqual(cm.slugify_pdf_stem("设计哲学"), "设计哲学")

        out_dir = self.root / "papers" / "software-engineering"
        resolved_dir = cm.resolve_output_path(self.pdf, str(out_dir))
        self.assertEqual(resolved_dir, out_dir.resolve() / "ousterhout-2018-a-philosophy-of-software-design.md")

        resolved_file = cm.resolve_output_path(self.pdf, str(self.root / "custom.md"))
        self.assertEqual(resolved_file, (self.root / "custom.md").resolve())

        out_dir.mkdir(parents=True)
        self.assertEqual(
            cm.resolve_output_path(self.pdf, str(out_dir)),
            out_dir.resolve() / "ousterhout-2018-a-philosophy-of-software-design.md",
        )

    def test_managed_tier_and_chunks(self) -> None:
        self.assertIsNone(cm.managed_tier_for("flash"))
        self.assertEqual(cm.managed_tier_for("basic"), "basic")
        self.assertEqual(cm.managed_tier_for("standard"), "standard")
        self.assertEqual(cm.managed_tier_for("advanced"), "standard")
        self.assertEqual(cm.compute_page_chunks(85, 40), ["1-40", "41-80", "81-85"])
        self.assertEqual(cm.compute_page_chunks(41, 40), ["1-40", "41"])

    def test_happy_path_creates_and_stops_session(self) -> None:
        harness = FakeColabHarness()
        runner = cm.ColabRunner("colab", run_fn=harness)
        out_dir = self.root / "papers" / "software-engineering"
        cfg = cm.parse_args([str(self.pdf), str(out_dir), "--poll-interval", "0"])

        result = cm.run_pipeline(cfg, runner=runner)
        self.assertTrue(result.exists())
        self.assertIn("Parsed body for pages all.", result.read_text(encoding="utf-8"))
        self.assertEqual(len(harness.stopped_sessions), 1)
        self.assertEqual(harness.sessions, [])

    def test_overwrite_guard_and_force(self) -> None:
        target = self.root / "out.md"
        target.write_text("existing", encoding="utf-8")
        cfg = cm.parse_args([str(self.pdf), str(target)])
        with self.assertRaises(cm.ColabMineruError):
            cm.run_pipeline(cfg, runner=cm.ColabRunner("colab", run_fn=FakeColabHarness()))

        harness = FakeColabHarness()
        cfg_force = cm.parse_args([str(self.pdf), str(target), "--force", "--poll-interval", "0"])
        cm.run_pipeline(cfg_force, runner=cm.ColabRunner("colab", run_fn=harness))
        self.assertIn("Parsed body", target.read_text(encoding="utf-8"))

    def test_gpu_unavailable_fails_unless_allow_cpu(self) -> None:
        harness = FakeColabHarness(gpu_available=False)
        cfg = cm.parse_args([str(self.pdf), str(self.root / "out.md")])
        with self.assertRaises(cm.ColabMineruError):
            cm.run_pipeline(cfg, runner=cm.ColabRunner("colab", run_fn=harness))
        self.assertEqual(harness.stopped_sessions, [])

        cfg_cpu = cm.parse_args([str(self.pdf), str(self.root / "out.md"), "--allow-cpu", "--poll-interval", "0"])
        res = cm.run_pipeline(cfg_cpu, runner=cm.ColabRunner("colab", run_fn=harness))
        self.assertTrue(res.exists())

    def test_session_reuse_and_keep(self) -> None:
        harness = FakeColabHarness(existing_sessions=["my-vm"], mineru_preinstalled=True, server_prehealthy=True)
        cfg = cm.parse_args([str(self.pdf), str(self.root / "a.md"), "-s", "my-vm", "--keep", "--poll-interval", "0"])
        cm.run_pipeline(cfg, runner=cm.ColabRunner("colab", run_fn=harness))
        subcommands = [c[1] for c in harness.calls]
        self.assertNotIn("new", subcommands)
        self.assertNotIn("stop", subcommands)
        self.assertEqual(harness.sessions, ["my-vm"])

        # Prefix session name must not falsely match `my-vm-2`
        harness2 = FakeColabHarness(existing_sessions=["my-vm-2"], mineru_preinstalled=True, server_prehealthy=True)
        cfg2 = cm.parse_args([str(self.pdf), str(self.root / "b.md"), "-s", "my-vm", "--poll-interval", "0"])
        cm.run_pipeline(cfg2, runner=cm.ColabRunner("colab", run_fn=harness2))
        self.assertIn("new", [c[1] for c in harness2.calls])

    def test_pagination_fallback_merges_chunks(self) -> None:
        harness = FakeColabHarness(fail_full_parse=True, total_pages=90, mineru_preinstalled=True, server_prehealthy=True)
        out = self.root / "merged.md"
        cfg = cm.parse_args([str(self.pdf), str(out), "--chunk-size", "40", "--poll-interval", "0"])
        cm.run_pipeline(cfg, runner=cm.ColabRunner("colab", run_fn=harness))
        text = out.read_text(encoding="utf-8")
        self.assertIn("# Section 1-40", text)
        self.assertIn("# Section 41-80", text)
        self.assertIn("# Section 81-90", text)

    def test_error_stops_vm_by_default_and_keeps_with_flag(self) -> None:
        harness = FakeColabHarness(fail_all_parses=True, total_pages=30, mineru_preinstalled=True, server_prehealthy=True)
        cfg = cm.parse_args([str(self.pdf), str(self.root / "x.md"), "--poll-interval", "0"])
        with self.assertRaises(cm.ColabMineruError):
            cm.run_pipeline(cfg, runner=cm.ColabRunner("colab", run_fn=harness))
        self.assertEqual(len(harness.stopped_sessions), 1)

        harness_keep = FakeColabHarness(fail_all_parses=True, total_pages=30, mineru_preinstalled=True, server_prehealthy=True)
        cfg_keep = cm.parse_args([str(self.pdf), str(self.root / "x.md"), "--keep-on-error", "--poll-interval", "0"])
        with self.assertRaises(cm.ColabMineruError):
            cm.run_pipeline(cfg_keep, runner=cm.ColabRunner("colab", run_fn=harness_keep))
        self.assertEqual(harness_keep.stopped_sessions, [])
        self.assertEqual(len(harness_keep.sessions), 1)

    def test_download_byte_mismatch_fails_atomically(self) -> None:
        harness = FakeColabHarness(corrupt_download=True, mineru_preinstalled=True, server_prehealthy=True)
        out = self.root / "broken.md"
        cfg = cm.parse_args([str(self.pdf), str(out), "--poll-interval", "0"])
        with self.assertRaises(cm.ColabMineruError):
            cm.run_pipeline(cfg, runner=cm.ColabRunner("colab", run_fn=harness))
        self.assertFalse(out.exists())
        self.assertEqual(list(self.root.glob(".colab-mineru-*")), [])


if __name__ == "__main__":
    unittest.main()
