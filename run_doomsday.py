import os
import signal
import sys
import time

# Set up PYTHONPATH for all modules
ROOT = os.path.dirname(os.path.abspath(__file__))
for pkg in ["cortex", "adapters", "doomsday", "mesh", "compliance", "simulation", "evolution"]:
    sys.path.insert(0, os.path.join(ROOT, pkg))
sys.path.insert(0, ROOT)

from doomsday.config import DeadManConfig, EscalationStep, StepType
from doomsday.daemon import DeadManSwitchDaemon

config = DeadManConfig(
    heartbeat_interval_s=5.0,
    grace_multiplier=3,
    escalation_multiplier=6,
    escalation_enabled=True,
    abortable_until_step=2,
    liquidation_grace_multiplier=4,
    plan=[
        EscalationStep(step=StepType.NOTIFY, channels=["ops-slack"]),
        EscalationStep(step=StepType.HALT_PLACEMENTS),
        EscalationStep(step=StepType.REDUCE_EXPOSURE, target_percentage=50.0),
        EscalationStep(step=StepType.ACQUIRE_ASSETS, asset_out="USDC", via="simulation_oracle"),
        EscalationStep(step=StepType.SEAL),
    ],
    oracle="simulation_oracle",
    strict_heartbeat_signing=False,
    max_journal_entries=2048,
)

daemon = DeadManSwitchDaemon(config=config)
daemon.start(tick_interval_s=1.25)
daemon.beat()

print(f"DoM: daemon running in {daemon.state}", flush=True)
print(f"  heartbeat interval: {config.heartbeat_interval_s}s", flush=True)
print(f"  grace period: {config.grace_period}s", flush=True)
print(f"  escalation period: {config.escalation_period}s", flush=True)
print(f"  plan steps: {len(config.plan)}", flush=True)

running = True
def handle_signal(signum, frame):
    global running
    running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

while running:
    time.sleep(1.0)
    daemon.beat()

print("\nDoM: stopping...", flush=True)
daemon.stop()
print("DoM: stopped.", flush=True)
