# PRD: Centaur-Apex Core — The 100-Year Autonomous Trading Ecosystem

**Version:** 1.0.0  
**Status:** Genesis Scaffolding Complete — Phase 1 Verified  
**Date:** 2026-09-14  
**Scope:** Full-system product requirements, mathematical invariants, architecture, phased build plan, and coverage matrix.

---

## 1. Executive Summary

Centaur-Apex Core is a self-sustaining, antifragile autonomous trading ecosystem engineered to operate profitably and resiliently for a minimum 100-year lifespan. The architecture strictly isolates deterministic safety from probabilistic intelligence, automates software decay prevention, distributes infrastructure globally, enforces post-quantum cryptography, and implements zero-human governance.

**Core design principle:** We do not write 100 years of code. We write the Genesis Codebase — the system's DNA — containing the deterministic safety kernel, the self-evolution framework, the protocol abstraction layer, and the distributed cryptographic backbone. Once alive, the system writes, tests, and replaces its own code.

> **Governing law:** Root `AGENTS.md` codifies this principle as binding law for every human and AI agent. Anything in that file overrides stylistic preference. Every on-disk artifact is classified as **Genesis DNA** (G1–G9, ours to hand-write) or **System-Written** (S1–S7, owned by the Evolution Sub-Agent). Grading question at all times: *"If the system's evolution engine existed today, would it own this file?"*

---

## 2. System Architecture (The Four Pillars)

| Pillar | Name | Purpose | Module(s) |
|--------|------|---------|-----------|
| 1 | Separating Mind from Machine | Isolate deterministic risk from probabilistic AI | Constitution, Adaptive Cortex |
| 2 | Solving Software Rot | Prevent technical obsolescence over decades | Metamorphic Evolution, Protocol-Agnostic Adapters |
| 3 | Spatial Resilience | Eliminate single points of failure globally | Decentralized Edge Mesh, PQC |
| 4 | Immortal Capital | Autonomous regulatory compliance and governance | Compliance Engine, DAO Governance |

Supporting systems: Chronos Simulator, Doomsday Protocol (future), Genesis Ceremony (future).

---

## 3. Module Specifications

### Module 1: The Iron Constitution (Deterministic Risk Core)

- **Language:** Rust (formally verified, no `unsafe` blocks without proof)
- **Crate:** `iron_constitution`
- **Isolation:** Runs in a sandboxed process with exclusive access to private signing keys. The AI layer has read-only portfolio access and zero signing privileges.
- **Fail-safe default:** On crash, unknown error, network loss, or hardware anomaly → Emergency Halt State (cancel all open orders, liquidate to cash).
- **Server:** `constitutiond` — a length-prefixed TCP framing daemon (`127.0.0.1:15565`), versioned IPC protocol (v1), 16KB max frame.

#### Mathematical Invariants

| Invariant | Formula | Default Threshold |
|-----------|---------|-------------------|
| A: Max Drawdown | `(HWM - E(t)) / HWM ≥ limit` | 0.15 (15%) |
| B: Leverage Cap | `Σ|Notional_i| / E(t) ≤ cap` | 2.5x |
| C: Asset Concentration | `|Notional_j| / E(t) ≤ limit` | 0.20 (20%) |
| D: Numerical Validity | No NaN, no negative equity | Always enforced |

**Evaluation order:** Numerical validity → Drawdown circuit breaker → Leverage ceiling → Concentration limit.

#### State Machine (4-States)

| State | Transitions to | Behavior |
|-------|----------------|----------|
| `Normal` | SoftDeleveraging (drawdown ≥ 80% of threshold), EmergencyHalt (threshold breached) | Evaluates proposals normally |
| `SoftDeleveraging` | Normal (recovery), EmergencyHalt (breach) | Rejects new positions, allows closing only |
| `EmergencyHalt` | AutonomousRecovery (cryptographic proof) | Cancels all orders, liquidates, locks trading |
| `AutonomousRecovery` | Normal (diagnostic pass) | Requires multi-sig cryptographic validation |

#### TMR (Triple-Modular Redundancy) Voter

Three independent Constitution replicas evaluate the same proposal. The voter applies majority-rule reconciliation:
- Unanimous → use result directly
- Majority consistent → use the majority result (conservative: minimum approved notional, first rejection reason, or emergency)
- No majority → reject on InvalidNumericalState (hardware fault detected)

#### IPC Protocol (v1)

**Envelope:** `{ protocol_version: 1, request_id: str, opcode: str, payload: string }`

| Opcode | Request | Response |
|--------|---------|----------|
| `EvaluateProposal` | `{portfolio, proposal}` | `{verdict, system_state}` |
| `GetStatus` | `{}` | `{system_state, proposals_seen, emergencies}` |
| `AttemptRecovery` | `{cryptographic_proof_valid: bool}` | `{recovery_success: bool}` |
| `Heartbeat` | `{}` | `{alive: true, protocol_version: 1}` |

**Test suite:** 6 IPC tests passing (heartbeat, approved, rejected, recovery, version mismatch, oversized frame).

---

### Module 2: The Adaptive Cortex (Probabilistic AI Layer)

