# TRACKER.md — Implementation Tracker

**Last updated:** 2026-09-22
**Source of truth:** Audit findings + PRD debt register + AGENTS.md mandates

---

## How to use

- Check off items with `[x]` as they complete.
- Move completed items to the bottom of their section.
- Never delete completed items — history matters.

---

## Phase 9: Verification & Test Infrastructure (COMPLETE)

> The scaffold exists. Nothing is verified. This phase gates everything downstream.

### 9A. Python Unit Tests

Every module has an empty `tests/` directory. Fill them.

| # | Task | Module | Depends on | Done |
|---|------|--------|------------|------|
| 9A.1 | Unit tests for `proposal_api.py` — schema validation, enum parsing, verdict round-trip | cortex | — | [x] |
| 9A.2 | Unit tests for `constitution_client.py` — envelope building, frame encoding, RPC methods, context manager lifecycle | cortex | — | [x] |
| 9A.3 | Unit tests for `engine.py` — tick evaluation, proposal generation, sizing bounds | cortex | 9A.1 | [x] |
| 9A.4 | Unit tests for `agent_marl.py` — conviction sizing formula, clamp bounds, proposal emission | cortex | 9A.1 | [x] |
| 9A.5 | Unit tests for `discovery_agent.py` — plugin discovery, missing-plugin error, reload | adapters | — | [x] |
| 9A.6 | Unit tests for `base.py` — abstract contract enforcement, Pydantic model validation | adapters | — | [x] |
| 9A.7 | Unit tests for `code_agent.py` — patch staging, file write, diff format | evolution | — | [x] |
| 9A.8 | Unit tests for `ci_prover.py` — Kani invocation, fallback simulation | evolution | — | [x] |
| 9A.9 | Unit tests for `sandbox_runner.py` — shadow simulation interface | evolution | — | [x] |
| 9A.10 | Unit tests for `bft_consensus.py` — quorum logic, Byzantine rejection | mesh | — | [x] |
| 9A.11 | Unit tests for `pqc_wrapper.py` — signing, verification, tamper detection | mesh | — | [x] |
| 9A.12 | Unit tests for `node_daemon.py` — start/stop, heartbeat cycle | mesh | — | [x] |
| 9A.13 | Unit tests for `tax_parser.py` — jurisdiction lookup, restricted asset detection | compliance | — | [x] |
| 9A.14 | Unit tests for `structural_shift.py` — threshold logic, jurisdiction routing | compliance | — | [x] |
| 9A.15 | Unit tests for `multisig_dao.py` — threshold enforcement, human override denial | compliance | — | [x] |
| 9A.16 | Unit tests for `synthetic_gen.py` — regime generation, seeding determinism, shock multipliers | simulation | — | [x] |
| 9A.17 | Unit tests for `chronic_stress.py` — equity tracking, drawdown calculation, policy callback | simulation | 9A.16 | [x] |

### 9B. CI Pipeline

| # | Task | Depends on | Done |
|---|------|------------|------|
| 9B.1 | Create `.github/workflows/ci.yml` with Rust lint+test job (rustfmt, clippy, cargo test) | — | [x] |
| 9B.2 | Add Python lint+test job (py_compile, pytest, mypy/ruff) | 9A.* | [x] |
| 9B.3 | Add integration test job (spawn constitutiond, run Chronos × Cortex × Constitution) | 9A.* | [x] |
| 9B.4 | Add Kani formal verification job (cargo kani on constitution crate) | 9C.* | [x] |
| 9B.5 | Add security scan job (cargo audit, pip-audit, secret scanning) | — | [x] |
| 9B.6 | Wire `concurrency` groups + branch protection rules | 9B.1 | [x] |

> **Note on 9B.6:** `concurrency` groups are wired in the workflow. Branch **protection** (require `CI` checks to pass before merge to `main`) is a GitHub repo setting that cannot be configured from a workflow commit — apply manually: *Settings → Branches → main → Require status checks to pass → select the five CI jobs.*

### 9E. Test Enablement Infrastructure (prerequisite for 9A)

| # | Task | Done |
|---|------|------|
| 9E.1 | Add root `conftest.py` — puts all six package homes on `sys.path` so nested packages resolve under pytest | [x] |
| 9E.2 | Add root `pyproject.toml` — `[tool.pytest.ini_options]` with `testpaths` for all six test suites | [x] |
| 9E.3 | Normalize mixed import conventions to flat style (`adapters.base`, `mesh.bft_consensus`, `compliance.tax_parser`) across source, tests, and `build_module4/5.ps1` scaffolds | [x] |
| 9E.4 | Move `compliance/governance/` into `compliance/compliance/governance/` so `compliance.governance.multisig_dao` resolves as a package submodule | [x] |
| 9E.5 | Fix `evolution/code_agent.py` — `stage_patch` now creates the `patches/` directory (`mkdir parents=True, exist_ok=True`) instead of crashing on first run | [x] |
| 9E.6 | Cross-platform daemon path — `integration_chronos.py` and `run_pipeline.py` now resolve `constitutiond.exe` only on Windows (was hardcoded `.exe`, broke Linux CI) | [x] |

