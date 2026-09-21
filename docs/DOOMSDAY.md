# Doomsday Protocol — Design Doc (Phase 14.1)

> **Genesis-aligned:** this document specifies the *machinery* by which the
> system manages catastrophic liveness loss. It is not a strategy, alpha, or
> venue-specific integration — those remain system-written artifacts.
> Classification: **G6** (governance & zero-human operational control).

---

## 1. Purpose

The Doomsday Protocol is the system's deterministic last-resort responder. It
operates **in reverse** of a human dead-man switch:

| Aspect | Human-style dead-man switch | Centaur-Apex Doomsday Protocol |
|--------|-----------------------------|--------------------------------|
| Who is watched | A human (if they fail to press the button, alarm fires) | The **system itself** + its governance/ops liveness beacons |
| Who acts | Hospital staff / operations | The system, autonomously, along a **pre-registered escalation path** |
| Override | A human can cancel | Humans **cannot** cancel (I7 — only cryptographic multi-sig can change governance) |
| Failure default | Alarm = safe | Escalation = safe: the system follows its registered plan, or halts (I6) |

The Protocol enforces invariants **I7 (zero-human override)** and **I8
(autonomy from genesis onward)** while an operator or governance oracle is
unavailable.

## 2. Failure model

The protocol triggers when the system observes **liveness loss**:

| Failure | Detection signal | Consequence if untreated |
|---------|------------------|--------------------------|
| Local daemon dies | Supervisor heartbeat not received for `grace_period` | Escalation path begins |
| Mesh quorum lost (network partition) | Peers stop acking; BFT quorum impossible | Conservative halt + limited liquidation plan |
| Ops/governance oracle unresponsive | Beacon oracle heartbeat absent | Treat as governance-unreachable -> escalate |
| Cryptographic keys unavailable | HSM/PQC vault heartbeat absent | Liquidate to survivable assets per plan |

The protocol has **one deterministic state machine** — it never guesses.

## 3. Dead-man switch state machine (deterministic)

```
ARMED --(first missed beat + grace period)--> WATCHING
WATCHING --(continue missing)--> ESCALATING
ESCALATING --(execute step k; next period)--> ESCALATING (step k+1)
ESCALATING --(no steps remain)--> LIQUIDATING
any-of {ARMED, WATCHING, ESCALATING, LIQUIDATING} --(heartbeat resumes BEFORE
exit condition)--> ARMED                      (fail-safe recovery)
LIQUIDATING --(asset conversion confirmed)--> DORMANT
```

Guarantees:

- Transitions are monotonic through the escalation ladder; **no state is
  skipped** (mirrors the Constitution FSM discipline, Phase 10.2).
- Re-arming is allowed only while escalation has not passed the
  `abortable_until` threshold, and only on a fresh valid heartbeat.
- `DORMANT` is terminal for a given configuration epoch (prevents flapping).
- Every transition is timestamped and journaled (bounded journal, cf.
  `MAX_TRANSITION_HISTORY` in the Constitution) for post-mortem audit.

## 4. Heartbeat cadence

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `heartbeat_interval` | 5 s | Period between normal beats the daemon emits |
| `grace_period` | 3 × `heartbeat_interval` | Misses tolerated before `WATCHING` |
| `escalation_period` | 6 × `heartbeat_interval` | Time between escalation steps |
| `abortable_until` | step 2 of N | Escalation depth beyond which the plan is no longer reversible |

All values are **data-driven** (config schema, Section 7) — never hardcoded.

## 5. Escalation path (executed steps)

Each step is an ordered, registered action drawn from a closed vocabulary:

| Step type | Action | Fail-safe on error |
|-----------|--------|--------------------|
| `notify` | Push alert to bonded channels (ops beacons) | Continue to next step |
| `halt_placements` | Freeze new order placement (gateway) | Halt (I6) |
| `reduce_exposure` | Issue commitment-reduction intents, bounded by Constitution | Constitution rejects if I1–I4 violated |
| `acquire_assets` | Instruct Asset Conversion Oracle to convert holdings to survivable assets | Retry (time-limited); then halt |
| `seal` | Rotate/ratchet keys, snapshot journal, publish evidence | Audit trail persists |

The plan is **schema-defined** (Section 7). Running a plan never bypasses the
Constitution — every intent still passes the risk kernel (I5 independence).

## 6. Asset conversion oracle (Phase 14.3 interface)

The physical asset conversion oracle is a **narrow interface** the daemon
consumes (`AssetConversionOracle`):

```text
quote(asset_in, asset_out, qty)         -> ConversionQuote (firm/indicative)
submit_conversion_request(quote, ... )  -> ConversionOrder (id, status)
get_conversion_status(order_id)         -> ConversionStatus
```

- Implementations (hardware-vendor, custodian, venue settlement rails) are
  **system-owned** (S7) — the interface is Genesis DNA only.
- The daemon always requires a *quote-ref* before submitting; a lost/dropped
  order becomes an audit event, never a guess.
- A `SimulationOracle` ships with the scaffold for sandbox testing; a
  `ConfigDrivenOracle` demonstrates data-driven integration for plugging in
  system-generated connectors.

## 7. Config schema (data-driven)

```yaml
deadman:
  heartbeat_interval_s: 5
  grace_multiplier: 3
  escalation_enabled: true
  plan:
    - step: notify
      channels: ["ops"]
    - step: halt_placements
    - step: reduce_exposure
      target_percentage: 50     # interpreted by the system's own generators
    - step: acquire_assets
      via: "simulation_oracle"  # or a system-generated connector
      asset_out: "USDT"
    - step: seal
  oracle: "simulation_oracle"
```

The scaffold validates this schema with Pydantic (`doomsday/config.py`); the
plan vocabulary is a closed enum so the system can never invent step types.

## 8. Why this is Genesis (not system code)

Ask AGENTS.md §5's questions:

1. *Does this change within 100 years?* The steps, assets, cadence, and oracle
   connector do → they live in **data** (schema), which the Evolution Sub-Agent
   owns.
2. *Is this a specific instantiation or a general mechanism?* The daemon, FSM,
   oracle interface, and config validator are the general mechanism.
3. *Would the evolution engine own this file?* The engine may re-parameterize
   plans, swap oracle connectors, and tune cadence — but the state machine,
   interface, and config contract are stable Genesis machinery.

## 9. Security notes

- Human operators cannot arm/disarm the switch — that requires the governance
  multi-sig path (Genesis Ceremony, §15).
- Heartbeats are signed with the mesh PQC engine (Phase 13.1) where a wallet
  exists; the daemon refuses unsigned beats in `strict` mode.
- Escalation evidence (journal + quotes + receipts) is sealed for post-mortem
  review — the only "human gate" is after-the-fact audit, never live control.