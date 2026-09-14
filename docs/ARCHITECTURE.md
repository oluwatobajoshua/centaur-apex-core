# Architecture — Centaur-Apex Core

**Status:** Genesis Bootstrap (v0.1.0)

---

## Design philosophy

> **Mind vs. Machine.** The deterministic safety core (the Constitution)
> and the probabilistic intelligence layer (the Cortex) are architecturally
> separated. They share no memory, no mutable state, and no control flow.
> The Cortex proposes; the Constitution disposes.

> **Evidence boundary.** Everything that crosses from the intelligence plane
> to the execution plane is a typed artifact (a `TradeProposal`, a
> `UniversalOrderIntent`). There is no hidden prompt chain, no opaque LLM
> call, and no untyped signal crossing the boundary. Every handoff is
> inspectable, replayable, and replaceable.

> **Deferral over permanence.** Anything that will need to change across
> decades (venues, strategies, laws, crypto standards) is never written as a
> final asset. Only the *mechanism to generate, verify, and swap* it belongs
> in the Genesis Codebase.

---

## The Four Pillars

| Pillar | Name | Purpose | Module(s) |
|--------|------|---------|-----------|
| 1 | Separating Mind from Machine | Isolate deterministic risk from probabilistic AI | Constitution, Cortex |
| 2 | Solving Software Rot | Prevent technical obsolescence | Metamorphic Evolution, Protocol-Agnostic Adapters |
| 3 | Spatial Resilience | Eliminate single points of failure | Decentralized Edge Mesh, PQC |
| 4 | Immortal Capital | Autonomous regulatory compliance + governance | Compliance Engine, DAO Governance |

---

## Dual-plane architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Evolution Plane                               │
│   Evolution Sub-Agent · Code Agent · Kani Prover · Shadow Sandbox      │
│   Detects obsolescence → generates patch → proves → tests → hot-swap   │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ typed patch artifacts
┌──────────────────────────────────▼──────────────────────────────────────┐
│                           Evidence Boundary                             │
│   TradeProposal · UniversalOrderIntent · ConstitutionVerdict            │
│   Every crossing is typed, logged, and inspectable                      │
└──────────┬───────────────────────┬──────────────────────────────────────┘
           │                       │
┌──────────▼──────────┐  ┌────────▼──────────────────────────────────────┐
│  Intelligence Plane │  │            Execution Plane                     │
│                     │  │                                                │
│  Adaptive Cortex    │  │  Iron Constitution (Rust)                     │
│  MARL agents        │──►  Invariants · State machine · TMR voter       │
│  engine.py (S2)     │  │  execute_order() — pure gate, never decides  │
│  proposal_api.py    │  │  constitutiond / constitution_cli             │
│                     │  │                                                │
└─────────────────────┘  │  Adapters (S1 stubs)                         │
                         │  M/T5 · mock · future venue plugins           │
                         │  AbstractExchangeAdapter contract             │
                         └────────────────────────────────────────────────┘
```

---

## Data flow: live proposal

1. **Cortex** (`engine.py` or `agent_marl.py`) evaluates a market tick, emits
   a typed `TradeProposal` (asset, direction, notional, slippage bound).
2. **Constitution client** (`constitution_client.py`) wraps it in an
   `EvaluateProposalRequest` (portfolio + proposal), serializes it as an
   IPC envelope, and sends it over a TCP framed connection to `constitutiond`
   (or via stdin/stdout to `constitution_cli`).
3. **Constitution** deserializes the envelope, runs the 4-invariant risk
   kernel in order:
   - Numerical validity (no NaN, no inf, equity ≥ 0)
   - Drawdown circuit breaker (I1)
   - Global leverage cap (I2)
   - Asset concentration cap (I3)
   And transitions the state machine (Normal → SoftDeleveraging → EmergencyHalt).
4. **Constitution** returns a typed `ConstitutionVerdict`:
   `Approved { adjusted_notional }` or `Rejected { reason_code }`, plus the
   current `system_state`.
5. **Cortex** processes the verdict (simulate fill, update HWM, re-submit,
   or abort).

---

## Process topology

| Process | Language | TCP port | Role |
|---------|----------|----------|------|
| `constitutiond` | Rust | 127.0.0.1:15565 | Risk kernel TCP daemon |
| `constitution_cli` | Rust | (stdin/stdout) | JSON bridge for NestJS / external callers |
| NestJS gateway | TypeScript | (TBD) | Orchestration, REST + WebSocket |
| Python Cortex | Python 3.11+ | (IPC client only) | Strategy proposals, learning loops |

The Constitution has **exclusive signing authority.** No other process may
route or sign an order (Invariant I5).

---

## Memory & state

| Component | State model |
|-----------|-------------|
| Constitution (per-connection) | Stateless across connections; state persists only within a single TCP session |
| TMR voter | Three constitution replicas evaluate the same proposal; majority rules |
| Cortex | In-memory market context; proposer state is ephemeral per tick |
| Chronos simulation | Synthetic equity/drawdown tracking in `chronic_stress.py`; no persistence across runs |
| Evolution patches | Ephemeral `evolution/patches/*.diff`; consumed by sandbox and discarded or committed |

---

## Trust boundary

| Boundary | What crosses | What cannot |
|----------|-------------|-------------|
| Cortex → Constitution | Typed `TradeProposal` + `PortfolioState` | Direct market execution, secret keys |
| Constitution → Cortex | `ConstitutionVerdict` + `system_state` | Risk parameter mutation (without multi-sig) |
| Constitution → Adapters | Typed `UniversalOrderIntent` | The Constitution *never* routes to an adapter — it only approves/rejects; routing lives outside it |
| Evolution → Constitution | Candidate patches (via Kani + sandbox gate) | Live hot-swap without formal verification + multi-sig governance |
| Any process → Constitution | Opcodes only | Privileged operations (only genesis multi-sig can mutate invariants) |