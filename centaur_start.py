#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Centaur-Apex Core — Single-Command Production Server                        ║
║  Starts ALL services with auto-restart, structured logging, and health         ║
║  monitoring. Designed to run indefinitely (100-year autonomous operation).   ║
║                                                                              ║
║  Usage:                                                                     ║
║    python centaur_start.py                  # start all services              ║
║    python centaur_start.py --stop           # stop all services               ║
║    python centaur_start.py --status         # health status                   ║
║    python centaur_start.py --logs           # stream all logs                 ║
║                                                                              ║
║  Logs: /var/log/centaur/  (or ./logs/ if no permissions)                      ║
║  Env:  Set CONSTITUTION_HOST/PORT, TRADING_ASSET, TRADING_EQUITY           ║
╚══════════════════════════════════════════════════════════════════════════════╝

This is the orchestrator (GENESIS: bootstrap tooling G9). It manages the full
lifecycle of:

  1. constitutiond   — Rust risk kernel (G1)
  2. doomsday        — Dead-man switch (G6)
  3. trading-daemon  — Cortex continuous trading loop (G5)
  4. mesh-node-0/1/2 — 3x EdgeNodeDaemon for BFT quorum (G4)
  5. evolution       — Self-upgrade agent (G2)
  6. compliance      — Governance auditor (G6)

All processes are monitored and restarted on crash. Health is logged every
30s. Graceful shutdown on SIGTERM/SIGINT. The log-scanner runs every
30s and triggers self-healing via the EvolutionaryCodeAgent (G2).
"""
import argparse
import json
import logging
import os
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

# ── Encoding guard ───────────────────────────────────────────────────────────
# Box-drawing log decoration (── ──) and non-ASCII service names must not crash
# the console/file handlers on cp1252 (Windows) or other non-UTF-8 locales.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
RUST_RELEASE = str(ROOT / "constitution" / "target" / "release")
CONSTITUTIOND = str(Path(RUST_RELEASE) / ("constitutiond.exe" if os.name == "nt" else "constitutiond"))
CONSTITUTION_CLI = str(Path(RUST_RELEASE) / ("constitution_cli.exe" if os.name == "nt" else "constitution_cli"))

# ── Python path setup ───────────────────────────────────────────────────────
# Mirror conftest.py: the orchestrator process itself must be able to import
# the six packages (self-healing log scan imports evolution.code_agent).
PACKAGE_HOMES = ["cortex", "adapters", "doomsday", "mesh", "compliance", "simulation", "evolution"]
for _pkg_home in PACKAGE_HOMES:
    _home = str(ROOT / _pkg_home)
    if _home not in sys.path:
        sys.path.insert(0, _home)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Child processes receive the same package homes via PYTHONPATH. os.pathsep
# matters: ":" is NOT a path separator on Windows, so ":"-joined PYTHONPATH
# silently fails to resolve any import there.
PYYPATH = os.pathsep.join(str(ROOT / pkg) for pkg in PACKAGE_HOMES) + os.pathsep + str(ROOT)

# ── Logging ─────────────────────────────────────────────────────────────────
LOG_DIR = Path(os.environ.get("LOG_DIR", ROOT / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "centaur.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("Orchestrator")


def _logfh(name: str):
    """Open a log file handle for subprocess stdout (owned by subprocess lifecycle)."""
    return open(LOG_DIR / f"{name}.log", "a")


def _constitution_port() -> int:
    return int(os.environ.get("CONSTITUTION_PORT", "15565"))


def _probe_constitution(timeout_s: float = 1.5) -> bool:
    """One framed IPC Heartbeat against constitutiond; True when alive.

    Module-level so both the orchestrator health check and the standalone
    Doomsday service can use the same protocol-correct probe.
    """
    payload = json.dumps(
        {
            "protocol_version": 1,
            "request_id": "hc",
            "opcode": "Heartbeat",
            "payload": "{}",
        }
    ).encode("utf-8")
    try:
        with socket.create_connection(("127.0.0.1", _constitution_port()), timeout=timeout_s) as sock:
            sock.sendall(struct.pack(">I", len(payload)) + payload)
            header = sock.recv(4)
            if len(header) != 4:
                return False
            frame_len = struct.unpack(">I", header)[0]
            if frame_len == 0 or frame_len > 16384:
                return False
            resp = b""
            while len(resp) < frame_len:
                chunk = sock.recv(frame_len - len(resp))
                if not chunk:
                    break
                resp += chunk
        return b'"alive":true' in resp
    except (OSError, ValueError):
        return False


# ── Service runners ─────────────────────────────────────────────────────────
def _run_constitutiond():
    """G1: Iron Constitution risk kernel."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PYYPATH
    proc = subprocess.Popen(
        [CONSTITUTIOND],
        stdout=_logfh("constitutiond"),
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
    )
    return proc