- **Language:** Python (Pydantic v2, NumPy)
- **Packages:** `adaptive_cortex`
- **Purpose:** Multi-Agent Reinforcement Learning (MARL) for alpha generation and meta-learning strategy discovery.
- **Execution privilege:** None. Emits `TradeProposal` structs; cannot execute trades directly.

#### Key Components

| File | Purpose |
|------|---------|
| `proposal_api.py` | Pydantic schemas: `TradeProposal`, `OrderDirection`, verdict parser |
| `agent_marl.py` | `AdaptiveCortexAgent` — conviction-based position sizing, proposal emission |
| `constitution_client.py` | TCP framing IPC client for `constitutiond` — supports persistent sessions for stateful evaluation |

**Position sizing formula:** `target_notional = equity × clamp(signal_strength, 0.01, 0.05)`

---

### Module 3: Metamorphic Code & Evolutionary Sub-Agent

- **Language:** Python
- **Packages:** `evolutionary_sub_agent`
- **Purpose:** Prevent software entropy. Self-refactoring pipeline with automated theorem prover CI.

#### Key Components

| File | Purpose |
|------|---------|
| `code_agent.py` | Detects runtime deprecation, stages patches to `evolution/patches/` |
| `ci_prover.py` | Wraps `cargo kani` / Lean for formal verification of candidate code |
| `sandbox_runner.py` | Shadow-trading harness; 99.9% confidence before production swap |

**Pipeline:** Detect deprecation → generate patch → run Kani/Lean → shadow test → hot-swap binary.

---

### Module 4: Protocol-Agnostic Execution Adapters

- **Language:** Python
- **Packages:** `protocol_agnostic_adapters`
- **Purpose:** Survive the death of any exchange/brokerage via universal intent-based routing.

#### Key Components

| File | Purpose |
|------|---------|
| `base.py` | Abstract `AbstractExchangeAdapter` with `UniversalOrderIntent` / `ExecutionReceipt` schemas |
| `discovery_agent.py` | Dynamic plugin loader; parses API changes, hot-swaps connectors |
| `venue_plugins/mock_exchange.py` | Reference adapter proving the universal interface |

---

### Module 5: Decentralized Edge Mesh & PQC

- **Language:** Python
- **Packages:** `decentralized_mesh`
- **Purpose:** Global P2P fault tolerance and quantum-resistant cryptography.

#### Key Components

| File | Purpose |
|------|---------|
| `pqc_wrapper.py` | Post-quantum signature generation (lattice-crypto placeholder) |
| `bft_consensus.py` | Byzantine Fault Tolerant state synchronization |
| `node_daemon.py` | Edge node health, heartbeat, microgrid telemetry |

---

### Module 6: Compliance & Cryptographic Governance

- **Language:** Python
- **Packages:** `immortal_compliance`
- **Purpose:** Autonomous regulatory compliance and zero-human operational control.

#### Key Components

| File | Purpose |
|------|---------|
| `tax_parser.py` | Real-time jurisdictional tax rate tracking, restricted-asset detection |
| `structural_shift.py` | Automatic capital routing under regulatory pressure |
| `multisig_dao.py` | Cryptographic multi-sig lockout; human overrides permanently denied |

---

### Chronos Simulation Rig

- **Language:** Python
- **Packages:** `chronos_simulator`
- **Purpose:** Accelerated-time synthetic market stress engine. **Mandate:** 1,000 simulated years without fatal error before mainnet.

#### Key Components

| File | Purpose |
|------|---------|
| `synthetic_gen.py` | Regime sampler: FLASH_CRASH, HYPERINFLATION, LIQUIDITY_EVAP, SOVEREIGN_RESET, LEDGER_FORK |
| `chronic_stress.py` | `ChronosStressHarness` — loops price paths, tracks equity/drawdown, fails on exhaustion |

---

## 4. Developer Handoff & Phased Roadmap

| Phase | Name | Status | What was built |
|-------|------|--------|----------------|
| 1 | Iron Constitution & TMR Core | **COMPLETE** | Rust kernel, 4-state machine, TMR voter, PQC key manager, TCP daemon, 6 tests |
| 2 | IPC Boundary + Cortex Client | **COMPLETE** | Versioned TCP framing protocol, Python persistent-session IPC client, E2E smoke test |
| 2b | CLI JSON Bridge | **COMPLETE** | `constitution_cli` — stdin/stdout JSON evaluator for non-TCP callers (NestJS gateway & external services) |
| 3 | Metamorphic Evolution Module | **COMPLETE** | Code agent, Kani CI wrapper, sandbox runner |
| 4 | Protocol-Agnostic Adapters | **COMPLETE** | Abstract routing, discovery agent, mock exchange plugin |
| 5 | Edge Mesh + PQC Layer | **COMPLETE** | BFT consensus, PQC signatures, node daemon |
| 6 | Compliance + Governance | **COMPLETE** | Tax parser, structural shift, DAO lockout |
| 7 | Chronos Simulation Rig | **COMPLETE** | Synthetic regime generator, 1000-yr stress harness |
| 8 | Chronos × Cortex × Constitution Integration | **COMPLETE** | Live integration test: MARL agent → Constitution IPC → equity tracking |
| 9 | Documentation (PRD) | **IN PROGRESS** | This document |
| 10 | Doomsday Protocol | NOT STARTED | Dead-man switch, physical asset conversion |
| 11 | Genesis Ceremony | NOT STARTED | Multi-sig key ceremony, time-locked smart contracts |
| 12 | Real PQC / Real Kani CI | NOT STARTED | CRYSTALS-Dilithium, live Lean/Kani in CI pipeline |

