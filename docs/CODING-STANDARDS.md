# Coding Standards — Centaur-Apex Core

Follow the law in `AGENTS.md` first. These are stylistic and structural standards
that make the Genesis Codebase durable, machine-auditable, and Kani-provable.

---

## Cross-cutting

- **No hardcoded secrets.** Zero keys, tokens, or credentials in source.
  Placeholders must be clearly marked `PQC-PLACEHOLDER` / `CI-ONLY`.
- **No untyped handoff.** Every artifact crossing a service boundary is a
  typed schema (Pydantic model in Python, `struct` + `serde` in Rust,
  `interface` in TypeScript).
- **Genesis vs. System.** Files that will be swapped out by the Evolution
  Sub-Agent carry a header comment: `# SYSTEM-OWNED STUB (Sx): <reason>`.
  Anything else is Genesis DNA and must be permanent, data-driven, and
  mechanism-shaped.
- **No comments unless they encode intent.** Prefer a 3-line block explaining
  *why* over 20 lines of inline commentary.
- **Failure is explicit.** Prefer `Result`/`raise`/`throw` over silent
  fallback, except where a fail-safe default (I6) demands the opposite.

---

## Rust (`constitution/`)

- Edition 2021, no `panic!` on the hot evaluation path.
- No `unsafe` blocks in `constitution/` without an accompanying Kani proof
  and a governance review record.
- Arithmetic: use checked/saturating ops where overflow could affect
  invariants; keep all computation Kani-provable.
- Public API: `pub struct` + `#[derive(Serialize, Deserialize, Debug)]`.
- Errors: define a local `Error` enum implementing `Display` + `std::error::Error`.
- Formatting: `cargo fmt --check` must pass.
- Unit tests live in the same module (`#[cfg(test)] mod tests`) or `tests/`;
  every invariant function has at least one test.
- Kani proofs: `#[cfg(kani)] #[kani::proof]` for `evaluate` and `handle_frame`
  no-panic guarantees.
- Binary entrypoints (`constitutiond`, `constitution_cli`) stay thin: parse
  → call library → serialize. Business logic lives in the lib crate.

## Python (`cortex/`, `adapters/`, `mesh/`, ...)

- Python 3.11+, Pydantic v2 for all schemas.
- Type hints on every public function signature (`-> None`, `-> dict[str, Any]`).
- Keep modules small and single-purpose. No god objects.
- Only banned dependency creep: Genesis modules depend on `pydantic`,
  `numpy`, `pandas`, `requests` — nothing else. ML frameworks are chosen by
  the Cortex at runtime, never baked into the Genesis layer.
- Import style: `from x import y` (absolute imports only). Sort imports
  (stdlib, third-party, local).
- Handle `MetaTrader5` import failure gracefully (`try/except ImportError`)
  since it is unavailable in CI.
- Constant buffers: use `MAX_*` names (e.g., `MAX_FRAME_BYTES`).
- Package data: schemas belong in `*schemas*.py` or `proposal_api.py`, never
  inline dictionaries.

## TypeScript (`gateway/`)

- Strict mode (`tsconfig`: `strict: true`), no `any` leaks.
- NestJS DI: services are `@Injectable()`, controllers thin.
- The Rust bridge (`rust-bridge.service.ts`) is the ONLY module allowed to
  touch the Constitution process; no other service may spawn it.

---

## Purpose-appropriate deferral

Standard: if a new file implements a *specific strategy, venue, tax regime,
or crypto algorithm* — i.e., something in S1–S7 — mark it as a system stub or
move the logic to a schema/config the system can populate. Do **not** build it
as a permanent, hand-maintained module.