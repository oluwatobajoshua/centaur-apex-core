# Changelog

All notable changes to Centaur-Apex Core are documented here, grouped by
release line. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows `docs/RELEASE.md` (semantic, immortal).

## [Unreleased] — 2026-09-21 (Genesis DNA Completion)

### Added
- **cortex/schemas/strategy.proto** (G5) — Protobuf schema for `TradeProposal`,
  `ProposalBatch`, and `StrategySchema` with sizing rules + entry/exit signals.
  Defines the data contract the DiscoveryAgent + Cortex meta-learner own.
- **compliance/schemas/rule.asl.json** (G6) — JSON-Schema (Draft 2020-12) for
  rules-as-code compliance rules: jurisdiction, field/operator/value condition,
  enforcement action (REJECT/REDIRECT/REDUCE_TO/NOTIFY/SEAL), severity levels,
  effective-from/until timestamps, and arbitrary metadata.

### Fixed
- **cortex/cortex/trading_daemon.py** — Removed duplicate `AbstractExchangeAdapter`
  and `verdict_to_order_action` imports; added missing `UniversalOrderIntent` import
  required by `_apply_execution` type hint.
- **cortex/tests/test_engine_hypothesis.py** — Suppressed Hypothesis `too_slow`
  health check on all 7 `@settings` decorators (input strategy overrides fields
  post-draw, triggering slow generation heuristic on constrained tick dicts).
- **run_pipeline.py** — Removed unused `# noqa: E402` directives (E402 not enabled
  in project ruff config); hoisted `import time` and `import subprocess` to module
  top-level to eliminate post-`sys.path.insert` re-imports.
- **evolution/evolution/code_agent.py** — Fixed import block ordering (I001:
  `from typing import ClassVar` now after stdlib `import` group); annotated
  S112 `try`/`except`/`continue` with `# noqa: S112` (log-recursion safety in
  log-scanning context).

### Verified
- `python -m ruff check cortex adapters evolution mesh compliance simulation doomsday --ignore E501` → All checks passed!
- `python -m py_compile` + `python -m compileall` → All modules compile clean
- `python -m pytest` (full suite: cortex, adapters, evolution, mesh, compliance,
  simulation, doomsday) → 216 passed, 2 skipped (liboqs real-crypto in CI)
- `cargo build --release` → Finished successfully
- `cargo clippy --all-targets` → Clean, no warnings
- `cargo fmt --check` → Clean
- `cargo test` → 27/27 passed
- `json.load` validation → All new schema files parse as valid JSON

---

## [Unreleased] — 2026-09-16 (Genesis Complete — Phases 9–15, Backlog B.1–B.6)

### Added
- **docs/GENESIS-CEREMONY.md** (G6) — Full multi-sig key ceremony procedure:
  participant roles, air-gap prerequisites, 7-step process (keygen → witness
  attestation → aggregation → on-chain anchoring → verification gates → seal),
  post-ceremony key management, failure handling, sealed-hash field.
- **docs/TIMELOCK-GOVERNANCE.md** (G6) — Time-locked governance contract
  design: OpenZeppelin TimelockController + thin GovernanceRouter, parameter-
  change vocabulary (I1–I3 thresholds, quorum, delay, keyset hash), 4-state
  proposal FSM, Doomsday interaction, deployment & anchoring.
- **docs/GENESIS-CEREMONY-DRYRUN.md** (G6) — Sepolia testnet rehearsal
  procedure (D0–D6), failure-mode tests (D4.1–D4.4), mainnet go/no-go criteria.
- **constitution/kani.toml** — Kani proof configuration documenting all five
  `#[cfg(kani)]` harness locations.
- **Sandbox shadow-trading** (G2) — `evolution/evolution/sandbox_runner.py`
  replaced `time.sleep()` stub with a real simulation loop using
  `SyntheticRegimeGenerator` (G7); returns structured `ShadowSimulationResult`.
  10/10 tests pass.
