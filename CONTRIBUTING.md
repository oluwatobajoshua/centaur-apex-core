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

1. Read `AGENTS.md` — it is binding law. Every file must be classified as
   Genesis DNA (G1–G9) or System-Written (S1–S7) before you write it.
2. Clone and build (see `docs/GETTING-STARTED.md`).
3. Create a feature branch: `feat/<thing>`, `fix/<thing>`, `docs/<thing>`.
4. Make the change. Follow `docs/CODING-STANDARDS.md`.
5. Verify locally — see **Verification checklist** below.
6. Update `TRACKER.md` — check off the relevant task and add any newly
   discovered tasks to the appropriate phase or backlog.
7. Open a PR against `main` (PR template enforced). All CI checks must pass.
8. A maintainer reviews; `main` is protected — no direct pushes, no force-push.

## Verification checklist

Run all applicable checks before opening a PR. The CI pipeline mirrors
these gates (see `.github/workflows/ci.yml`).

### Rust (`constitution/`)

```powershell
cd constitution
& "C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe" build --release
& "C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe" test          # 17/17 must pass
& "C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe" fmt --check   # must be clean
& "C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe" clippy --all-targets -- -D warnings
& "C:\Users\OluwatobaOgunsakin\.cargo\bin\cargo.exe" build          # debug build for constitution_cli
```

**No `unsafe` blocks** in `constitution/` — CI enforces this via grep. Kani
proofs (`#[cfg(kani)]`) are verified in CI on Linux: `cargo kani`.

### Python (all six packages)

```powershell
# Compile-check every module
python -m compileall -q cortex adapters evolution mesh compliance simulation doomsday

# Lint
ruff check cortex adapters evolution mesh compliance simulation doomsday --ignore E501

# Full test suite (188 passed, 2 skipped as of 2026-09-14)
python -m pytest

# Chronos 1000-year stress gate (takes ~1-2 min)
python simulation/tests/integration_chronos.py 1000

# Live E2E pipeline (Cortex → Constitution)
python run_pipeline.py
```

**Note:** The `conftest.py` at repo root injects all six package homes onto
`sys.path`. If running Python outside pytest, set `PYTHONPATH` accordingly.

### Gateway (`gateway/`)

```powershell
cd gateway
npm ci
npm run build              # nest build / tsc
npm run test:unit          # 18 Jest unit tests
npm run test:e2e           # 4 e2e tests (gateway → constitution_cli → Constitution)
```

### What CI runs

| Job | Command | Gate |
|-----|---------|------|
| `rust` | build, fmt, clippy, test, unsafe-grep | Hard gate |
| `python` | compileall, ruff, pytest | Hard gate |
| `chronos-integration` | build constitutiond, Chronos 250-yr, live pipeline | Hard gate |
| `kani-verify` | `cargo kani` (Linux only) | Advisory (`continue-on-error: true`) |
| `gateway` | npm ci, build, unit, e2e | Hard gate |
| `security` | gitleaks, cargo-audit, pip-audit | Hard gate |

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
- [ ] `python -m compileall` passes for all six packages
- [ ] `python -m pytest` — all tests pass (188 passed, 2 skipped)
- [ ] `cargo fmt --check` clean; `cargo clippy --all-targets` clean (Rust)
- [ ] `ruff check` clean (Python)
- [ ] `TRACKER.md` updated — relevant task checked off, new tasks added
- [ ] No secrets, credentials, or private keys introduced
- [ ] Relevant docs updated (`README.md`, `docs/`, `AGENTS.md` sync points)

## Security

See `SECURITY.md`. Never open a public issue for a vulnerability; report via
Private Security Advisory.

## Code of conduct

Professional, constructive behavior is expected in issues, PRs, and internal
channels. Harassment, doxxing, or intimidation is not tolerated. Violations
can be reported through the same private channel as security issues.