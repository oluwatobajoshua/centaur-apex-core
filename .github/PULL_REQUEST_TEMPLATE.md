## Description

<!-- What does this change do? Link the issue if one exists. -->

## Genesis-DNA classification

<!-- Which G1–G9 does this touch, or which S1–S7 machinery does it add?
     If this adds a concrete strategy/venue/alpha as a final asset, it must be rejected. -->

- [ ] Genesis DNA (mechanism/framework/invariant)
- [ ] Bootstrap stub clearly marked SYSTEM-OWNED (Sx)
- [ ] No system-written artifact added as a permanent asset (`AGENTS.md` §3)

## Verification

- [ ] `cargo build --release` + `cargo test` pass (Rust changes)
- [ ] `python -m py_compile` passes (Python changes)
- [ ] `simulation/tests/integration_chronos.py` passes (if touched)
- [ ] No secrets / keys introduced
- [ ] Docs updated (`README.md`, `docs/`, `AGENTS.md` sync points)
- [ ] No new warnings introduced

## Reviewer checklist

- [ ] Texture check: would the Evolution Sub-Agent own this file if it existed today?
- [ ] Invariant check: does this weaken I1–I8 in any way?
- [ ] Scope check: no business alpha hardcoded as a permanent asset.