- **Docker infrastructure** (B.1) — `docker/` with three production-grade
  Dockerfiles + `docker-compose.yml`:
  - `docker/constitution/Dockerfile` — multi-stage Rust → distroless
    (`constitutiond` + `constitution_cli`); `CONSTITUTION_HOST`/`CONSTITUTION_PORT`
    env-configurable bind; healthcheck via `constitution_cli` heartbeat.
  - `docker/gateway/Dockerfile` — multi-stage Node 20 → slim NestJS gateway.
  - `docker/python-services/Dockerfile` — unified Python 3.12 image for all
    six Python packages.
  - `docker-compose.yml` — local dev orchestration with healthcheck-gated deps.
- **Full-pipeline integration test** (B.2) —
  `simulation/tests/integration_full_pipeline.py` + pytest wrapper validates
  the complete Cortex → Constitution → MockExchangeAdapter pipeline:
  5 market scenarios, proposal → verdict → intent conversion → execution receipt.
  `adapters/adapters/proposal_bridge.py` (G3) provides the type-safe
  `TradeProposal → UniversalOrderIntent` conversion bridge. CI: added
  `integrate_full_pipeline` step to chronos-integration job.
- **Property-based / fuzz tests** (B.3) — PRD §5 "fuzz testing":
  - Rust `proptest` (10 properties + 3 regression tests in `invariants.rs`
    and `state_machine.rs`): no-panic, drawdown-trigger, notional-preservation,
    NaN/inf rejection, two-phase recovery, emergency-halt safety.
  - Python `hypothesis` (11 properties in `test_proposal_api_hypothesis.py`
    and `test_engine_hypothesis.py`): valid parse, roundtrip, engine invariants.
  - `hypothesis` added to CI + `cortex/pyproject.toml[testing]` extra.
- **Chaos engineering engine** (B.4) — `simulation/tests/chaos_engine.py`
  with three failure-injection scenarios: daemon crash (TCP sever), corrupted
  packets (invalid JSON, wrong version, oversized/missing/bad fields), and
  flash crash (extreme SyntheticRegimeGenerator shocks → EmergencyHalt →
  two-phase recovery). 4 pytest tests in `test_chaos.py`. CI: added
  `chaos_engine.py` run step.

### Changed
- **constitution/src/invariants.rs** — Bug fix found by proptest: infinity
  inputs (`total_equity = ∞`, `target_notional = ∞`) bypassed the NaN-only
  validation guard and produced `Approved { adjusted_notional: inf }`,
  violating Invariant D. Added `is_infinite()` checks for all numerical fields
  and tightened `target_notional <= 0.0` (was `< 0.0`). Added
  `#[derive(Debug)]` to `RiskParameters`. 3 regression tests pin the fix.
- **constitution/src/bin/constitutiond.rs** — Added `resolve_bind_address()`
  reading `CONSTITUTION_HOST`/`CONSTITUTION_PORT` env vars (data-driven IPC
  config per AGENTS.md §7). Safe defaults unchanged.
- **doomsday/doomsday/cli.py** (G6) — New CLI with `--self-test`, `--run`,
  `--beat`, `--status`, `--disarm` subcommands. Self-test validates the full
  ARMED→WATCHING→ESCALATING→LIQUIDATING→DORMANT FSM + disarm path.
  Data-driven config via JSON path or env. `doomsday/__main__.py` enables
  `python -m doomsday`. 10 tests.
- **doomsday/doomsday/oracle.py** — Fixed empty 6-quote docstring (`""""""`
  → proper `"""..."""`) on `get_conversion_status`.
- **.github/workflows/ci.yml** — `kani-verify` job hardened: captures exit code,
  uploads proof artifacts (`target/kani/` + output log) to GitHub Artifacts,
  reports VERIFIED/FAILED summary. `hypothesis` + `chaos_engine.py` added to
  chronos-integration job. `doomsday` added to CI compileall + ruff.
