# Contributing to Centaur-Apex Core

> **Read [AGENTS.md](AGENTS.md) first.** It is the binding law for every human
> and AI agent touching this repository. If there is a conflict between this
> guide and AGENTS.md, AGENTS.md wins.

## Who may contribute

This is a **closed-source proprietary project**. Contributions are internal
unless you have been authorized in writing by the copyright holder. See
`LICENSE`.

## The Grading Question

Before any change, ask:

> **"If the system's evolution engine existed today, would it own this file?"**

- **Yes** → stop. Write the *tooling* that lets the system generate it, not
  the artifact itself (this is the bootstrapping principle).
- **No, it is Genesis DNA** → proceed, but keep it reusable, data-driven, and
  replaceable, never a hand-finalized instantiation.

## Types of changes

| Type | Allowed? | Gate |
|------|----------|------|
| Genesis DNA (mechanisms, invariants, scaffolding) | Yes | Described below |
| Bootstrap stubs explicitly marked S1–S7 that the system will replace | Yes | Must carry a `SYSTEM-OWNED STUB` header comment |
| Concrete strategies, venue connectors, or transpiled artifacts treated as final assets | **No** | Rejected |
| `constitution/` invariant changes | Only via formal verification + multi-sig governance (AGENTS.md §6) | Never merged by direct write |

## Development workflow

1. Clone and build (see `docs/GETTING-STARTED.md`).
2. Create a feature branch: `feat/<thing>`, `fix/<thing>`, `docs/<thing>`.
3. Make the change. Follow `docs/CODING-STANDARDS.md`.
4. Verify locally:

   ```powershell
   # Rust (constitution/)
   cargo build --release
   cargo test
   cargo fmt --check

   # Python (all modules + tests)
   python -m py_compile <files...>
   python simulation/tests/integration_chronos.py

   # Live pipeline
   python run_pipeline.py
   ```

5. Open a PR against `main` (PR template enforced). All checks must pass.
6. A maintainer reviews; `main` is protected — no direct pushes, no force-push.

## Commit message convention

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
`<type>(<scope>): <subject>` — e.g. `feat(constitution): add stdin/stdout
JSON bridge`, `fix(cortex): clamp zero-notional proposals`.

Allowed types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`,
`security`.

## Definition of done

- [ ] Aligned with one of G1–G9, or intentionally adds machinery for S1–S7
- [ ] No hardcoded strategy/venue logic added as a permanent asset
- [ ] No unconverted `SYSTEM-OWNED STUB` left where the system should own it
- [ ] `cargo build --release` + `cargo test` pass (Rust changes)
- [ ] `python -m py_compile` passes (Python changes)
- [ ] No secrets, credentials, or private keys introduced
- [ ] Relevant docs updated (`README.md`, `docs/`, `AGENTS.md` sync points)

## Security

See `SECURITY.md`. Never open a public issue for a vulnerability; report via
Private Security Advisory.

## Code of conduct

Professional, constructive behavior is expected in issues, PRs, and internal
channels. Harassment, doxxing, or intimidation is not tolerated. Violations
can be reported through the same private channel as security issues.