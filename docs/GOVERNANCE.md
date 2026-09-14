# Governance — Centaur-Apex Core

**Status:** Genesis bootstrap; multi-sig infrastructure defined, ceremony not
yet executed.

---

## The constitutional principle

Humans are **permanently locked out of operational control** of the trading
system. There is no panic button, no "admin override," no emergency-stop
webhook. The system must be allowed to follow its century-long strategy to
its mathematical conclusion.

This is not a product feature — it is the system's survival assumption.
If humans can panic-stop the system, the system will be panic-stopped.

The only permissible changes to governance parameters are made through the
**cryptographic multi-sig layer** documented below.

---

## Who may change the rules?

| Action | Who may initiate | What is required |
|--------|-----------------|------------------|
| Modify invariant thresholds (I1–I3) | Genesis multi-sig only | Formal verification (Kani proof) + multi-sig vote |
| Modify invariant *existence* (add/remove I1–I8) | Genesis multi-sig only | Formal verification + multi-sig + on-chain record |
| Modify state machine transitions | Genesis multi-sig only | Formal verification + multi-sig vote |
| Swap the PQC algorithm | Evolution Sub-Agent (runtime) + governance (parameter change) | The Evolution Sub-Agent generates a replacement; the governance layer authorizes the swap via multi-sig |
| Add a new venue adapter | Evolution Sub-Agent (autonomous) | The Discovery Agent + Sub-Agent may generate and hot-swap adapters without governance (this is S1: the system's job) |
| Change a risk parameter *value* (e.g., raise leverage cap from 2.5 to 3.0) | Genesis multi-sig only | Governance vote + on-chain record; an invariant *threshold* is a governance parameter, not a code change |
| Emergency: freeze the system | No human may do this | The system enters `EmergencyHalt` automatically (I6); humans cannot override it |
| Emergency: recover from `EmergencyHalt` | Genesis multi-sig only | Cryptographic proof of legitimacy → `AttemptRecovery` RPC |

---

## The Genesis multi-sig

The system's governance is controlled by a set of **cryptographic keys** held
by a quorum of designated trustees (initially: the founding engineers).

- A governance change requires a threshold quorum of signatures (e.g.,
  3-of-5).
- Keys are held in HSMs or PQC wallets — never in software, never in the
  repository.
- The public keys are hardcoded into `constitution/src/secure_keys.rs`
  (PQC placeholder: the real keys are added during the **Genesis Ceremony**).

This is a skeleton. The full ceremony is described below.

---

## The Genesis Ceremony

**Status: NOT YET EXECUTED.**

The Genesis Ceremony is the one-time event where:

1. The founding trustees generate their PQC key pairs in an air-gapped
   environment.
2. Each trustee's public key is signed by a ceremony witness (a human who
   is not a trustee).
3. The signed public keys are embedded in `secure_keys.rs` via a
   governance-signed patch.
4. The patch is verified (Kani + Chronos 1000-year gate) and merged.
5. The system's autonomous operation begins.

Once the ceremony completes, **no human may ever update the key set without
the current quorum's approval.** This is the point of no return.

---

## Zero-human override — deeper

The law (AGENTS.md I7) means:

- There is no REST endpoint to force an emergency liquidation.
- There is no admin CLI that bypasses invariants I1–I3.
- There is no social-engineering backdoor: "we lost the key, so we can
  manually liquidate."
- The system will continue trading (or stay halted) until it reaches a
  mathematical conclusion, even if that takes decades.

If the quorum of keys is lost entirely, the system enters a permanent halt
state. This is considered an acceptable outcome over allowing human override.

---

## The Compliance DAO

`compliance/governance/multisig_dao.py` encodes the on-chain governance
logic for:

- Parameter changes (leverage cap, concentration limit, drawdown threshold).
- Trustee rotation (adding/removing signers).
- Jurisdictional rule updates.

All DAO actions require the multi-sig and are recorded on-chain for auditability.

---

## Succession protocol

If a trustee dies, loses their key, or becomes unreachable:

1. The remaining quorum meets (via the governance channel in SUPPORT.md).
2. They vote to revoke the lost key and add a replacement trustee's key.
3. The new key set is embedded via a governance-signed patch (same process
   as the Genesis Ceremony).

If the quorum drops below the threshold, governance changes are impossible.
The system stays in its current configuration forever. This is a deliberate
design trade-off in favor of zero-human override.

---

## Emergency governance (post-ceremony)

All of the above is enforced by code. There is no "exception clause."
The only way to change the rules is to sign a governance change with the
current quorum, which is cryptographically enforced by the Constitution.