# AGENTS.md — Centaur-Apex Core Governance

## The Law

> **We do not write 100 years of code. We write the Genesis Codebase — the system's DNA — containing the deterministic safety kernel, the self-evolution framework, the protocol abstraction layer, and the distributed cryptographic backbone. Once alive, the system writes, tests, and replaces its own code.**

This is binding law for every human and every AI agent that touches this repository. Anything in this file overrides stylistic or convenience preferences. When in doubt, ask: **"Is this a piece of Genesis DNA, or is this code the system itself should write?"**

---

## 1. Mandate

Centaur-Apex Core is a self-sustaining, antifragile autonomous trading ecosystem engineered for a minimum **100-year** operational lifespan. The architecture strictly:

1. Isolates **deterministic safety** from **probabilistic intelligence** (Mind vs. Machine).
2. Automates software decay prevention (self-refactoring, transpilation, formal verification).
3. Distributes infrastructure globally (fault-tolerant edge mesh, no single points of failure).
4. Enforces post-quantum cryptography and zero-human operational governance.

---

## 2. What WE Build (Genesis DNA) — Immutable, Foundational

The code we write is limited to a small, defensible set. It must be memory-safe, formally verifiable where possible, and structurally designed to be **extended or transpiled by the system — never hand-maintained forever**.

| # | Genesis Component | Location | Rule |
|---|-------------------|----------|------|
| G1 | **Iron Constitution** (deterministic risk kernel) | `constitution/` | Real invariants, state machine, TMR voter, secure keys, IPC/CLI boundary. **No AI may override it.** |
| G2 | **Self-Evolution Framework** | `evolution/` | The *machinery* that reads code, runs theorem provers, sandboxes, and merges patches. |
| G3 | **Protocol-Agnostic Abstraction Layer** | `adapters/` | The universal `AbstractExchangeAdapter` interface + discovery agent. **Specific venue plugins are the system's job.** |
| G4 | **Distributed Cryptographic Backbone** | `mesh/` | BFT state sync, PQC wrappers, node daemon, microgrid hooks. |
| G5 | **Adaptive Cortex frameworks** | `cortex/` | *Frameworks only*: proposal schemas, MARL scaffolding, meta-learning structure. |
| G6 | **Governance & Compliance foundations** | `compliance/` | Rules-as-code parsers, structural shift logic, multi-sig DAO lockout. |
| G7 | **Chronos Simulation Rig** | `simulation/` | Synthetic regime generators, accelerated-time stress harness. |
| G8 | **Gateway / orchestration skeleton** | `gateway/` | NestJS scaffolding + the Rust bridge (IPC framing). No hardcoded business alpha. |
| G9 | **Build / bootstrap tooling** | `build_*.ps1`, `setup.sh` | Reproducible scaffolding. |

### 2.1 Absolute Rules for Genesis Code

- **G1 is non-negotiable.** The Constitution's invariants (`invariants.rs`) and state machine may only be changed through the formal verification + cryptographic governance path. No agent, human, or model writes `unsafe` blocks into it.
- Genesis code must contain **zero hardcoded market strategies, zero venue-specific business logic, zero assumptions about specific brokers or asset classes** that are meant to survive 100 years.
- Genesis code should prefer **data-driven, schema-defined config** over hardcoded values wherever the system will need to adapt.

---

## 3. What THE SYSTEM Writes (Over 100 Years) — NOT Ours

Humans and agents must **never** pre-write these. Writing them by hand breaks the law.

| # | System-Written Artifact | Where It Appears | Examples |
|---|-------------------------|------------------|----------|
| S1 | **Dynamic Exchange Adapters** | `adapters/adapters/venue_plugins/` | MT5, CME, crypto venue connectors. *Discovery Agent + Evolution Sub-Agent produce these over time.* |
| S2 | **Alpha Generation Strategies** | `cortex/models/`, `cortex/cortex/` (strategy modules) | Any concrete sizing, signal, or entry/exit logic. *The Cortex meta-learns and generates these.* |
| S3 | **Transpiled / Refactored Genesis Code** | `evolution/patches/` | Rewrites of Genesis components against future compilers, runtimes, and hardware arch. |
| S4 | **Cryptographic migrations** | `mesh/` | New PQC algorithm implementations as standards evolve. |
| S5 | **Compliance rule expansions** | `compliance/` | New jurisdiction parsers, tax regimes as law evolves. |
| S6 | **New venue discovery adapters** | `adapters/` | Hot-swapped plugins when venues die or change APIs. |
| S7 | **New asset-class handling modules** | `cortex/`, `mesh/` | Support for asset classes that don't exist yet. |

