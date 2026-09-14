# Centaur-Apex Core

**A self-sustaining, antifragile autonomous trading ecosystem engineered for a minimum 100-year operational lifespan.**

> We do not write 100 years of code. We write the Genesis Codebase — the system's DNA — containing the deterministic safety kernel, the self-evolution framework, the protocol abstraction layer, and the distributed cryptographic backbone. Once alive, the system writes, tests, and replaces its own code.

---

## What is it?

Centaur-Apex Core separates **deterministic safety** (the Iron Constitution, written in formally-verifiable Rust) from **probabilistic intelligence** (the Adaptive Cortex, written in Python). The Constitution is a pure gate — it approves, rejects, or downsizes trade proposals. It never decides *what* to trade. The Cortex proposes; the Constitution disposes.

## Repository layout

| Path | Module | Layer |
|------|--------|-------|
| `constitution/` | Iron Constitution — risk kernel, state machine, TMR, keys, IPC + CLI | Deterministic safety (G1) |
| `cortex/` | Adaptive Cortex — proposal schemas, MARL agents, IPC client | Probabilistic intelligence (G5) |
| `evolution/` | Self-evolution machinery — code agent, theorem-prover CI, sandbox | Genesis machinery (G2) |
| `adapters/` | Protocol-agnostic execution abstraction + venue discovery | Genesis abstraction (G3) |
| `mesh/` | Edge mesh — BFT consensus, PQC wrapper, node daemon | Distributed backbone (G4) |
| `compliance/` | Governance — tax rules, structural shift, multi-sig DAO | Genesis foundations (G6) |
| `simulation/` | Chronos rig — synthetic regimes, accelerated-time stress | Test harness (G7) |
| `gateway/` | NestJS orchestration skeleton + Rust bridge | Skeleton (G8) |
| `AGENTS.md` | **The Law** — binding governance for humans and AI agents | Governance |
| `docs/PRD.md` | Full product requirements, invariants, compliance audit | Spec |
| `build_module*.ps1`, `setup.sh` | Reproducible bootstrap tooling | Tooling (G9) |

## Prerequisites

- **Rust toolchain** (cargo ≥ 1.7x) and/or `constitution/target/release/` binaries prebuilt
- **Python 3.11+** with `pydantic`, `numpy`, `pandas`, `requests`
- Node 18+ (gateway only)

## Quick start

```powershell
# 1. Build the Rust risk core (release)
cargo build --release --manifest-path constitution/Cargo.toml

# 2. Run the live Cortex → Constitution pipeline (auto-starts constitutiond)
python run_pipeline.py

# 3. Run the Chronos integration harness (250 simulated years)
python simulation/tests/integration_chronos.py
```

See [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) for the full walkthrough, and [docs/RUNBOOK.md](docs/RUNBOOK.md) for operations.

## The 100-year invariants

| # | Invariant |
|---|-----------|
| I1 | Max drawdown `(HWM − E(t)) / HWM ≥ 0.15` → EmergencyHalt + liquidation |
| I2 | Global leverage `Σ\|Notional\| / E(t) ≤ 2.5` |
| I3 | Asset concentration `\|Notional_j\| / E(t) ≤ 0.20` |
| I4 | Numerical validity — no NaN, no negative equity, no infinities |
| I5 | **No code outside `constitution/` may execute, sign, or route an order** |
| I6 | Any unknown state / crash / lost connectivity → EmergencyHalt |
| I7 | Zero-human override — only cryptographic multi-sig changes governance |
| I8 | Autonomy from genesis onward — must survive without human intervention |

## Documentation index

- [PRD (product requirements)](docs/PRD.md)
- [Governance (the law)](AGENTS.md) · [Governance deep-dive](docs/GOVERNANCE.md)
- [Architecture](docs/ARCHITECTURE.md) · [ADRs](docs/ADRS.md)
- [IPC protocol reference](docs/IPC-PROTOCOL.md)
- [Getting started](docs/GETTING-STARTED.md) · [Runbook](docs/RUNBOOK.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Coding standards](docs/CODING-STANDARDS.md)
- [Test strategy & QA mandates](docs/TEST-STRATEGY.md)
- [Security policy](SECURITY.md) · [Risk disclosure](docs/RISK-DISCLOSURE.md)
- [Changelog](CHANGELOG.md) · [Release process](docs/RELEASE.md)

## Contributing

This is a **closed-source proprietary project**. Internal contributors must read [AGENTS.md](AGENTS.md) (the law) and [CONTRIBUTING.md](CONTRIBUTING.md) before making any change. Every change is graded against the Genesis-DNA question: *"If the system's evolution engine existed today, would it own this file?"*

## License

All rights reserved. See [LICENSE](LICENSE) and [NOTICE](NOTICE).