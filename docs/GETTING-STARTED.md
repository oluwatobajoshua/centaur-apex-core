# Getting Started — Centaur-Apex Core

**Goal:** run a live end-to-end evaluation of a trade proposal through the
Rust Iron Constitution in under 10 minutes.

---

## 1. Toolchain check

| Tool | Check |
|------|-------|
| Rust/cargo | `cargo --version` (or use full path `C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe`) |
| Python 3.11+ | `python --version`; verify `import pydantic, numpy, pandas, requests` |
| Git | `git --version` |
| (Optional) Node 18+ | `node --version` — only for the `gateway/` scaffold |

---

## 2. Clone

```powershell
git clone https://github.com/oluwatobajoshua/centaur-apex-core.git
cd centaur-apex-core
```

---

## 3. Build the Rust risk core

```powershell
cargo build --release --manifest-path constitution/Cargo.toml
```

This builds two binaries:
- `constitutiond` — the TCP daemon on `127.0.0.1:15565`
- `constitution_cli` — the stdin/stdout JSON bridge

Verify the unit tests:
```powershell
cargo test --manifest-path constitution/Cargo.toml
```
Expected: `6 passed; 0 failed`.

---

## 4. Run the live pipeline

```powershell
python run_pipeline.py
```

**What it does:**

1. Opens (or starts) `constitutiond`.
2. Creates a `ConstitutionIPCClient` with a persistent session.
3. Feeds 3 market scenarios through `CortexEngine`:
   - Bullish EURUSD → proposal generated
   - Bearish EURUSD (high vol) → proposal generated, size halved
   - Neutral (no momentum) → `NoAction`
4. Each proposal is wrapped in `EvaluateProposal`, sent to the Rust
   Constitution, and returns an `Approved` or `Rejected` verdict.

**Expected output (excerpt):**
```
[1] Cortex proposal -> Constitution verdict: {"Approved":{"adjusted_notional":...}} [Normal]
...
[SUCCESS] End-to-End pipeline (Cortex -> Rust Constitution) complete!
```

---

## 5. Try the CLI bridge directly

Send a heartbeat:

```powershell
'{"protocol_version":1,"request_id":"t","opcode":"Heartbeat","payload":"{}"}' | & "constitution\target\release\constitution_cli.exe"
# {"alive":true,"protocol_version":1}
```

Send an evaluation (approved case — 50K notional on 1M equity):

```powershell
& "constitution\target\release\constitution_cli.exe" '{"protocol_version":1,"request_id":"t","opcode":"EvaluateProposal","payload":"{\"portfolio\":{\"timestamp\":1,\"total_equity\":1000000,\"cash_balance\":900000,\"high_water_mark\":1000000,\"open_positions\":[]},\"proposal\":{\"proposal_id\":\"p\",\"asset_id\":\"EURUSD\",\"direction\":\"Buy\",\"target_notional\":50000,\"max_acceptable_slippage\":0.001}}"}}'
# {"verdict":{"Approved":{"adjusted_notional":50000.0}},"system_state":"Normal"}
```

---

## 6. Run the Chronos integration harness

```powershell
python simulation/tests/integration_chronos.py
```

Simulates **250 years** of synthetic market regimes through the live Rust
Constitution. Expect ~1-2 minutes.

---

## 7. Next steps

| Module | Read |
|--------|------|
| Architecture | `docs/ARCHITECTURE.md` |
| Governance (the law) | `AGENTS.md` |
| Protocol | `docs/IPC-PROTOCOL.md` |
| Ops | `docs/RUNBOOK.md` |
| Full spec | `docs/PRD.md` |

---

## Troubleshooting quick links

- `docs/RUNBOOK.md` §Debugging — malformed envelopes, port conflicts,
  orphaned daemons.
- `docs/TROUBLESHOOTING.md` — common issues and fixes.