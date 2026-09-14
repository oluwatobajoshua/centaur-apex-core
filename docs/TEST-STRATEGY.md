# Test Strategy & QA Mandates — Centaur-Apex Core

> **Chronos mandate:** The system must survive 1,000 simulated years without
> fatal error before touching real capital. This is non-negotiable.

---

## Test pyramid

| Layer | What | Where | Runs on |
|-------|------|-------|---------|
| Unit (Rust) | Invariant logic, state machine transitions, TMR voter, IPC framing | `constitution/src/*.rs` | `cargo test` |
| Unit (Python) | Proposal schemas, client protocol, proposal logic | `cortex/tests/`, module-level tests | `python -m pytest` |
| Property-based / fuzz | Randomized portfolios, proposals, edge cases | Proptest (Rust), Hypothesis (Python) | CI |
| Integration | Multi-component E2E: Cortex → Constitution → verdict | `simulation/tests/` | Manual + CI |
| Chronos stress | 100–1000 year accelerated-time simulation | `simulation/tests/integration_chronos.py` | Manual gate pre-mainnet |
| Shadow sandbox | Live-environment replay without real capital | `evolution/sandbox_runner.py` | Pre-swap gate |

---

## Rust invariants (`constitution/`)

**Mandatory before any merge to `main`:**

```powershell
cargo build --release --manifest-path constitution/Cargo.toml
cargo test --manifest-path constitution/Cargo.toml
cargo fmt --check --manifest-path constitution/Cargo.toml
```

Current passing test count: **6/6** (heartbeat roundtrip, approved proposal,
rejected proposal, version mismatch, oversized frame, recovery with proof).

### Kani formal verification

The `invariants.rs` and `ipc.rs` modules contain `#[cfg(kani)]` proof
annotations. Before mainnet, these must pass:

```powershell
cargo kani --manifest-path constitution/Cargo.toml
```

The Kani proofs verify:
- `evaluate_proposal` never panics.
- `handle_frame` never panics for any byte input up to `MAX_FRAME_BYTES`.
- No arithmetic overflows on any input path.

---

## Python modules

**Mandatory for any Python change:**

```powershell
python -m py_compile <changed_file>
```

All existing modules currently compile cleanly.

### Unit tests

```powershell
python -m pytest cortex/tests/ simulation/tests/
```

---

## Chronos integration gate

```powershell
python simulation/tests/integration_chronos.py
```

This runs:
1. A simulated 250-year market (expandable to 1,000 years).
2. Synthetic regime sampling across 6 crisis types.
3. MARL agent proposals evaluated by the live Rust Constitution.
4. Equity, drawdown, and state-machine tracking.

Current results (v0.1.0, 250 years):
- `passed=True`
- Approved: 79,110 | Rejected: 11,825
- Emergency liquidations: 65 | Recoveries: 65
- Worst drawdown: 0.2752
- Final equity: 237,028.8

**Gate:** The Chronos run must complete with `passed=True` and 0 unrecovered
emergency halts before any deployment toward live capital.

---

## Fault injection testing

**To be implemented (Phase 6 of backlog):**

| Fault | Expected behavior |
|-------|------------------|
| Network drop mid-IPC | Client times out; daemon remains up; state machine unchanged |
| NaN injection in `target_notional` | Constitution returns `Rejected { reason_code: InvalidNumericalState }` |
| Extreme drawdown spike | State machine transitions: Normal → SoftDeleveraging → EmergencyHalt |
| Repeated failed recovery attempts | System stays in EmergencyHalt until valid cryptographic proof is provided |
| Oversized market data tick | Proposer silently discards; Constitution never sees it |

---

## Coverage targets

| Component | Minimum | Rationale |
|-----------|---------|-----------|
| `constitution/invariants.rs` | 100% (Kani) | Mathematical correctness of risk controls |
| `constitution/ipc.rs` | 100% (Kani) | Protocol boundary is attack surface |
| `constitution/state_machine.rs` | 100% (Kani) | All 4 states + transitions |
| `cortex/` modules | 90% line coverage | Python-side proposal logic |
| `simulation/` | Manual gate (not coverage-driven) | Stress harness correctness is validated by pass/fail outcome, not branch coverage |

---

## CI pipeline (to be implemented)

```
[push/PR to main]
  → rustfmt + clippy (constitution/)
  → cargo test (constitution/)
  → cargo kani (constitution/, optional gate)
  → python -m py_compile (all modules)
  → python -m pytest (unit tests)
  → integration test (Chronos, smoke)
  → security scan (gitleaks, cargo-audit)
```

All checks must pass before merge to `main` (branch protection enforced).