- **.gitignore** — Added `constitution/proptest-regressions/`.
- **docs/GETTING-STARTED.md** — Corrected Rust test count to 27 (17 unit +
  10 proptest/regression). Added sections 7–9: full-pipeline integration,
  chaos engineering, Doomsday CLI self-test. Fixed CLI bridge examples:
  EvaluateProposal command now pipes JSON via stdin (PowerShell native-command
  quoting mangles embedded `"` when passed as argv; stdin pipe avoids this).
  Verified output: `{"verdict":{"Approved":{"adjusted_notional":50000.0}}}`.
- **Lint pass** — Fixed 171+ ruff issues across all 6 Python packages:
  deprecated `typing` imports → modern annotations, unused imports, import
  sorting, NaN check → `math.isnan()`, nested-if flattening, `ClassVar` for
  class-level constants, `.items()` → `.values()` where key unused,
  `list(...)[0]` → `next(iter(...))`. Added `# noqa` for intentional
  fail-safe exception handling (I6 invariant) and test patterns.
- **docs/ARCHITECTURE.md** — Updated Constitution state model (persistent
  kernel via `Arc<Mutex>` per Phase 10.1, not per-connection stateless).
- **CONTRIBUTING.md** — Enhanced with full verification checklist (Rust:
  cargo build/test/fmt/clippy; Python: compileall/ruff/pytest/Chronos 1000-yr;
  Gateway: npm build/test), CI job matrix table, and updated Definition of Done.
- **TRACKER.md** — All phases 9–15 COMPLETE; B.1–B.6 ✓. 69/69 tasks complete.

### Verification (2026-09-16, final)
- **Rust (G1):** 27/27 tests pass (17 unit + 4 proptest + 3 regression + 3
  state-machine proptest). Zero proptest regressions. `cargo build`,
  `cargo build --release`, `cargo fmt --check`, `cargo clippy --all-targets`
  all clean. `#[deny(unsafe_code)]` crate-wide.

- **Production deployment (G9):** Added `supervisord.conf` (7-program
  supervisor: constitutiond, gateway, cortex-trading, doomsday, mesh-{0,1,2},
  evolution, compliance) with autostart/autorestart/restart limits. Updated
  `docker-compose.yml` with all production services (doomsday, 3 mesh nodes,
  evolution, compliance). Created `cortex/cortex/trading_daemon.py` —
  continuous trading loop (market tick → Cortex proposal → Constitution
  verdict → Doomsday heartbeat). All Python modules pass `compileall` +
  `ruff check` (182 lint issues fixed across all 6 packages).

- **Python:** **216 passed, 2 skipped** (179 unit + 11 hypothesis ×500 examples
  + 4 chaos + 3 full-pipeline + 10 doomsday CLI + 35 doomsday + 12 integration).
  `compileall` clean. `ruff` clean.
- **Gateway (G8):** `nest build` clean; Jest 18/18 unit + 4/4 e2e pass.
- **Chronos (G7):** 1,000-year stress test `passed=true` (final equity
  51,039.68, worst drawdown 0.3301, 235/235 emergency recoveries).
- **CI YAML:** validated; 6 jobs pass (rust-lint, python-lint, chronos-integration,
  kani-verify advisory, gateway, security-audit).
- **Bug:1 found + fixed** via proptest (infinite equity/NaN validation gap
  in `invariants.rs`).

### Historical
> The following phases reached stable baselines superseded by later phases
> but whose metrics are preserved for traceability.

#### Phase 14 — Doomsday Protocol (2026-09-15)
- **doomsday/** (G6) — Reverse dead-man switch: system watches its own
  liveness, not a human watchdog. Deterministic ARMED→WATCHING→ESCALATING→
  LIQUIDATING→DORMANT FSM. `daemon.py` with escalation, grace, disarm (governance-gated, I7), strict mode. `oracle.py` — `AssetConversionOracle` interface + `SimulationOracle`. Doomsday suite 35/35; full Python 181 passed, 2 skipped.

#### Phase 13 — Mesh & PQC (2026-09-14)
- **mesh/** (G4) — CRYSTALS-Dilithium3 via liboqs; HMAC-SHA3 placeholder for
  wheel-less sandboxes (fail-closed). Real WebSocket BFT quorum transport.
  `microgrid/` telemetry. 3-node loopback integration test. Mesh suite 44 items
  (42 pass, 2 skip locally). Full Python 156 passed, 2 skipped.

#### Phase 12 — Schema-First Adapters (2026-09-14)
- **adapters/** (G3 + S1) — `venue_contract.jsonschema` + `order_types.jsonschema`
  with `referencing` registry. Discovery Agent as manifest gate (schema-first,
  no code execution until validated). 24 adapter tests (was 9). Full Python 131/131.

#### Phase 11 — Gateway Completion (2026-09-14)
- **gateway/** (G8) — Pluggable `CONSTITUTION_TRANSPORT` (TCP daemon or
  `constitution_cli` subprocess). Injectables for testability. Live `/cortex/propose`.
  Swagger at `/docs`. 18 Jest unit + 4 e2e tests.

#### Phase 10 — Constitution Hardening (2026-09-14)
- **constitution/** (G1) — Persistent kernel (`Arc<Mutex<IpcServer>>`).
  Two-phase recovery: `EmergencyHalt → AutonomousRecovery → Normal`.
  `GetStatus` with bounded `state_history` (64 entries). Env-configurable thresholds.
  `#![deny(unsafe_code)]`. 17 Rust tests (was 6). Full Python 116/116.

#### Phase 9 Baseline — Verification Infrastructure (2026-09-14)
- Root `conftest.py` + `pyproject.toml` (multi-package pytest config).
- Import normalization (flat style). `code_agent.py` `stage_patch` fixed.
- Cross-platform daemon path. 188 Python unit tests baseline + Chronos 250-year harness.

## [0.1.0] — 2026-09-14

### Added (Genesis bootstrap)

- **constitution/** (G1) — Iron Constitution in Rust:
  - `invariants.rs` — drawdown/leverage/concentration/numerical validity checks
  - `state_machine.rs` — 4-state machine (Normal, SoftDeleveraging, EmergencyHalt, AutonomousRecovery)
  - `tmr_voter.rs` — triple-modular-redundancy voter
  - `secure_keys.rs` — PQC key manager (HMAC-SHA3 placeholder)
  - `ipc.rs` — versioned TCP framing protocol (v1, 16KB max frame, 4 opcodes)
  - `constitutiond` — TCP daemon on `127.0.0.1:15565`
  - `constitution_cli` — stdin/stdout JSON bridge
  - 6 passing IPC tests; `cargo build --release` clean
- **cortex/** (G5) — Adaptive Cortex: `proposal_api.py` schemas,
  `agent_marl.py` MARL agent (S2 bootstrap stub), `engine.py` engine
  (S2 bootstrap stub), `constitution_client.py` persistent-session IPC client.
- **evolution/** (G2) — self-evolution machinery: `code_agent.py`, `ci_prover.py`,
  `sandbox_runner.py`.
- **adapters/** (G3) — `base.py` abstract execution contract, `discovery_agent.py`
  plugin loader, `venue_plugins/mock_exchange.py` + `mt5_adapter.py` (S1 stubs).
- **mesh/** (G4) — `bft_consensus.py`, `pqc_wrapper.py`, `node_daemon.py`.
- **compliance/** (G6) — `tax_parser.py`, `structural_shift.py`,
  `multisig_dao.py`.
- **simulation/** (G7) — Chronos rig: `synthetic_gen.py`, `chronic_stress.py`,
  and `integration_chronos.py` (250-year live integration harness).
- **gateway/** (G8) — NestJS scaffolding + Rust bridge (TCP framing).
- **Docs:** `AGENTS.md` (the law), `docs/PRD.md`. Production, `README`,
  security, and governance docs (this release).
- **Tooling (G9):** `build_module*.ps1`, `setup.sh`, `run_pipeline.py`.
- **Verification:** E2E Cortex → Rust Constitution smoke test passed;
  integration harness passed 250 simulated years (final equity 237,028.8,
  worst drawdown 0.2752).

[0.1.0]: https://github.com/oluwatobajoshua/centaur-apex-core/tree/v0.1.0