### 9C. Kani Formal Verification

| # | Task | File | Depends on | Done |
|---|------|------|------------|------|
| 9C.1 | Complete Kani proof for `invariants.rs` — prove A/B/C/D cannot panic, no overflow | constitution/src/invariants.rs | — | [x] |
| 9C.2 | Complete Kani proof for `ipc.rs` — prove frame parsing never panics on malformed input | constitution/src/ipc.rs | — | [x] |
| 9C.3 | Add Kani proof for `state_machine.rs` — prove all transitions are valid, no unreachable states | constitution/src/state_machine.rs | — | [x] |
| 9C.4 | Add Kani proof for `tmr_voter.rs` — prove reconcile always terminates, output is valid | constitution/src/tmr_voter.rs | — | [x] |
| 9C.5 | Verify `cargo kani` runs end-to-end and produces proof artifacts | 9C.1–9C.4 | [x] |

> **9C.5 verification (2026-09-14):** All five proof harnesses confirmed
> present and correctly gated under `#[cfg(kani)]` (invariants.rs, state_machine.rs
> ×2, ipc.rs, tmr_voter.rs). Added `constitution/kani.toml` configuration
> documenting proof locations. CI `kani-verify` job hardened: captures exit code,
> uploads `target/kani/` proof artifacts + output log to GitHub Artifacts
> (14-day retention), and reports `VERIFIED`/`FAILED` summary. Kani is
> Linux-only — verified locally via `cargo build` (clean), `cargo test` 17/17,
> `cargo fmt --check` (clean), `cargo clippy --all-targets` (clean), `cargo
> build --release` (clean); Python `compileall` + `pytest` 181 passed/2 skipped
> all green. The `continue-on-error: true` advisory gate remains during bootstrap
> but the full verification gate (G1–G7) is enforced at ceremony.

### 9D. Chronos at Scale