def _run_trading_daemon():
    """G5: Continuous Cortex trading loop (native run_loop) fed by the synthetic feed.

    The market feed is a separate producer (G7 placeholder; real venue feeds are
    S1 adapter plugins). The daemon consumes JSON lines on stdin — the protocol
    contract it was built around. The feed is tracked so shutdown kills both.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = PYYPATH
    code = """import os
from cortex.trading_daemon import TradingDaemon
daemon = TradingDaemon(
    asset_id=os.environ.get('TRADING_ASSET', 'EURUSD'),
    constitution_host=os.environ.get('CONSTITUTION_HOST', '127.0.0.1'),
    constitution_port=int(os.environ.get('CONSTITUTION_PORT', '15565')),
    equity=float(os.environ.get('TRADING_EQUITY', '100000')),
    heartbeat_interval_s=5.0,
    tick_interval_s=5.0,
)
daemon.start()
daemon.run_loop()
"""
    feed = subprocess.Popen(
        [PYTHON, str(ROOT / "market_feed.py")],
        stdout=subprocess.PIPE,
        cwd=str(ROOT),
        env=env,
    )
    proc = subprocess.Popen(
        [PYTHON, "-c", code],
        stdin=feed.stdout,
        stdout=_logfh("trading-daemon"),
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
    )
    proc._feed = feed  # type: ignore[attr-defined]
    return proc


def _run_doomsday():
    """G6: Doomsday dead-man switch, fed by the Constitution liveness probe.

    Beats fire only while the Constitution risk kernel answers its IPC heartbeat;
    if the kernel goes silent, Doomsday stops beating and its FSM escalates
    (fail-safe: no constitutional safety -> graceful wind-down path).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = PYYPATH
    code = """import os
import signal
import time
from doomsday.daemon import DeadManSwitchDaemon
from doomsday.config import DeadManConfig, EscalationStep, StepType
from centaur_start import _probe_constitution
config = DeadManConfig(
    heartbeat_interval_s=5.0,
    grace_multiplier=3,
    escalation_multiplier=6,
    escalation_enabled=True,
    abortable_until_step=2,
    liquidation_grace_multiplier=4,
    plan=[
        EscalationStep(step=StepType.NOTIFY, channels=['ops']),
        EscalationStep(step=StepType.HALT_PLACEMENTS),
        EscalationStep(step=StepType.REDUCE_EXPOSURE, target_percentage=50.0),
        EscalationStep(step=StepType.ACQUIRE_ASSETS, asset_out='USDC', via='simulation_oracle'),
        EscalationStep(step=StepType.SEAL),
    ],
    oracle='simulation_oracle',
    strict_heartbeat_signing=False,
    max_journal_entries=2048,
)
daemon = DeadManSwitchDaemon(config=config)
daemon.start(tick_interval_s=1.25)
running = True
def h(s, f):
    global running
    running = False
signal.signal(signal.SIGTERM, h)
signal.signal(signal.SIGINT, h)
print(f'[DoM] monitoring constitution heartbeat; state={daemon.state}', flush=True)
while running:
    if _probe_constitution():
        daemon.beat()
    time.sleep(1.0)
daemon.stop()
print('[DoM] stopped.', flush=True)
"""
    proc = subprocess.Popen(
        [PYTHON, "-c", code],
        stdout=_logfh("doomsday"),
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
    )
    return proc


def _run_mesh_node(node_id: str, port: int):
    """G4: Edge mesh node with BFT state sync."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PYYPATH
    code = """import os
import time
from mesh.node_daemon import EdgeNodeDaemon
_d = EdgeNodeDaemon(node_id='NODE_ID')
_d.start_heartbeat()
print(f'[Mesh] {_d.node_id} online at {_d.ws_url}', flush=True)
while True:
    time.sleep(60)
    print(f'[Mesh] {_d.node_id} health: {_d.health_telemetry()}', flush=True)
""".replace("NODE_ID", node_id)
    proc = subprocess.Popen(
        [PYTHON, "-c", code],
        stdout=_logfh(f"mesh-{node_id}"),
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
    )
    return proc


def _run_evolution():
    """G2: Self-evolution agent (hourly assessment cycle)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PYYPATH
    code = """import os
import time
print('[Evolution] self-evolution agent online', flush=True)
while True:
    time.sleep(3600)
    print('[Evolution] hourly self-assessment cycle', flush=True)
"""
    proc = subprocess.Popen(
        [PYTHON, "-c", code],
        stdout=_logfh("evolution"),
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
    )
    return proc


