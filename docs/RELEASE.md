# Release Process — Centaur-Apex Core

**Note:** Releases are a scaffold for the Genesis bootstrap phase. Once the
system becomes autonomous, the Evolution Sub-Agent participates in release
governance (it may propose transpiled binaries; the current versioning & gate
policy still applies to hand-authored changes).

---

## Versioning

Semantic — `MAJOR.MINOR.PATCH`:
- **MAJOR:** incompatible governance/invariant changes (rare; requires
  Kani + multi-sig).
- **MINOR:** additive, backward-compatible Genesis features.
- **PATCH:** bug fixes, docs, tooling, verifiable refactors.

There is no pre-1.0 convention change; we stay `0.x.y` until mainnet locking.

### Immortal versioning

Because the system must run for a century, `MAJOR` releases are expected to be
extremely rare:
- A MAJOR change requires a **formal verification record** (Kani proof) AND
  a **multi-sig governance authorization** per `docs/GOVERNANCE.md`.
- The invariant set I1–I8 is considered **immutable** unless the governance
  layer explicitly votes to change it (recorded on-chain).

---

## Release gates (Definition of Done — see also `AGENTS.md` §8)

- [ ] `cargo build --release` passes
- [ ] `cargo test` passes (≥ 6/6)
- [ ] `cargo fmt --check` passes
- [ ] All Python modules pass `python -m py_compile`
- [ ] `python simulation/tests/integration_chronos.py` passes (Chronos gate)
- [ ] `run_pipeline.py` succeeds end-to-end
- [ ] No secrets / keys in the tree
- [ ] CHANGELOG updated, version bumped per semantic rules
- [ ] Governance-reviewed (for anything touching invariants)

---

## Release procedure (for a maintainer)

### 1. Prepare

```powershell
# Ensure branch is main, clean, and up-to-date
git checkout main
git pull origin main

# Run the full gate suite (blocking any failure)
cargo build --release --manifest-path constitution/Cargo.toml
cargo test --manifest-path constitution/Cargo.toml
python -m compileall -q cortex adapters simulation mesh compliance evolution
python simulation/tests/integration_chronos.py
python run_pipeline.py
```

### 2. Bump version + CHANGELOG

Update the version in the CHANGELOG's latest release block and any package
manifests. **Do not** edit `Cargo.lock` by hand.

### 3. Commit + tag

```powershell
git add -A
git commit -m "release(v0.x.y): ...
git tag v0.x.y
git push origin main --tags
```

---

## Rollback policy

Rollback of a **hand-authored** change is a normal git operation (revert the
commit). Rollback of a **governance-changed invariant** is impossible via
normal release — that is the design. If the next `MAJOR` release contradicts
the current one, the old state is deprecated, but never force-reverted.

---

## Automation roadmap

- CI pipeline that runs all gates automatically on push/PR.
- Release binaries built via CI (checksums + provenance).
- Signed release tags: tag signatures keyed to the PQC key material, once
  the Genesis Ceremony is complete.