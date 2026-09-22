import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import ClassVar


class EvolutionaryCodeAgent:
    """
    Manages codebase entropy, identifies compiler or runtime obsolescence,
    and stages self-generated refactoring patches.

    Genesis DNA (G2 — self-evolution framework): this is the *machinery* that
    reads code, runs tests/provers, and merges patches. It does NOT contain
    trading strategy or venue logic itself — it only produces/refactors the
    scaffolding that other Genesis components own.
    """

    ERROR_PATTERNS: ClassVar[list[tuple[re.Pattern, str]]] = [
        (re.compile(r"Traceback \(most recent call last\)"), "python_traceback"),
        (re.compile(r"SyntaxError|TypeError|AttributeError|ValueError|KeyError|ImportError|NameError|RuntimeError|PermissionError|TimeoutError|ConnectionRefusedError|ConnectionResetError|FileNotFoundError|ZeroDivisionError"), "python_exception"),
        (re.compile(r"Failed|Error|Panic|panic|CRITICAL|FATAL", re.IGNORECASE), "generic_error"),
        (re.compile(r"MalformedEnvelope|MalformedFrame|oversized_frame|version_mismatch"), "ipc_protocol_error"),
        (re.compile(r"MaxDrawdown|EmergencyHalt|liquidation"), "risk_violation"),
        (re.compile(r"bind|address already in use|EADDRINUSE"), "port_conflict"),
    ]

    # Log lines emitted by the scan/report machinery itself must never be
    # re-matched as errors — that would make the log scan self-feeding.
    _SELF_MARKERS: ClassVar[tuple[str, ...]] = (
        "Log Scan:",
        "[generic_error]",
        "[SKIP]",
        "Healing history:",
        "Cannot infer target file from:",
    )
    _LINE_TS_RE: ClassVar[re.Pattern] = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.patches_dir = self.workspace_root / "evolution" / "patches"
        self.healing_log = self.workspace_root / "logs" / "healing.jsonl"

    def stage_patch(self, file_path: str, proposed_content: str, reason: str) -> str:
        patch_id = hashlib.sha256(proposed_content.encode("utf-8")).hexdigest()[:12]
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        patch_filename = self.patches_dir / f"patch_{patch_id}.diff"

        metadata = f"# REASON: {reason}\n# TARGET: {file_path}\n\n"
        patch_filename.write_text(metadata + proposed_content, encoding="utf-8")

        print(f"Staged evolutionary patch [{patch_id}] for target: {file_path}")
        return patch_id

    def apply_patch(self, file_path: str, patch_content: str, run_tests: bool = True) -> bool:
        """Apply a staged patch to a file and optionally run tests to validate.

        Returns True if the patch was applied and tests passed.
        """
        target = self.workspace_root / file_path
        if not target.exists():
            self._log_healing(file_path, "SKIP", "File not found")
            return False

        original = target.read_text(encoding="utf-8")
        backup = self.workspace_root / "evolution" / "patches" / f"backup_{hashlib.sha256(str(target).encode()).hexdigest()[:8]}.bak"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(original, encoding="utf-8")

        try:
            target.write_text(patch_content, encoding="utf-8")
            if run_tests:
                ok = self._run_validation(file_path)
                if not ok:
                    target.write_text(original, encoding="utf-8")
                    self._log_healing(file_path, "ROLLBACK", "Tests failed after patch")
                    return False
            self._log_healing(file_path, "APPLIED", "Patch applied successfully")
            return True
        except Exception as e:  # noqa: BLE001 - patch application error, rollback
            target.write_text(original, encoding="utf-8")
            self._log_healing(file_path, "ROLLBACK", f"Exception: {e}")
            return False

    def _run_validation(self, file_path: str) -> bool:
        """Run compile + targeted tests to validate a patch."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", file_path],
                capture_output=True, text=True, timeout=30,
                check=False, cwd=str(self.workspace_root),
            )
            if result.returncode != 0:
                return False

            test_files = list(self.workspace_root.rglob(f"test_*{Path(file_path).stem}*.py"))
            for test_file in test_files:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(test_file), "-q"],
                    capture_output=True, text=True, timeout=60,
                    check=False, cwd=str(self.workspace_root),
                )
                if result.returncode != 0:
                    return False
            return True
        except Exception:  # noqa: BLE001 - validation failure means patch rejected
            return False

    def _log_healing(self, file_path: str, action: str, detail: str) -> None:
        """Append a healing action to the structured healing log."""
        self.healing_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": time.time(),
            "file": file_path,
            "action": action,
            "detail": detail,
        }
        with open(self.healing_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _ts_to_epoch(self, ts: str) -> float:
        """Best-effort parse of the ISO `YYYY-MM-DDTHH:MM:SS` log prefix."""
        try:
            return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            return float("inf")

    def scan_logs_for_errors(self, log_dir: Path, since_seconds: float = 300) -> list[dict]:
        """Scan log files for error patterns in the last N seconds.

        Returns a list of detected errors with pattern type and context.
        """
        cutoff = time.time() - since_seconds
        errors = []

        if not log_dir.exists():
            return errors

        for log_file in log_dir.glob("*.log"):
            if log_file.name.endswith(".rotated.log"):
                continue
            try:
                stat = log_file.stat()
                if stat.st_mtime < cutoff:
                    continue
                content = log_file.read_text(encoding="utf-8", errors="replace")
                lines = content.strip().split("\n") if content else []

                for line in lines[-1000:]:
                    ts_hit = self._LINE_TS_RE.match(line)
                    if ts_hit and ts_hit.group(1) and self._ts_to_epoch(ts_hit.group(1)) < cutoff:
                        continue
                    if any(marker in line for marker in self._SELF_MARKERS):
                        continue
                    for pattern, label in self.ERROR_PATTERNS:
                        if pattern.search(line):
                            errors.append({
                                "file": str(log_file.name),
                                "pattern": label,
                                "line": line.strip()[:200],
                                "timestamp": stat.st_mtime,
                            })
                            break
            except Exception:  # noqa: BLE001, S112 - skip unreadable log files, log recursion risk
                continue
        return errors

    def propose_fix(self, error: dict, file_to_fix: str | None = None) -> str | None:
        """Given an error from scan_logs_for_errors, propose a self-healing patch.

        This is the Genesis mechanism for autonomous repair. It:
        1. Identifies the source file from the error context.
        2. Reads the current content.
        3. Propagates the file with a simple fix (e.g., add a missing import,
           add a None guard, retry a connection).
        4. Stages the patch via stage_patch.
        5. If sandbox tests pass, applies the fix.

        Returns the patch_id if a fix was staged, None otherwise.
        """

        error.get("file", "")
        pattern = error.get("pattern", "")
        error_line = error.get("line", "")

        # Skip errors that require human judgment (risk violations, governance)
        if pattern in ("risk_violation",):
            self._log_healing("unknown", "SKIP", f"Risk violation — requires human quorum: {error_line[:80]}")
            return None

        # Determine target file
        if file_to_fix:
            target = self.workspace_root / file_to_fix
        else:
            # Try to infer from the error line
            match = re.search(r'([a-zA-Z_][a-zA-Z0-9_/]*\.py)', error_line)
            if match:
                target = self.workspace_root / match.group(1)
            else:
                self._log_healing("unknown", "SKIP", f"Cannot infer target file from: {error_line[:80]}")
                return None

        if not target.exists():
            self._log_healing(str(target), "SKIP", "Target file not found")
            return None

        content = target.read_text(encoding="utf-8")
        original = content
        reason = f"Auto-fix for {pattern}: {error_line[:80]}"

        # Pattern-specific fixes
        if pattern == "ImportError" or "ImportError" in error_line:
            # Try to add missing import
            module_match = re.search(r"No module named '([^']+)'", error_line)
            if module_match:
                mod = module_match.group(1)
                # Simple heuristic: add import at the top
                content = f"import {mod}\n" + content
        elif pattern == "NameError":
            var_match = re.search(r"name '([^']+)' is not defined", error_line)
            if var_match:
                var = var_match.group(1)
                content = f"{var} = None  # auto-init\n" + content
        elif pattern == "port_conflict":
            # Retry with a different port
            port_match = re.search(r"(\d{4,5})", error_line)
            if port_match:
                port = int(port_match.group(1)) + 1
                content = content.replace(
                    f":{port - 1}",
                    f":{port}",
                    1,
                ) if f":{port - 1}" in content else content
        else:
            # Generic: add a retry wrapper
            if "try:" not in content[:200] and "def main" in content:
                # Wrap main call in retry
                content = content.replace(
                    "main()",
                    "for attempt in range(3):\n"
                    "    try:\n"
                    "        main()\n"
                    "        break\n"
                    "    except Exception:\n"
                    "        import time; time.sleep(2)\n",
                    1,
                )

        if content != original:
            patch_id = self.stage_patch(str(target.relative_to(self.workspace_root)), content, reason)
            return patch_id

        self._log_healing(str(target), "SKIP", f"No auto-fix pattern matched for {pattern}")
        return None

    def healing_history(self) -> list[dict]:
        """Return the structured healing log as a list of dicts."""
        if not self.healing_log.exists():
            return []
        entries = []
        for line in self.healing_log.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries
