# Troubleshooting — Centaur-Apex Core

Common problems and their fixes. If your issue isn't here, check
`docs/RUNBOOK.md` §Debugging first.

---

## cargo: command not found (Windows)

The cargo binary is not on `PATH`. Use the full path:
```powershell
C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe <args>
```

Or add it to your session:
```powershell
$env:Path += ";$env:USERPROFILE\.cargo\bin"
```

---

## Port 15565 already in use

An orphaned `constitutiond` is holding the port:
```powershell
Get-NetTCPConnection -LocalPort 15565 | Select OwningProcess
Stop-Process -Id <OwningProcess>
```

---

## `MalformedEnvelope` from constitution_cli

Check:
1. `"protocol_version"` is an integer `1`, not a string `"1"`.
2. `"opcode"` is exactly one of `EvaluateProposal`, `GetStatus`,
   `AttemptRecovery`, `Heartbeat`.
3. `"payload"` is a **string** containing escaped JSON
   (`\"portfolio\"`, not `"portfolio"`), i.e., double-encoded.

PowerShell quoting is the usual culprit:
```powershell
# BROKEN (PowerShell eats the backslashes):
& constitution_cli.exe "{...\"payload\"...}"
# SOLUTION: write the envelope to a file and pipe it:
Get-Content -Raw env.json | & constitution_cli.exe
```

---

## `MalformedPayload` from constitution_cli

The envelope parsed, but the `payload` string doesn't match the opcode:
- For `EvaluateProposal`, the payload must contain `{"portfolio":{...},"proposal":{...}}`
- `direction` must be `"Buy"` or `"Sell"` (case-sensitive — `"BUY"` fails)
- All numeric fields must be numbers, not strings

---

## Integration test import errors (`cannot import name ...`)

Sub-package imports (`from cortex.proposal_api import ...`) require the module
root on `sys.path`. Run from the repo root, or set:
```powershell
$env:PYTHONPATH = "cortex"; python simulation/tests/integration_chronos.py
```

`run_pipeline.py` handles this automatically via `sys.path.insert`.

---

## MT5 adapter dry-run / `MetaTrader5` import fails

The `MetaTrader5` Python package is absent in CI/sandbox. This is expected;
the `mt5_adapter` plugin (`venue_plugins/mt5_adapter/adapter.py`) degrades to
`DRY_RUN` receipts. Install with:
```powershell
pip install MetaTrader5
```
and connect from a machine with the MT5 terminal installed.

---

## Chronos integration test says `passed=False`

- Look for unrecovered emergency halts in the output — the system stays in
  `EmergencyHalt` unless a valid recovery proof is supplied.
- Check that a *fresh* `constitutiond` is running (state isn't shared across
  connections; a stale daemon can carry prior state).
- Confirm Python packages installed: `pip install pydantic numpy pandas`.

---

## Gateway build fails (`v {` / TS2322)

The padded NestJS output in the original scaffold was replaced in-repo with
the typed `RustBridgeService`. Reinstall dependencies from scratch:
```powershell
cd gateway
Remove-Item -Recurse -Force node_modules, dist
npm install
npm run build
```

---

## Version mismatch after protocol change

If `constitution/` payload schemas changed, bump `IPC_PROTOCOL_VERSION` in
`constitution/src/ipc.rs` and update `docs/IPC-PROTOCOL.md` versioning table.
Clients must send the new version or they get `VersionMismatch`.