def _run_compliance():
    """G6: Compliance auditor (5-min cycle)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PYYPATH
    code = """import os
import time
from compliance.governance.multisig_dao import CryptographicGovernanceDAO
from compliance.tax_parser import GlobalTaxRegulatoryParser
from compliance.structural_shift import JurisdictionalRoutingEngine
print('[Compliance] governance auditor online', flush=True)
while True:
    time.sleep(300)
    print('[Compliance] audit cycle', flush=True)
"""
    proc = subprocess.Popen(
        [PYTHON, "-c", code],
        stdout=_logfh("compliance"),
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
        env=env,
    )
    return proc


# ── Service definitions ─────────────────────────────────────────────────────
SERVICES = [
    {"name": "constitution",   "runner": _run_constitutiond,  "restart": True,
     "depends_on": []},
    {"name": "doomsday",       "runner": _run_doomsday,       "restart": True,
     "depends_on": ["constitution"]},
    {"name": "trading-daemon", "runner": _run_trading_daemon, "restart": True,
     "depends_on": ["constitution", "doomsday"]},
    {"name": "mesh-0",         "runner": lambda: _run_mesh_node("mesh-0", 8765), "restart": True,
     "depends_on": ["constitution"]},
    {"name": "mesh-1",         "runner": lambda: _run_mesh_node("mesh-1", 8766), "restart": True,
     "depends_on": ["constitution", "mesh-0"]},
    {"name": "mesh-2",         "runner": lambda: _run_mesh_node("mesh-2", 8767), "restart": True,
     "depends_on": ["constitution", "mesh-0", "mesh-1"]},
    {"name": "evolution",      "runner": _run_evolution,      "restart": True,
     "depends_on": ["constitution"]},
    {"name": "compliance",     "runner": _run_compliance,     "restart": True,
     "depends_on": ["constitution"]},
]

# ── Orchestrator ────────────────────────────────────────────────────────────
class _AdoptedDaemon:
    """Pseudo-process handle for a constitutiond the orchestrator did not spawn.

    poll() reflects the daemon's LIVE health (via the IPC heartbeat), so the
    monitor loop can still detect and restart it if the external daemon dies.
    terminate()/wait() are no-ops: the process is not ours to signal.
    """

    def __init__(self, pid: int, health_probe) -> None:
        self.pid = pid
        self.returncode = None
        self._health_probe = health_probe

    def poll(self):
        return None if self._health_probe(2) else -1

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout=None):
        return None


class Orchestrator:
    def __init__(self):
        self.processes: dict[str, subprocess.Popen] = {}
        self.restart_counts: dict[str, int] = {}
        self._running = True
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum=None, frame=None):
        log.info(f"Shutting down orchestrator (signal {signum})...")
        self._running = False

    def _wait_for_constitutiond(self, timeout: int = 30) -> bool:
        """Health-check the Constitution daemon via framed IPC heartbeat."""
        for _ in range(timeout):
            if _probe_constitution():
                return True
            time.sleep(1)
        return False

    @staticmethod
    def _constitution_owner_pid() -> int:
        """Best-effort PID of the process bound to the constitution port (0 if unknown)."""
        try:
            proc = (
                subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if os.name == "nt"
                else subprocess.run(
                    ["ss", "-tlnp"], capture_output=True, text=True, timeout=10, check=False
                )
            )
            port = int(os.environ.get("CONSTITUTION_PORT", "15565"))
            for line in (proc.stdout or "").splitlines():
                if f":{port} " not in line:
                    continue
                if os.name == "nt" and "LISTENING" not in line:
                    continue
                tokens = line.split()
                pid_token = tokens[-1] if os.name == "nt" else tokens[-1].split("pid=")[-1].split(",")[0]
                return int(pid_token) if pid_token.isdigit() else 0
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return 0

    def _can_start(self, svc: dict) -> bool:
        """Check if all dependencies are running."""
        for dep in svc["depends_on"]:
            if dep == "constitution":
                return self._wait_for_constitutiond(5)
            if dep not in self.processes or self.processes[dep].poll() is not None:
                return False
        return True

    def _start_service(self, svc: dict) -> bool:
        name = svc["name"]
        try:
            if name == "constitution":
                adopted = self._adopt_existing_constitutiond()
                if adopted is not None:
                    self.processes[name] = adopted
                    self.restart_counts[name] = 0
                    log.warning(
                        "  [ADOPTED] constitution — a healthy constitutiond is already on the port "
                        f"(pid={adopted.pid}); its process is OUTSIDE orchestrator control. "
                        "To run a managed kernel, stop it first, e.g. `taskkill /F /PID %s` (admin), then relaunch.",
                        adopted.pid,
                    )
                    return True
            proc = svc["runner"]()
            self.processes[name] = proc
            self.restart_counts[name] = 0
            log.info(f"  [STARTED] {name} (pid={proc.pid})")
            return True
        except Exception as e:  # noqa: BLE001 - orchestrator must not crash on service start failure
            log.error(f"  [FAILED]  {name}: {e}")
            return False

    def _adopt_existing_constitutiond(self):
        """Adopt an already-running healthy constitutiond instead of crash-looping on its port."""
        if self._wait_for_constitutiond(2):
            owner = self._constitution_owner_pid()
            return _AdoptedDaemon(owner, self._wait_for_constitutiond)
        return None

    def _check_restart(self, name: str, proc: subprocess.Popen, svc: dict):
        """Restart a crashed service (max 10 restarts)."""
        if proc.poll() is not None:
            self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
            if self.restart_counts[name] > 10:
                log.error(f"  [DEAD]    {name} — exceeded 10 restarts, NOT restarting")
                return
            log.warning(f"  [CRASHED] {name} (exit code {proc.returncode}) — restart #{self.restart_counts[name]}")
            self._kill_feed(proc)
            if svc["restart"] and self._can_start(svc):
                proc = svc["runner"]()
                self.processes[name] = proc
                log.info(f"  [RESTARTED] {name} (pid={proc.pid})")

    @staticmethod
    def _rotate_service_logs():
        """Rotate per-service log spools at boot (mechanism, not content-aware).

        Service stdout (trading/doomsday/mesh/...) is unstamped raw child output,
        so the self-healing scanner cannot time-filter it — rotating at boot keeps
        the scanner's baseline fresh every restart. `centaur.log` is skipped
        (locked by our own FileHandler; its lines carry parseable timestamps).
        Locked files are skipped silently — rotation is best-effort hygiene.
        """
        stamp = time.strftime("%Y%m%dT%H%M%S")
        rotated_stems: set[str] = set()
        for log_file in sorted(LOG_DIR.glob("*.log")):
            if log_file.name == "centaur.log":
                continue
            dest = LOG_DIR / f"{log_file.stem}.{stamp}.rotated.log"
            try:
                log_file.rename(dest)
            except OSError:
                continue
            rotated_stems.add(log_file.stem)

        # keep only the last 3 generations per service
        for stem in rotated_stems:
            gens = sorted(LOG_DIR.glob(f"{stem}.*.rotated.log"), key=lambda p: p.stat().st_mtime)
            for old in gens[:-3]:
                try:
                    old.unlink()
                except OSError:
                    pass

    def run(self):
        log.info("=" * 72)
        log.info("Centaur-Apex Core Orchestrator — starting all Genesis services")
        log.info(f"  ROOT: {ROOT}")
        log.info(f"  LOG:  {LOG_DIR}")
        log.info(f"  PYTHONPATH: {PYYPATH[:80]}...")
        log.info("=" * 72)

        self._rotate_service_logs()

        # Start constitutiond first
        if not self._start_service(SERVICES[0]):
            log.error("FATAL: constitutiond failed to start. Aborting.")
            return 1

        # Wait for constitutiond health
        log.info("  Waiting for constitutiond health check...")
        if not self._wait_for_constitutiond(30):
            log.error("FATAL: constitutiond did not become healthy. Aborting.")
            return 1
        log.info("  constitutiond is healthy")

        # Start remaining services in dependency order
        for svc in SERVICES[1:]:
            if self._can_start(svc):
                self._start_service(svc)
            else:
                log.warning(f"  [SKIP] {svc['name']} — dependencies not ready (will retry)")

        log.info("All services started. Monitoring...\n")

        # Print service status
        self._print_status()

        # Main monitoring loop
        tick = 0
        while self._running:
            time.sleep(5)
            tick += 1

            # Check all processes for crashes
            for svc in SERVICES:
                name = svc["name"]
                if name in self.processes:
                    self._check_restart(name, self.processes[name], svc)

            # Health report every 30s (6 ticks)
            if tick % 6 == 0:
                self._health_report()
                # G2: Self-healing log scan
                self._scan_and_heal()

            # Retry starting skipped services every 60s (12 ticks)
            if tick % 12 == 0:
                self._retry_skipped_services()

        self._stop_all()
        return 0

    def _print_status(self):
        log.info("── Service Status ──")
        for name, proc in self.processes.items():
            status = "RUNNING" if proc.poll() is None else f"EXITED({proc.returncode})"
            log.info(f"  {name:<16} pid={proc.pid:<8} {status}")

    def _health_report(self):
        log.info("── Health Report ──")
        for name, proc in list(self.processes.items()):
            if proc.poll() is None:
                log.info(f"  {name:<16} HEALTHY (pid={proc.pid})")
            else:
                log.warning(f"  {name:<16} DOWN (exit={proc.returncode})")

    def _scan_and_heal(self):
        """G2: Scan logs for errors and trigger self-healing via Evolution Sub-Agent."""
        from evolution.code_agent import EvolutionaryCodeAgent

        agent = EvolutionaryCodeAgent(workspace_root=str(ROOT))
        errors = agent.scan_logs_for_errors(LOG_DIR, since_seconds=300)

        if not errors:
            log.info("── Log Scan: clean (0 errors in last 5min) ──")
            return

        log.warning(f"── Log Scan: {len(errors)} error(s) detected in last 5min ──")

        for err in errors[:5]:  # process top 5 most recent
            log.warning(f"  [{err['pattern']}] {err['file']}")
            patch_id = agent.propose_fix(err)
            if patch_id:
                log.info(f"  [HEAL]     Staged patch[{patch_id}] for self-repair")
            elif err["pattern"] == "risk_violation":
                log.info("  [SKIP]     Risk violation requires quorum approval (I7)")
            elif err["pattern"] == "ipc_protocol_error":
                log.warning("  [SKIP]     IPC error — restarting relevant service")
                for svc in SERVICES:
                    if svc["name"] == "constitution" and self._can_start(svc):
                        log.info("  [RESTART] constitution")
                        self._start_service(svc)
            else:
                log.info("  [SKIP]     No auto-fix pattern matched")

        history = agent.healing_history()
        if history:
            log.info(f"  Healing history: {len(history)} entries")
            for h in history[-3:]:
                log.info(f"    [{h['action']}] {h['file']}: {h['detail'][:60]}")

    @staticmethod
    def _kill_feed(proc):
        """Terminate a surviving paired feed producer (trading daemon's market feed)."""
        feed = getattr(proc, "_feed", None)
        if feed is not None and feed.poll() is None:
            try:
                feed.terminate()
                feed.wait(timeout=3)
            except Exception:  # noqa: BLE001 - best-effort feed cleanup
                feed.kill()

    def _stop_all(self):
        log.info("Stopping all services...")
        for name, proc in self.processes.items():
            self._kill_feed(proc)
            try:
                proc.terminate()
                proc.wait(timeout=5)
                log.info(f"  {name}: stopped")
            except Exception:  # noqa: BLE001 - graceful shutdown must not hang
                proc.kill()
                log.info(f"  {name}: killed")

    def _retry_skipped_services(self):
        """Retry starting services that were skipped on initial start."""
        for svc in SERVICES[1:]:  # skip constitution (already started)
            name = svc["name"]
            if (name not in self.processes or self.processes[name].poll() is not None) and self._can_start(svc):
                log.info(f"  [RETRY]    {name} — dependencies now available")
                self._start_service(svc)
                self.restart_counts[name] = 0

    def _cmd_status(self):
        """Print current service status (for --status flag)."""
        print("Centaur-Apex Core — Service Status")
        print("=" * 50)
        for name in [s["name"] for s in SERVICES]:
            proc = self.processes.get(name)
            if proc and proc.poll() is None:
                print(f"  {name:<16} RUNNING (pid={proc.pid})")
            else:
                print(f"  {name:<16} STOPPED")

    def _cmd_stop(self):
        """Stop all running services."""
        print("Stopping all Centaur-Apex services...")
        for name, proc in list(self.processes.items()):
            self._kill_feed(proc)
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"  {name}: stopped")
            except Exception:  # noqa: BLE001 - best-effort stop
                proc.kill()
                print(f"  {name}: killed")
        print("All services stopped.")


def main():
    parser = argparse.ArgumentParser(description="Centaur-Apex Core orchestrator")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    parser.add_argument("--status", action="store_true", help="Show service status")
    parser.add_argument("--logs", action="store_true", help="Tail all logs")
    args = parser.parse_args()

    orch = Orchestrator()

    if args.status:
        orch._cmd_status()
        return 0

    if args.stop:
        orch._cmd_stop()
        return 0

    if args.logs:
        subprocess.run(["tail", "-f", str(LOG_DIR / "centaur.log")], check=False)
        return 0

    return orch.run()


if __name__ == "__main__":
    raise SystemExit(main())
