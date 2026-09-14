# Architecture Decision Records (ADRs)

This file records the significant architectural decisions made during the
Genesis bootstrap, providing "why not the alternative" context across decades.

---

## ADR-001: TCP length-prefixed framing for Constitution IPC

**Date:** 2026-09-14

**Context:** The Rust Constitution risk core needs a stable, low-latency
boundary with Python and TypeScript callers. Options: HTTP/REST, gRPC,
Unix domain sockets, shared memory, raw TCP framing.

**Decision:** Raw TCP with 4-byte big-endian length-prefix framing (`>I` in
Python struct, `[u8; 4]` in Rust), versioned JSON envelope, MAX_FRAME_BYTES
16KB.

**Rationale:**
- gRPC introduces a protobuf toolchain dependency, which is heavy for a
  100-year system where Rust toolchains will be transpiled by the Evolution
  Sub-Agent.
- HTTP has overhead not needed for a binary daemon.
- TCP framing is trivial, fully under our control, and easily replaced.
- JSON envelopes allow human debugging during the bootstrap phase; can be
  upgraded to a binary envelope later without changing the framing layer.

**Status:** Accepted.

---

## ADR-002: Per-connection Constitution kernel spawn

**Date:** 2026-09-14

**Context:** The initial `constitutiond` daemon creates a new
`ConstitutionService` per TCP connection, meaning cross-connection state is
not persisted.

**Decision:** Accept this as a scaffold limitation. The
`constitution_client.py` IPC client manages a persistent session (opening
one TCP connection and reusing it for the full evaluation lifecycle).

**Rationale:**
- Stateless-per-connection keeps the initial implementation simple and
  prevents accidental state bleed across calls.
- In a production deployment, the kernel should evolve to an event-driven
  long-lived actor (tokio/tarpc or actor-framework) — but this is
  engineering debt to be retired by the Evolution Sub-Agent, not something
  we hand-optimize now.

**Status:** Accepted as temporary (documented in `docs/PRD.md` §7).

---

## ADR-003: Python 3.11+ with Pydantic v2 for Cortex schemas

**Date:** 2026-09-14

**Decision:** Use Python 3.11+ with Pydantic v2 for all Cortex data models.

**Rationale:**
- Pydantic v2 provides runtime JSON schema validation at the IPC boundary,
  catching malformed proposals before they reach the Constitution.
- Python 3.11+ gives `tomllib`, structured sub-exceptions, and performance
  improvements important for real-time proposal evaluation.
- Constrained to specific packages (`pydantic`, `numpy`, `pandas`, `requests`);
  no ML frameworks allowed in the Genesis codebase (the Cortex's
  meta-learning framework will choose frameworks at runtime).

**Status:** Accepted.

---

## ADR-004: HMAC-SHA3 placeholder for PQC layer

**Date:** 2026-09-14

**Decision:** `mesh/pqc_wrapper.py` uses HMAC-SHA3 as a placeholder, with
real lattice crypto (`liboqs` / CRYSTALS-Dilithium) flagged for replacement
before mainnet.

**Rationale:**
- Real PQC libraries have C/FFI bindings that introduce platform-specific
  build fragility — unsuitable for a scaffold that must build across
  developers and CI environments during bootstrap.
- The *contract* (sign-then-verify API shape) is what matters now;
  swapping the underlying algorithm is a localized change, which is the
  point of the protocol abstraction layer.

**Status:** Accepted, tracked as known debt in PRD §7.

---

## ADR-005: Proprietary license

**Date:** 2026-09-14

**Decision:** All rights reserved, proprietary.

**Rationale:**
- The Genesis Codebase is not a library; it is the system's DNA.
- Open-sourcing it would allow competitors to adopt the architecture without
  contributing back, and would make it difficult to enforce the governance
  model (AGENTS.md) via cryptographic multi-sig.
- The system-generated artifacts (strategies, venue adapters) belong to the
  system; open licensing them is a future governance decision, not a
  bootstrap-time one.

**Status:** Accepted.

---

## ADR-006: Schema-driven IPC envelope over ad-hoc dicts

**Date:** 2026-09-14

**Decision:** All IPC communication uses typed `IpcEnvelope` (Rust) and
`IpcEnvelope`/`TradeProposal` (Python, Pydantic) structures with a
versioned `protocol_version` field.

**Rationale:**
- Prevents silently-incorrect payloads (an untyped dict can silently
  produce a zero-notional proposal; Pydantic + Rust serde catch this).
- Versioning allows backward-compatible evolution of opcodes and payloads
  without breaking the framing layer — critical for a 100-year system.

**Status:** Accepted.