### 3.1 What Happens If We Write System Code

We are code. We are judged on alignment. If a build step, plugin, or strategy module is hand-authored as if it were a **final, permanent asset**, we have:

1. Introduced technical debt the system cannot fully "own".
2. Violated the bootstrapping principle — the system is meant to *discover* these, not inherit them.
3. Potentially created a hand-maintained bottleneck across decades.

The correct response is to **defer**: build the generation/verification *machinery*, not the artifact.

---

## 4. The 100-Year Invariants (System-Level)

These mathematical/computational guarantees must hold, and no change may weaken them:

| Invariant | Definition |
|-----------|------------|
| I1 | Max drawdown `(HWM − E(t)) / HWM ≥ 0.15` → **EmergencyHalt + liquidation** |
| I2 | Global leverage `Σ|Notional| / E(t) ≤ 2.5` |
| I3 | Asset concentration `|Notional_j| / E(t) ≤ 0.20` |
| I4 | Numerical validity — no NaN, no negative equity, no `Infinite` states |
| I5 | **Independence**: no code outside `constitution/` may ever execute, sign, or route an order itself |
| I6 | **Fail-safe default**: any unknown state, crash, or loss of connectivity → EmergencyHalt |
| I7 | **Zero-human override**: humans cannot panic-stop a century-long strategy; only cryptographic multi-sig can change governance |
| I8 | **Autonomy**: the system must survive without human intervention *from genesis onward* |

---

## 5. The Principle That Guides Every Decision

> "We are writing the Genesis Codebase — the system's DNA. Once the self-evolution engine is alive, it handles the ongoing development, refactoring, and adaptation itself. Everything we hand-write now must be just enough foundation for the system to take over."

Ask these three questions before adding any code:

1. **Does this artifact need to change within 100 years?** If yes, build the mechanism to change it (data-driven, plugin, agent-generated) — do not hand-hardcode the solution.
2. **Is this a specific instantiation, or a general mechanism?** Instantiations belong to the system; mechanisms are Genesis.
3. **If the system's evolution engine existed today, would it own this file?** If yes, do not write it — write the tooling that lets the system generate it.

---

## 6. Constitution Review Gate

Any change intended for `constitution/` (G1) must:

1. Be accompanied by an entry in `docs/PRD.md` unchanged invariants, or an explicit **formal-verification-driven** invariant change record.
2. Pass `cargo test` and `cargo build --release`.
3. Be submitted as a **proposal** to the cryptographic governance layer (multi-sig) — never merged by direct write.

---

## 7. Contribution Conventions

- **Zero hardcoded secrets.** Keys live in HSM / PQC vaults, never in the repo.
- **DNS/schema over code.** New venues/strategies/asset classes are declared in schemas (`adapters/schemas/`), not hand-written logic.
- [ ] **Formal verification where possible.** Rust invariants must remain Kani-provable; don't introduce unchecked arithmetic that defeats it. Proptest fuzzes all f64 inputs (NaN/inf/negative) — 27 total tests, bug found + fixed (infinite equity validation gap). Python `hypothesis` adds 11 property tests (500 examples each).
- **Sandbox everything.** Any new executable logic goes through Chromos sandboxing before it can be trusted.
- **Never extend the endpoint with business logic.** The Constitution is a pure gate — it approves/rejects/downsizes. It does not decide *what* to trade.

---

## 8. Done Checklist (Definition of Done)

A change is "done" only when:

- [ ] It is Genesis DNA (a mechanism) OR clearly marked as a stub that the system will own.
- [ ] No hardcoded strategy/venue logic was added as a permanent asset.
- [ ] `cargo build --release` + `cargo test` pass (for Rust).
- [ ] Python modules pass `python -m py_compile`.
- [ ] No secrets, credentials, or private keys are present.
- [ ] Change aligns with one of G1–G9, or intentionally adds machinery for S1–S7.
- [ ] **`TRACKER.md` is updated immediately.** The corresponding task item is checked off, and any newly discovered tasks are added to the appropriate phase or backlog. This is a hard gate — a session that modifies code but leaves the tracker stale is not done.