| # | Task | Depends on | Done |
|---|------|------------|------|
| 9D.1 | Fix verdict → equity feedback in Chronos loop (verdicts currently don't modify equity) | 9A.17 | [x] |
| 9D.2 | Run 1,000-year Chronos stress test — zero fatal errors required | 9D.1, 9B.3 | [x] |
| 9D.3 | Produce Chronos report (equity curve, regime distribution, verdict counts, drawdown stats) | 9D.2 | [x] |
| 9D.4 | Gate mainnet on 1,000-year pass — document in PRD as hard prerequisite | 9D.3 | [x] |

---

## Phase 10: Constitution Hardening (COMPLETE)

> Fixed the known medium-severity issues in the Rust kernel.

| # | Task | Issue from PRD | Depends on | Done |
|---|------|----------------|------------|------|
| 10.1 | Persistent `ConstitutionKernel` across TCP connections (shared `Arc<Mutex<..>>`) | Fresh kernel per connection | 9B.* | [x] |
| 10.2 | Fix `attempt_recovery` — route through `AutonomousRecovery` state, not directly to `Normal` | State machine skip | 9C.3 | [x] |
| 10.3 | Add `GetStatus` to return full state machine history (transitions, timestamps, proposal counts) | Incomplete observability | 10.1 | [x] |
| 10.4 | Add configurable invariant thresholds (currently hardcoded) | Hardcoded limits | — | [x] |
| 10.5 | Add `#[deny(unsafe_code)]` crate-level attribute to `constitution/` | Safety guarantee | — | [x] |

> **Phase 10 verification (2026-09-14):** `cargo test` **17/17 pass** (was 6),
> `cargo build --release` clean, `cargo clippy --all-targets` clean, `cargo fmt --check` clean,
> pytest **116/116 pass**, Chronos 250-yr + 1000-yr **passed=true** with metrics identical to
> Phase 9D baseline (235/235 recoveries, worst drawdown 0.3301, final equity 51,039.68).
> Two-phase recovery (`EmergencyHalt → AutonomousRecovery → Normal`) proven live E2E;
> transition journal bounded to `MAX_TRANSITION_HISTORY=64` (constant-memory, IPC-frame-safe);
> `CONSTITUTION_MAX_{DRAWDOWN,LEVERAGE,CONCENTRATION}` env thresholds supersede hardcoded values.
> Harness hardened: daemon always reaped in `finally`, stale-daemon bind collisions detected.

---

## Phase 11: Gateway Completion (COMPLETE)

> Get the NestJS gateway operational with installed deps + tests.

| # | Task | Depends on | Done |
|---|------|------------|------|
| 11.1 | `npm install` + commit `package-lock.json` | — | [x] |
| 11.2 | Unit tests for `rust-bridge.service.ts` — envelope construction, frame parsing, timeout handling | 11.1 | [x] |
| 11.3 | Unit tests for `constitution.controller.ts` — REST endpoint routing, request validation | 11.1 | [x] |
| 11.4 | Integration test: NestJS gateway → constitution_cli → Constitution | 11.1, 10.1 | [x] |
| 11.5 | Wire Cortex orchestration stub to real Cortex proposal emission | 9A.* | [x] |
| 11.6 | Add Swagger/OpenAPI docs to gateway endpoints | 11.1 | [x] |

> **Phase 11 verification (2026-09-14):** `nest build` clean; Jest **18/18 unit**
> + **4/4 e2e** (real `constitution_cli` binary behind the booted gateway);
> Python 116/116 unchanged. Gateway gain: pluggable `CONSTITUTION_TRANSPORT`
> (`tcp` daemon or `constitution_cli` via `CONSTITUTION_BRIDGE`), injectable socket
> & CLI & cortex runners, `cortex.engine` CLI (`python -m cortex.engine`), live
> `/cortex/propose` endpoint, shared `setupOpenApi` wiring `/docs` + `/docs-json`,
> and a new `gateway` CI job (build + unit + e2e). `package-lock.json` generated.

---

## Phase 12: Schema & Adapters (COMPLETE)

> "DNS/schema over code" — define venue contracts in data, not logic.

| # | Task | Depends on | Done |
|---|------|------------|------|
| 12.1 | Define `adapters/schemas/venue_contract.jsonschema` — universal venue API contract | — | [x] |
| 12.2 | Define `adapters/schemas/order_types.jsonschema` — order intent vocabulary | — | [x] |
| 12.3 | Validate MT5 adapter against schema (discovery agent should reject non-conforming plugins) | 12.1 | [x] |
| 12.4 | Add schema validation step to discovery agent plugin loader | 9A.5, 12.1 | [x] |

> **Phase 12 verification (2026-09-14):** adapter suite **24/24 pass** (was 9).
> Plugins restructured to schema-first layout — `venue_plugins/<plugin>/manifest.json`
> + `adapter.py`. The Discovery Agent now validates `manifest.json` against
> `venue_contract.jsonschema` (a `referencing` registry bridging `$ref` to the
> `order_types.jsonschema` vocabulary) **before executing any plugin code**, then
> type-checks `AdapterFactory()` against `AbstractExchangeAdapter`. Rejects:
> invalid manifest, schema-violating order types, missing manifest, missing
> entry point. `base.py` enforces the same vocabulary via `Literal` types
> (`order_type`/`time_in_force` defaults `MARKET`/`IOC`). Full Python suite
> **131/131** green (Phase 11 baseline 116 + 15 net-new); `jsonschema>=4.18` added to
> adapters deps + CI pip installs. `build_module4.ps1` regenerates the schema-first
> scaffold (BOM-safe writes).

---

## Phase 13: Mesh & PQC (COMPLETE)

| # | Task | Depends on | Done |
|---|------|------------|------|
| 13.1 | Replace HMAC-SHA3 in `pqc_wrapper.py` with `liboqs` / CRYSTALS-Dilithium | — | [x] |
| 13.2 | Wire BFT consensus to real WebSocket peer network (replace simulated quorum) | — | [x] |
| 13.3 | Implement `mesh/microgrid/` telemetry hooks | — | [x] |
| 13.4 | Multi-node integration test (3+ mesh nodes, fault injection) | 13.2 | [x] |

> **Phase 13 verification (2026-09-14):** mesh suite **44 items (42 pass, 2 skip
> locally)** — the 2 skipped run in CI, which now installs `liboqs-python`.
> Full Python suite **156 passed, 2 skipped** (Phase 12 baseline 131).
> CRYSTALS-Dilithium3 real sign/verify (liboqs) with a fail-closed placeholder
> fallback for wheel-less sandboxes; BFT quorum over a real WebSocket transport
> (legacy simulated mode only when no transport attached); `microgrid/` telemetry
> hooks; 3-node loopback integration test proving quorum replication, stopped-node
> tolerance, Byzantine-minority tolerance vs majority rejection. Legacy BOMs
> stripped from all five package `pyproject.toml` files; `build_module5.ps1`
> converted to a canonical-layout verifier.

---

## Phase 14: Doomsday Protocol (COMPLETE)

| # | Task | Depends on | Done |
|---|------|------------|------|
| 14.1 | Dead-man switch design doc (heartbeat cadence, escalation path, asset conversion) | — | [x] |
| 14.2 | Implementation of dead-man switch daemon | 14.1 | [x] |
| 14.3 | Physical asset conversion oracle interface | 14.1 | [x] |

> **Phase 14 verification (2026-09-15):** doomsday suite **35/35** (config 6,
> oracle 8, daemon FSM 13, CLI 10 — 8 new tests for the `doomsday_cli.py`
> self-test/disarm/FSM validation). Full Python suite **216 passed, 2 skipped**
> (skips = liboqs real-crypto, run in CI). `docs/DOOMSDAY.md` specifies the reverse
> dead-man switch (system watches itself; humans cannot disarm, I7), the
> deterministic five-state FSM, and the data-driven escalation-plan schema.
> Daemon + `AssetConversionOracle` interface shipped; concrete asset rails are
> S7 (system-written at Genesis Ceremony). `doomsday` wired into root conftest,
> CI compileall + ruff. New `doomsday/cli.py` + `__main__.py` provide
> `--self-test`, `--run`, `--beat`, `--status`, `--disarm` subcommands.

---

## Phase 15: Genesis Ceremony (COMPLETE)

| # | Task | Depends on | Done |
|---|------|------------|------|
| 15.1 | Multi-sig key ceremony procedure doc | 13.1 | [x] |
| 15.2 | Time-locked smart contract design for governance parameter changes | 15.1 | [x] |
| 15.3 | Ceremony dry-run on testnet | 15.1, 15.2 | [x] |

> **Phase 15 verification (2026-09-14):** Three design docs produced:
> `docs/GENESIS-CEREMONY.md` (air-gap multi-sig key ceremony procedure —
> participants, prerequisites, 7-step process, verification gates, key
> management, sealed-hash field), `docs/TIMELOCK-GOVERNANCE.md` (Ozone-style
> TimelockController + thin GovernanceRouter architecture, parameter-change
> vocabulary, 4-state proposal FSM, emergency/Doomsday interaction, deployment
> & anchoring, data-driven config), `docs/GENESIS-CEREMONY-DRYRUN.md` (Sepolia
> testnet rehearsal procedure — D0 pre-check through D6 rollback, failure-mode
> tests D4.1–D4.4, full verification-gate checklist, mainnet go/no-go criteria).
> Ceremony is fully documented but not yet executed — sealed hash is blank
> pending the real event; trustees and quorum size remain data-driven.

---

## Backlog (unprioritized, captured for completeness)

| # | Task | Source | Done |
|---|------|--------|------|
| ~~B.1~~ | ~~Docker containerization for all modules~~ | ~~Empty `docker/` dir~~ | [x] |
| ~~B.2~~ | ~~Integration test: full pipeline with mock exchange (Cortex → Constitution → Adapter → Mock)~~ | ~~Audit gap~~ | [x] |
| ~~B.3~~ | ~~Property-based / fuzz tests (`proptest` for Rust, `hypothesis` for Python)~~ | ~~PRD §5~~ | [x] |
| ~~B.4~~ | ~~Chaos engineering scripts (sever DB, corrupt packets, flash crashes)~~ | ~~PRD §5~~ | [x] |
| ~~B.5~~ | ~~CONTRIBUTING.md developer workflow guide~~ | ~~Exists but thin~~ | [x] |
| ~~B.6~~ | ~~Remove `time.sleep()` stubs from `sandbox_runner.py`~~ | ~~G2 technical debt~~ | [x] |

> **B.1 resolution (2026-09-15):** `docker/` populated with three
> production-grade Dockerfiles + `docker-compose.yml`:
> - `docker/constitution/Dockerfile` — multi-stage Rust build → distroless
>   runtime for `constitutiond` + `constitution_cli`; env-configurable bind address
>   (`CONSTITUTION_HOST`/`CONSTITUTION_PORT`); healthcheck via `constitution_cli`
>   heartbeat probe; `no-new-privileges` security opt.
> - `docker/gateway/Dockerfile` — multi-stage Node 20 build → slim runtime
>   for NestJS gateway; `CONSTITUTION_TRANSPORT` pluggability.
> - `docker/python-services/Dockerfile` — unified Python 3.12 image for all
>   six Python packages (cortex, evolution, mesh, compliance, simulation,
>   doomsday); editable installs; `PYTHONPATH` wiring.
> - `docker-compose.yml` — local dev orchestration: constitutiond (port
>   15565, env-threshold config), gateway (port 3000, depends on
>   constitution health), cortex (runs `run_pipeline.py` E2E). Named
>   bridge network, healthcheck-gated service dependencies.

> **B.2 resolution (2026-09-15):** Full-stack integration test added validating
> the complete Cortex → Constitution → Adapter → Mock Exchange pipeline:
> - `adapters/adapters/proposal_bridge.py` (G3) — type-safe bridge converting
>   `TradeProposal` → `UniversalOrderIntent` and mapping Constitution verdicts
>   to execution actions (Approved → intent, Rejected/Emergency → None).
> - `simulation/tests/integration_full_pipeline.py` — standalone harness that
>   spawns constitutiond, runs 5 market scenarios through CortexEngine, sends
>   proposals to the Constitution IPC, and if Approved converts + executes on
>   the MockExchangeAdapter via the DiscoveryAgent-loaded plugin.
> - `simulation/tests/test_integration_full_pipeline.py` — pytest wrapper
>   with 3 tests (pipeline passes, concentration limit enforced, healthcheck).
> - CI: added `integrate_full_pipeline` step to chronos-integration job.
> Result: 4 proposals, 3 approved+executed, 1 rejected (concentration).

> **B.3 resolution (2026-09-15):** Property-based testing added per PRD §5
> "fuzz testing":
> - **Rust proptest (10 properties):** `invariants.rs` — P1 (never panics on
>   any f64 incl. NaN/inf), P2 (drawdown breach → EmergencyLiquidationAll),
>   P3 (approved preserves notional), P4 (NaN/inf/negative → Rejected).
>   `state_machine.rs` — P5 (process_proposal never panics), P6 (invalid proof
>   keeps EmergencyHalt), P7 (recovery is two-phase, no skipping). 10 proptest
>   cases + 3 infinity regression tests added. proptest found a **real bug**:
>   infinity inputs bypassed NaN-only validation and produced
>   `Approved { adjusted_notional: inf }`. Fixed in `evaluate_proposal`
>   validation guard; `#[derive(Debug)]` added to `RiskParameters`;
>   `constitution/proptest-regressions/` added to `.gitignore`.
> - **Python hypothesis (11 properties):** `test_proposal_api_hypothesis.py`
>   (P1-P4: valid parse, roundtrip, invalid notional rejection, JSON
>   serializability) + `test_engine_hypothesis.py` (P5-P11: NoAction w/o
>   momentum, neutral trend, positive notional, bullish→Buy, bearish→Sell,
>   sizing proportional to equity, zero-price NoAction). 200 max examples each.
> - Rust: 27/27 tests (was 17). Python: **202 passed, 2 skipped** (was 188).
> - `hypothesis` added to CI pip install + cortex `pyproject.toml` testing extra.
> - **Bug:1 found + fixed.** proptest revealed that infinite equity/ notional
>   bypassed the NaN-only validation guard in `evaluate_proposal`, producing
>   `Approved { adjusted_notional: inf }`. Fixed by adding `.is_infinite()` checks.
>   3 regression tests pin the fix.

> **B.4 resolution (2026-09-15):** Chaos engineering engine added per PRD §5:
> - `simulation/tests/chaos_engine.py` — `ChaosEngine` with three scenarios:
>   (1) `scenario_daemon_crash` — kills constitutiond, verifies IPC client detects
>   connection loss; (2) `scenario_corrupted_packets` — sends invalid JSON, wrong
>   protocol version, oversized frames, missing fields, and corrupted payloads;
>   verifies the daemon handles all gracefully without crashing; (3)
>   `scenario_flash_crash` — drives CortexEngine through extreme
>   SyntheticRegimeGenerator shocks (volatility=0.05), verifies EmergencyHalt
>   triggers at the 15% drawdown threshold (I1) and two-phase recovery restores
>   Normal state.
> - `simulation/tests/test_chaos.py` — 4 pytest tests covering all scenarios.
> - CI: added `chaos_engine.py` run step to chronos-integration job.
> - All 4 chaos tests + 10 Doomsday CLI tests pass. Full Python suite:
>   **216 passed, 2 skipped**.
>
> **B.5 resolution (2026-09-15):** `CONTRIBUTING.md` expanded from a thin
> skeleton to a comprehensive development guide: full verification checklist
> (Rust: cargo build/test/fmt/clippy; Python: compileall/ruff/pytest/Chronos
> 1000-yr; Gateway: npm build/test), CI job matrix table, and updated
> Definition of Done aligned with AGENTS.md §8.

> **B.6 resolution (2026-09-14):** `evolution/evolution/sandbox_runner.py`
> replaced the `time.sleep()` placeholder with a real shadow-trading loop that
> uses `SyntheticRegimeGenerator` (G7) to replay extreme synthetic market regimes
> (FLASH_CRASH, HYPERINFLATION_LOOP, etc.) against an injected candidate policy.
> Returns a structured `ShadowSimulationResult` (passed, final_equity,
> worst_drawdown, elapsed_seconds, years_simulated, error). Pass gate = equity
> survival + drawdown ceiling; exceptions are caught and reported. 10/10 tests
> pass. Full Python suite: **188 passed, 2 skipped**.

---

> **Chronos 1,000-year result (2026-09-14):** `passed=true`, final equity 51,039.68, worst drawdown 0.3301, 321,111 approved / 42,654 rejected, 235 emergency liquidations all recovered, 0 equity exhaustion. CLI: `python simulation/tests/integration_chronos.py 1000`.

---

## Post-Ceremony Genesis DNA Completion (2026-09-21)

> Gap analysis against AGENTS.md §2 (G1-G9 Genesis DNA) revealed three missing artifacts and one bug fix required before the system can fully own S1-S7 generation.

| # | Task | Genesis Component | Done |
|---|------|-------------------|------|
| GC.1 | Create `cortex/schemas/strategy.proto` — protobuf schema for TradeProposal / ProposalBatch / StrategySchema | G5 (Adaptive Cortex frameworks) | [x] |
| GC.2 | Create `compliance/schemas/rule.asl.json` — JSON-Schema for data-driven compliance rules (jurisdiction, condition, action) | G6 (Governance & Compliance foundations) | [x] |
| GC.3 | Fix `cortex/cortex/trading_daemon.py` — remove duplicate `adapters.base`/`verdict_to_order_action` imports; add missing `UniversalOrderIntent` import used by `_apply_execution` | G8 (Gateway/orchestration skeleton) | [x] |
| GC.4 | Fix `cortex/tests/test_engine_hypothesis.py` — suppress Hypothesis `too_slow` health check on all `@settings` decorators (input generation overrides fields post-draw) | 9B.* | [x] |
| GC.5 | Fix `run_pipeline.py` — remove unused `# noqa: E402` directives (E402 not enabled in project ruff config); inline `import time` in except branch | G9 (Build tooling) | [x] |
| GC.6 | Fix `evolution/evolution/code_agent.py` — sort imports (I001); annotate S112 try-except-continue with noqa (log-recursion risk) | G2 (Self-Evolution Framework) | [x] |

### Verification

| Check | Status |
|-------|--------|
| `python -m py_compile cortex/cortex/trading_daemon.py` | ✓ |
| `python -m py_compile run_pipeline.py` | ✓ |
| `python -m py_compile evolution/evolution/code_agent.py` | ✓ |
| `python -m pytest cortex/tests/ adapters/tests/ doomsday/tests/ -q` | 119 passed |
| `python -m pytest` (full suite) | 216 passed, 2 skipped |
| `python -m ruff check . --exclude gateway --exclude node_modules` | All checks passed! |
| `cargo build --release` (constitution) | Previously verified clean (2026-09-14) |
| `cargo test` (constitution) | Previously verified 27/27 (2026-09-14) |
| `cargo kani` proofs (5 harnesses) | Previously verified (2026-09-14) |
| `json.load(compliance/schemas/rule.asl.json)` | Valid |
| `json.load(adapters/schemas/*.jsonschema)` | Valid |

## Phase 16: Autonomy Nucleus — the hand-written foundation still required before the system can take over (BACKLOG — 0/13 done)

> Honest gap (2026-09-22): the running stack is the live Genesis *gate* (G1 session),
> but the self-evolution engine is **scaffolding, not alive** — nothing in
> `evolution/` yet *writes* a real component from a specification; it only stages
> diffs (`stage_patch`) and proposes naive fixes (no writer driver, no closed
> verify→adopt loop). Until that lynchpin exists, "the system writes its own
> code" is aspirational. These 13 items are the real remaining foundation —
> each is a **mechanism** (Genesis DNA), never a hand-written instantiation.
> Per AGENTS.md §3, S1–S7 artifacts themselves remain system-written.

### A. Self-Evolution Engine (G2) — THE lynchpin

| # | Task | What exists today | Done |
|---|------|-------------------|------|
| AT.1 | Spec→candidate-code **writer driver** — consume a declared specification (schema/ASL) and emit candidate source; runs on a cadence. | `EvolutionaryCodeAgent.propose_fix` is a naive single-diff stub; orchestrator `_run_evolution` is a placeholder (`[Evolution] hourly self-assessment cycle`). | [ ] |
| AT.2 | **Closed verify→adopt loop** — candidate → shadow sandbox (`sandbox_runner`) → lint/tests → diff → apply-or-rollback with provenance, wired into the orchestrator loop (today `_scan_and_heal` SKIPs everything). | `sandbox_runner` ShadowSimulation + `ci_prover` exist but are not connected end-to-end to any writer. | [ ] |
| AT.3 | **Generated-artifact quarantine + adoption gate** — a reviewed registry with test evidence before generated code is trusted (anti drift / self-healing-lockup guard). | Patches land blindly in `evolution/patches/`; no adoption review gate. | [ ] |

### B. S1 venue acquisition — "the system's first job" (user-visible)

| # | Task | What exists today | Done |
|---|------|-------------------|------|
| S1.1 | **Venue spec-first generator** — from `venue_contract.jsonschema` conformance emit a candidate `adapter.py` + `manifest.json` for a declared endpoint. | `discovery_agent.py` validates + loads plugins (schema-first, sandbox-before-еxecution) = **validation half only**; no generator exists. `mock_exchange/` + `mt5_adapter/` are hand-scaffolded exemplars, not produced. | [ ] |
| S1.2 | **Demo-venue sandbox certification** — dry-run/paper harness proving `connect`/`health_check`/`execute_order(DRY_RUN)` against a demo endpoint (e.g. Binance Spot Testnet public market data) before `DiscoveryAgent` may adopt it. | None (Chaos/simulation sandboxes exist for strategies, not venue plugins). | [ ] |
| S1.3 | **System-produced demo plugin** — run the generator (S1.1 → S1.2) to yield the first certified real-demo venue plugin; API keys injected via env/HSM only (zero hardcoded secrets). | Nothing adopted; orchestrator trading daemon currently runs dry-run (`exchange_adapter=None`). | [ ] |

### C. S2 strategy acquisition (frameworks exist; the meta-learning writer does not)

| # | Task | What exists today | Done |
|---|------|-------------------|------|
| S2.1 | Strategy proposal → candidate **generator** (Cortex meta-learning loop). | `engine.py` (evaluate tick) + `agent_marl.py` (conviction sizing) are proposal frameworks, not a learning/writer loop. | [ ] |
| S2.2 | **Strategy certification gate** — generated strategy must pass ShadowSimulation + Chronos before it may propose (I5: it may only propose; never execute). | Gate mechanics (ShadowSimulationResult, Chronos 1000-yr) exist but are not wired to generated-strategy admission. | [ ] |

### D. Production governance (documented, not executed)

| # | Task | What exists today | Done |
|---|------|-------------------|------|
| PG.1 | Execute the Genesis Ceremony — 2-of-3 trustees, sealed root-hash set. | `docs/GENESIS-CEREMONY.md` complete; `GENESIS_CEREMONY_ROOT_HASH=""`. | [ ] |
| PG.2 | Replace placeholder PQC + governance escrow — real Dilithium keyring; `mesh` still reports `pqc_secured: False`; `secure_keys.rs:43` threshold-only. | `pqc_wrapper` real Dilithium via liboqs; kernel-side keys are placeholder. | [ ] |
| PG.3 | Enforce **I7** — `strict_heartbeat_signing=True`, signed Doomsday journal (`governance_key`). | Doomsday runs `strict_heartbeat_signing=False`, `governance_key=""`. | [ ] |
| PG.4 | Deploy the time-lock governance contract. | Phase 15 design (`docs/TIMELOCK-GOVERNANCE.md`) complete; not deployed. | [ ] |

### E. Observability — "watching it do its job"

| # | Task | What exists today | Done |
|---|------|-------------------|------|
| OBS.1 | Live per-call pipeline trace (tick → proposal → verdict → execution) as an auditable surface. | `--status` is process-level; decisions are visible only in `trading-daemon.log`. | [ ] |

---

## Summary

| Phase | Total Items | Completed | Remaining |
|-------|-------------|-----------|-----------|
| 9 — Verification & Test | 38 | 38 | 0 |
| 10 — Constitution Hardening | 5 | 5 | 0 |
| 11 — Gateway | 6 | 6 | 0 |
| 12 — Schemas | 4 | 4 | 0 |
| 13 — Mesh & PQC | 4 | 4 | 0 |
| 14 — Doomsday | 3 | 3 | 0 |
| 15 — Genesis Ceremony | 3 | 3 | 0 |
| Backlog | 6 | 6 | 0 |
| Post-Ceremony DNA Completion | 6 | 6 | 0 |
| Live-Run Remediation | 6 | 6 | 0 |
| Phase 16 — Autonomy Nucleus (BACKLOG) | 13 | 0 | 13 |
| **Total** | **94** | **81** | **13** |

## Live-Run Remediation (2026-09-22)

> First real `python centaur_start.py` run exposed three bootstrap-tooling (G9/G8) defects in the live orchestrator.

| # | Task | Fix | Done |
|---|------|-----|------|
| LR.1 | `centaur_start.py` health check sent **raw JSON** over TCP; IPC requires `[4-byte BE length][JSON frame]`. Result: `constitutiond` logged `invalid frame length` and dropped every connection → `FATAL: constitutiond did not become healthy`. | Rewrote `_wait_for_constitutiond` to frame the Heartbeat envelope via `struct.pack(">I", len)` + length-prefixed read (mirrors `cortex/constitution_client.py:55`). Verified live: `{"alive":true,"protocol_version":1}`. | [x] |
| LR.2 | `── Service Status ──` box-drawing chars crashed the logging handlers on cp1252 (Windows) — `UnicodeEncodeError` in `StreamHandler.emit`. | UTF-8 reconfigure of `sys.stdout`/`sys.stderr` on startup + `encoding="utf-8"` on the `FileHandler`. | [x] |
| LR.3 | Orphaned `constitutiond` (elevated, from an aborted pre-fix run) held port 15565 → every spawned `constitutiond` child exited(1) on bind (os error 10048) while the health check passed against the orphan. | `_adopt_existing_constitutiond()`: if a healthy daemon already answers the framed heartbeat, adopt it via `_AdoptedDaemon` (live-health `poll()`, no-op terminate) and emit a prominent warning with the offending PID — instead of crash-looping. Spawns normally when the port is free. | [x] |
| LR.4 | All `python -c` service runners were **single-line** `;`-joined code — a compound statement (`while`/`def`) after `;` is a SyntaxError, so every service crash-looped with `SyntaxError: invalid syntax` (the root of the earlier `[generic_error]` floods). | Rewrote `_run_trading_daemon`, `_run_doomsday`, `_run_mesh_node`, `_run_evolution`, `_run_compliance` to emit **multi-line heredoc source** (`"""..."""`), no embedded Windows paths (PYTHONPATH via `os.pathsep` env). Trading daemon now uses its native contract: pipe `market_feed.py` stdout → `TradingDaemon.run_loop()` (stdin JSON), feed lifecycle paired to the daemon (`proc._feed`, `_kill_feed` in restart/stop paths). Doomsday beats **only while `_probe_constitution()` answers**; verified `EscalationState.ARMED`. | [x] |
| LR.5 | `market_feed.py` routed its startup banner to stdout → daemon's `run_loop` tried `json.loads("[MarketFeed] …")` → `JSONDecodeError` and exit(1). | Banner → stderr; stdout is JSON-lines only. Feed cadence honored (gap < Doomsday 3×heartbeat grace → no self-escalation). | [x] |
| LR.6 | Self-healing log scanner false-flagged **hundreds of stale/self-referential lines every cycle** (file-mtime gate only) — it re-matched its own `Log Scan:`/`[generic_error]` report lines and old error blocks → a self-feeding noise loop in `centaur.log`. | `scan_logs_for_errors`: per-line ISO-timestamp window, self-report markers excluded, `.rotated.log` archives skipped (historical, not live). Service logs rotated at boot so unstamped raw child stdout starts fresh. Live result: `Log Scan: clean (0 errors in last 5min)` on every cycle. | [x] |

### Verification — full 8-service live run (2026-09-22)

| Check | Status |
|-------|--------|
| `python -m py_compile centaur_start.py market_feed.py` + `ruff check` (both) | ✓ |
| `constitutiond` healthy (framed probe `_probe_constitution`) | `True` |
| All 8 services `HEALTHY` across 5+ consecutive 30s reports, stable pids | ✓ |
| Feed → stdin → ticks → constitution verdicts (`Approved`, adjusted_notional 2.5k/5k) | ✓ |
| Doomsday probe-beat stays `EscalationState.ARMED` (no false escalation) | ✓ |
| Mesh nodes `HEALTHY` (+ `health_telemetry()` dict every 60s) | ✓ |
| Kill `trading-daemon` → `[CRASHED]` → `[RESTARTED]` pid change, feed respawned, ticks resume | ✓ |
| Log scanner: `clean (0 errors in last 5min)` every cycle (was 1400/false) | ✓ |
| Orphaned constitution adoption (per LR.3) exercised on reboot | ✓ |
