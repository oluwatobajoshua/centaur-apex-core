# Runbook — Centaur-Apex Core

**System:** Centaur-Apex Core
**Support:** See `SUPPORT.md` | **Security findings:** See `SECURITY.md`

---

## Port map

| Service | Port | Protocol | Binding |
|---------|------|----------|---------|
| `constitutiond` | 15565 | TCP (length-prefixed JSON framing) | 127.0.0.1 |

---

## Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Rust/cargo | ≥ 1.7x | `C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe` (not on PATH; use full path) |
| Python | 3.11+ | `C:\Python314\python.exe`; packages: `pydantic`, `numpy`, `pandas`, `requests` |
| Node/npm | 18+ | For `gateway/` only |
| OS | Windows 10+ (current); Linux/macOS supported by Rust crate |

---

## Starting the system

### Start constitutiond (Rust daemon)

```powershell
C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe run --release --manifest-path constitution/Cargo.toml --bin constitutiond
```

Confirm it is listening:
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 15565
```

### Run the live E2E pipeline

```powershell
python run_pipeline.py
```

This will auto-start `constitutiond` if it is not running. The pipeline runs
three market scenarios through the Cortex engine and the Rust Constitution.

### Run the Chronos integration test (250 years)

```powershell
python simulation/tests/integration_chronos.py
```

Output should end with:
```json
{
  "passed": true,
  "final_equity": 237028.8,
  ...
}
```

### Start the NestJS gateway

```powershell
npm install --prefix gateway
npm run build --prefix gateway
$env:CONSTITUTION_BRIDGE = "tcp"   # or "cli" for constitution_cli transport
npm run start --prefix gateway
```

- REST: `GET /constitution/status`, `POST /constitution/evaluate`,
  `GET /cortex/propose?price=...&equity=...`
- OpenAPI docs: `http://localhost:3000/docs` (also `/docs-json`)
- Tests: `npm run test:unit` / `npm run test:e2e` (from `gateway/`)

---

## IPC testing (quick)

### Heartbeat via constitution_cli

```powershell
'{"protocol_version":1,"request_id":"t","opcode":"Heartbeat","payload":"{}"}' | & "constitution\target\release\constitution_cli.exe"
```

Expected: `{"alive":true,"protocol_version":1}`

### Evaluate proposal via Python

```python
from cortex.constitution_client import ConstitutionIPCClient
with ConstitutionIPCClient(timeout=2.0) as client:
    client.open_session()
    resp = client.evaluate(portfolio, proposal)
    print(resp)
```

---

## Operations & monitoring

| State | Meaning | What to do |
|-------|---------|------------|
| `Normal` | System evaluating proposals normally | Monitor |
| `SoftDeleveraging` | Drawdown ≥ 80% of threshold; new positions rejected | Monitor; system is protecting capital |
| `EmergencyHalt` | Drawdown threshold breached; system halted | Investigate; initiate recovery via `AttemptRecovery` with valid cryptographic proof |
| `AutonomousRecovery` | Recovery in progress; awaiting diagnostic pass | Wait for state transition |

Current system status can be queried:
```python
client.status()  # Returns {"system_state": "Normal", "proposals_seen": ..., "emergencies": ...}
```

---

## Recovery procedures

### System stuck in EmergencyHalt

1. Verify the market event that caused the breach is genuinely over.
2. Generate a cryptographic proof-of-legitimacy (process TBD during Genesis Ceremony).
3. Send `AttemptRecovery` with `cryptographic_proof_valid: true` — this moves
   `EmergencyHalt → AutonomousRecovery` (phase 1 of 2).
4. After the diagnostic pass in `AutonomousRecovery`, send a **second** valid
   `AttemptRecovery` to reach `Normal` (phase 2 of 2).
5. Invalid proofs never advance the FSM — the system stays halted. Do not retry
   with `cryptographic_proof_valid: false`; staying halted is the correct
   zero-human-override behavior (I7).

### constitutiond process not responding

1. Kill the orphaned process: find the PID via `Get-Process constitutiond`
   and `Stop-Process -Id <pid>`.
2. Re-launch: `cargo run --release --manifest-path constitution/Cargo.toml --bin constitutiond`.
3. The kernel is now persistent across connections for the daemon's lifetime
   (Phase 10.1); only a daemon restart resets it.

### Port 15565 already in use

An orphaned `constitutiond` is likely holding the port:
```powershell
Get-NetTCPConnection -LocalPort 15565 | Select OwningProcess
Stop-Process -Id <OwningProcess>
```

---

## Debugging

### Malformed envelope errors

- Ensure `protocol_version` is exactly `1` (integer, not string).
- The `opcode` field must be one of: `EvaluateProposal`, `GetStatus`,
  `AttemptRecovery`, `Heartbeat`.
- The `payload` must be a JSON **string** (the value is double-encoded).
- `direction` inside a proposal must be `"Buy"` or `"Sell"` (case-sensitive).

### Integration test import failures

`agent_marl.py` imports `from cortex.proposal_api import ...`. The Python
path must include the `cortex/` project directory:

```powershell
$env:PYTHONPATH = "cortex"; python simulation/tests/integration_chronos.py
```

Or ensure `run_pipeline.py` (which inserts `sys.path` automatically) is used.