---

## 5. Verification & QA Mandates

- **Fuzz Testing:** Continuous `proptest` (Rust) / property-based Python testing against millions of random market scenarios.
- **Formal Verification:** Kani model checker proofs for all invariant functions — prove no panics, no overflows, no logical bypasses.
- **Chaos Engineering:** Automated scripts severing DB connections, corrupting packets, simulating flash crashes.
- **Chronos Mandate:** System must survive 1,000 simulated years autonomously before touching mainnet.

---

## 6. Coverage Matrix

| Blueprint Requirement | On-Disk | Build Verified | Tested E2E |
|-----------------------|---------|----------------|------------|
| Iron Constitution (Rust) | `constitution/src/` | cargo build ✓ | 6/6 IPC tests ✓ |
| CLI JSON Bridge | `constitution/src/bin/constitution_cli.rs` | cargo build ✓ | — |
| Adaptive Cortex (Python) | `cortex/cortex/` | py_compile ✓ | Live vs constitutiond ✓ |
| Metamorphic Evolution | `evolution/evolution/` | py_compile ✓ | — |
| Protocol-Agnostic Adapters | `adapters/adapters/` | py_compile ✓ | — |
| Edge Mesh + PQC | `mesh/mesh/` | py_compile ✓ | — |
| Compliance + Governance | `compliance/compliance/` | py_compile ✓ | — |
| Chronos Simulation | `simulation/simulation/` | py_compile ✓ | Integration test ✓ |
| Genesis Governance Law | `AGENTS.md` | — | Enforced via grading questions (§8) |
| NestJS Gateway scaffold | `gateway/` | — | TCP bridge to `constitution_cli` |
| Doomsday Protocol | — | — | — |
| Genesis Ceremony | — | — | — |
| Real PQC (lattice crypto) | — | — | — |
| TMR hardware-level | — | — | — |

---

## 7. Known Limitations & Technical Debt

| Issue | Severity | Notes |
|-------|----------|-------|
| `constitutiond` spawns fresh kernel per TCP connection | Medium | Cross-connection state not persisted. Acceptable for scaffold; needs persistent service for production. |
| PQC wrapper uses HMAC-SHA3, not real lattice crypto | Low | Placeholder; swap to `liboqs` / CRYSTALS-Dilithium before mainnet. |
| BFT consensus is simulated, not wired to real network | Low | Functional prototype; replace with real Raft/BFT library for production. |
| Integration test equity tracking is simplified | Low | Verdicts don't modify equity in Chronos loop yet; needs real order-fill simulation. |
| No `docs/` directory in original scaffold | Fixed | This PRD now populates it. |

---

## 8. Genesis DNA Compliance Audit

Ground truth: `AGENTS.md` §2–§3. Every file is classified; **System-Written artifacts are permitted on-disk only as clearly-marked bootstrap stubs** the Evolution Sub-Agent owns — never as final assets.

| Artifact | Classification | On-disk posture |
|----------|----------------|-----------------|
| `constitution/` (invariants, state machine, TMR, keys, IPC, `constitutiond`, `constitution_cli`) | **G1** Genesis | Core with `cargo build` + 6 passing tests |
| `evolution/` (code_agent, ci_prover, sandbox_runner) | **G2** Genesis | Machinery only; zero pre-written patches |
| `adapters/base.py`, `discovery_agent.py` | **G3** Genesis | Abstract contract + loader |
| `mesh/` (bft, pqc, node_daemon) | **G4** Genesis | Backbone, stub crypto |
| `cortex/proposal_api.py`, `constitution_client.py` | **G5** Genesis | Schema/framework/machinery |
| `compliance/` (tax, structural_shift, multisig_dao) | **G6** Genesis | Foundations |
| `simulation/` (synthetic_gen, chronic_stress) | **G7** Genesis | Rig |
| `gateway/` (NestJS scaffold + Rust bridge) | **G8** Genesis | Skeleton, IPC framing only |
| `build_module*.ps1`, `setup.sh` | **G9** Genesis | Bootstrap tooling |
| `adapters/venue_plugins/mt5_adapter.py`, `mock_exchange.py` | **S1** System | Marked bootstrap stub; hot-swappable; not 100-yr assets |
| `cortex/cortex/engine.py`, `agent_marl.py` | **S2** System | Marked bootstrap alpha; Cortex meta-learning owns replacement |

**Rule of tension:** anything that *needs to change within 100 years* (venue APIs, alphas, laws, crypto) must never be hand-finalized — only the mechanism to generate/swap it belongs in Genesis DNA.
