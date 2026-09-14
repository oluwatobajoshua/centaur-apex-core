# Changelog

All notable changes to Centaur-Apex Core are documented here, grouped by
release line. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows `docs/RELEASE.md` (semantic, immortal).

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