# Security Policy

Centaur-Apex Core is a proprietary trading system that handles real capital and
private cryptographic material. Security findings are treated with the highest
priority.

## Supported versions

| Branch | Support level |
|--------|---------------|
| `main` | Supported — always-current with the Genesis Codebase |
| Release tags (`vX.Y.Z`) | Supported for the current release line |

Only the current release line receives security fixes. Because the system is
designed to transpile and replace its own code (`evolution/patches/`), no
legacy branch is maintained beyond the active one.

## Reporting a vulnerability

**Do NOT open a public issue or PR for a security finding.**

Report privately to:

- **GitHub Private Security Advisory:** navigate to the repo's
  *Security → Advisories → New draft security advisory*. The repository owner
  is automatically notified.
- **Owners list:** the Git user (and commit-author) identity recorded in
  `AUTHORS.md`.

Include:
1. Severity estimate and the component affected (`constitution/`, `gateway/`,
   `adapters/`, `mesh/`, etc.).
2. Steps to reproduce, or the failing input if it is data-driven.
3. Which 100-year invariant (I1–I8) is potentially weakened, if any.
4. Whether the finding exposes keys, can route or sign an order (I5), or can
   force premature liquidation.

## Response expectations

| Severity | Initial acknowledgment | Fix target |
|----------|------------------------|------------|
| Critical (compromise of keys, order execution, or I1–I8 bypass) | ≤ 24 h | ≤ 7 days |
| High | ≤ 72 h | ≤ 30 days |
| Medium / Low | ≤ 1 week | Next release |

We follow coordinated disclosure: we ask reporters for a 45-day window before
publication, extendable by mutual agreement.

## Scope / threat model

The threat model is: **an attacker who has network or local access to one or
more Centaur-Apex components, or who supplies market data or trade proposals
to the system, but does NOT possess the genesis signing keys.**

In scope:
- Bypass or weakening of invariants I1–I8 (drawdown, leverage, concentration,
  numerical validity, execution independence).
- Risks to key material in `constitution/src/secure_keys.rs` and its PQC
  wrappers in `mesh/`.
- Memory-safety flaws in `constitution/` (Rust `unsafe`, unchecked arithmetic).
- IPC boundary abuse: `constitution_cli` / `constitutiond` framing,
  authentication-less paths, oversized frames, malformed envelopes.
- Order-execution independence (I5): anything allowing code outside
  `constitution/` to route, sign, or execute an order.

Out of scope (by design, documented in docs/RISK-DISCLOSURE.md):
- Disagreement of probabilistic market models — the Cortex is allowed to be
  wrong; that is a market risk, not a security bug.
- Deliberate deactivation of the daemon by a party holding seed/HSM access.
- Endpoint availability of public market-data feeds.

## Security expectations for contributors

- **Zero secrets in the repo.** Keys live in HSM / PQC vaults, never in code.
- No `unsafe` blocks in `constitution/` unless accompanied by a Kani proof.
- All new executable logic passes the Chromos sandboxing gate.
- Branch protection (PR-only merges, signed commits) applies to `main`;
  see `.github/`.

## Disclosure to operators

Security advisories intended to change risk parameter defaults are routed
through the multi-sig governance layer described in `docs/GOVERNANCE.md`,
because weakening an invariant is a governance change, not a code fix.