# Genesis Ceremony — Multi-Sig Key Ceremony Procedure (Phase 15.1)

> **Genesis-aligned:** this document specifies the *mechanism* for establishing
> the cryptographic governance quorum that locks human operational control out
> of the trading system. It is a *procedure*, not strategy, alpha, or venue logic.
> Classification: **G6** (governance & zero-human operational control).

---

## 1. Purpose

The Genesis Ceremony is the **one-time, physical, air-gapped event** that
creates the trust root for governance. After this ceremony:

- A set of **post-quantum (PQC) public keys** are embedded into
  `constitution/src/secure_keys.rs`.
- Each public key is **witness-signed** (attested by a human witness who is NOT
  a trustee) to prove it was generated on-site, untampered.
- The Constitution's `KeyVaultAccess` authorizes signing **only** when a
  threshold quorum of these keys present valid signatures.
- **No human may ever modify the key set without the current quorum's approval.**
  This is the point of no return.

The system's autonomous operation begins at ceremony completion. This is the
last moment humans have any influence over the system's cryptographic boundary.

---

## 2. Participants

| Role | Count | Responsibility |
|------|-------|----------------|
| **Trustee** | N | Generates a PQC key pair; holds the private half for life. Present public key for witnessing. |
| **Witness** | N | Independent human (NOT a trustee) who witnesses key generation and signs (attests) the public key. |
| **Notary (ceremony coordinator)** | 1 | Runs the procedure clock, records the journal, ensures no step is skipped. Does NOT hold any key material. |
| **Observer (optional)** | 0–M | Auditors / journalists who observe but do not participate. |

**Default N = 5** (5-of-9 quorum: any 5 of 9 trustees may authorize a governance
change). This matches the `multisig_dao.py` default `threshold_signatures_required`.

---

## 3. Pre-ceremony prerequisites

### 3.1 Physical security

- **Air-gap machines:** N brand-new laptops, factory-reset, never connected to
  the internet or any internal network. Each machine boots from a
  **verified** Linux live USB.
- **Media:** N write-once USB sticks (or QR paper backups) for the final key
  export. No rewritable media for key material.
- **Cameras off / RF shielding:** Machines must not have cameras, Wi-Fi, or
  Bluetooth active. BIOS disabled wireless devices.
- **Physical venue:** A locked room, no recording devices, checked at entry.
- **Live-USB verification:** SHA-256 of the live USB image is verified against
  a publisher signature before boot (OpenPGP web-of-trust or the
  ceremony coordinator's pre-published checksum).

### 3.2 Tooling

- `constitution_cli --genesis-init` — a one-shot subcommand that:
  1. Generates a CRYSTALS-Dilithium3 key pair using `liboqs`.
  2. Prints a **witness statement** (JSON) containing the public key, a
     random session nonce, and the machine's hardware fingerprint
     (`cpu_id`, `bios_version`, disk serial) captured on-airgapped-boot.
  3. Exits — the private key is written only to the write-once medium.
- **Witness signing tool:** A separate air-gap machine runs
  `constitution_cli --witness-sign <public_key.json>` which loads the
  witness's *own* Ed25519 witness key (generated separately, not part of
  the governance quorum) over a QR code and produces a witness signature.
- **Aggregate tool:** Runs on an air-gap machine; combines all trustee public
  keys + witness signatures into a single JSON bundle.

### 3.3 Governance parameter freeze

- No code changes are accepted to `constitution/` 48 hours before the ceremony.
- The `main` branch is tagged `genesis-ceremony-input`.
- All Kani proofs and the 1000-year Chronos gate must be **green** on this tag.

---

## 4. Ceremony procedure (step by step)

### Step 0 — Kickoff (00:00)

1. Notary verifies all machines boot from the verified live USB.
2. Each trustee claims their assigned machine. No two trustees share a machine.
3. Each witness claims their own machine (separate set).
4. **Journal begins** — Notary records: participant roster, machine fingerprints,
   start time, UTC. All video (if any) is time-stamped.

### Step 1 — Key generation (00:10)

For each trustee `T_i` in parallel (witnesses watch but do not assist):

1. `T_i` runs `constitution_cli --genesis-init` on their air-gap machine.
2. The machine prints a **witness statement** to stdout (human-readable) and
   writes `public_T_i.json` + `witness_statement_T_i.json` to a write-once USB.
3. The private key (`private_T_i.key`) is written to a **second** write-once
   USB, which `T_i` keeps sealed.
4. `T_i` shows their screen to their assigned witness `W_i` so `W_i` can
   visually confirm: (a) the public key appears, (b) the hardware fingerprint
   matches the machine, (c) the timestamp is correct.

**Invariant:** If any machine was ever network-connected before or during the
ceremony, its key is **discarded** and regenerated. The witness attests to this
in their signature.

### Step 2 — Witness attestation (00:40)

For each trustee `T_i`:

1. `W_i` loads their own witness key (pre-generated on a separate air-gap
   machine, stored on QR paper).
2. `W_i` runs `constitution_cli --witness-sign public_T_i.json` on their machine.
3. The tool prints `witness_sig_T_i.json` (signs the public key + session nonce
   + hardware fingerprint).
4. `W_i` hands the witness signature USB back to `T_i`.
5. `W_i` signs the **ceremony journal entry** for `T_i` — a timestamped
   statement: "I witnessed `T_i` generate key `pubkey_T_i` on machine
   `hardware_fingerprint` at `timestamp`, and confirm it was air-gapped."

### Step 3 — Key rotation commitment (01:00)

Each trustee commits to a **key rotation schedule** — a pre-agreed rule for
when and how they will hand over or destroy their key in the event of
death, incapacitation, or long-term unavailability:

1. Each `T_i` writes their rotation commitment (a hash) into the aggregate
   bundle before the ceremony ends.
2. The full commitments are recorded on-chain at the ceremony's end
   (see Step 5).

### Step 4 — Aggregation & embedding (01:20)

1. The Notary runs the **aggregate tool** on a dedicated air-gap machine:
   - Collects all `public_T_i.json`, `witness_sig_T_i.json`, journal entries.
   - Produces `genesis_keyset.json` — a single file containing all N public
     keys, all witness attestations, all journal entries, and rotation
     commitments.
2. The Notary **hashes** the final bundle: `sha256(genesis_keyset.json)`.
3. A **patch** is generated to `constitution/src/secure_keys.rs`:
   - The N public keys are embedded as `const` byte arrays.
   - The witness attestations are embedded as `const` for auditability.
   - The bundle hash is embedded as `GENESIS_CEREMONY_ROOT_HASH`.
4. The patch is **reviewed** by all trustees and witnesses (air-gap machine,
   no internet) — they verify the public keys match what they generated.
5. The patch is signed (individually) by each trustee using their Ed25519
   signer key and committed to the repo as a `.signed.patch` file.

**No single person holds all keys.** The patching machine never sees any private
key material — only public keys and signatures.

### Step 5 — On-chain anchoring (02:00)

1. The `genesis_keyset.json` bundle hash and the `GENESIS_CEREMONY_ROOT_HASH`
   are submitted to the **time-locked governance contract** (see
   `docs/TIMELOCK-GOVERNANCE.md`) on the chosen EVM testnet.
2. The contract emits a `GenesisCeremonyCompleted` event recording:
   - The bundle hash.
   - The quorum configuration (e.g., 5-of-9).
   - The timestamp.
   - The on-chain transaction hash.
3. The transaction hash is recorded in the **ceremony journal**.

### Step 6 — Verification gate (02:10)

The ceremony is **not complete** until all verification gates pass:

| Gate | Check | Tool |
|------|-------|------|
| G1 | All witness statements valid | `constitution_cli --verify-witnesses` |
| G2 | `secure_keys.rs` patch matches genesis bundle hash | `sha256` + `grep GENESIS_CEREMONY_ROOT_HASH` |
| G3 | Kani proofs green on the patched `constitution/` | `cargo kani` |
| G4 | `cargo test` (17/17) pass on the patched crate | `cargo test` |
| G5 | Chronos 1000-year stress test passes | `python simulation/tests/integration_chronos.py 1000` |
| G6 | Full Python + Rust + Gateway test suite green | `cargo test` + `pytest` + `npm test` |
| G7 | On-chain anchoring transaction confirmed | `curl` to RPC |

### Step 7 — Seal (03:00)

1. Notary writes the final `GENESIS_CEREMONY_ROOT_HASH` to
   `docs/GENESIS-CEREMONY.md#sealed-hash`.
2. The `main` branch is tagged `genesis-ceremony-complete`.
3. **The sealed keyset is now immutable.** Governance changes require the
   quorum of these keys + the time-lock contract (see `TIMELOCK-GOVERNANCE.md`).
4. Trustees destroy the air-gap machines (physical destruction of storage).

---

## 5. Key management after the ceremony

| Key type | Holder | Lifetime | Rotation |
|----------|--------|----------|----------|
| **Governance PQC key** (Dilithium3) | Trustees (HSM / PQC wallet) | Until revoked by quorum | See GOVERNANCE.md §Succession |
| **Witness key** (Ed25519) | Witnesses | Per-ceremony | Regenerated each ceremony |
| **Bundle root hash** | On-chain (contract) + `secure_keys.rs` | Permanent | Only via quorum + time-lock |

- Trustee private keys **never** touch a networked machine after generation.
- Trustees are expected to store their key in an **HSM** or a **PQC wallet**
  with physical custody. The Constitution reads only the **public** part.
- The `secure_keys.rs` `authorize_signing` function only ever checks
  whether a presented signature matches one of the N embedded public keys
  and whether `proof_claim >= self.signing_threshold`.

---

## 6. What happens if the ceremony fails

- If a key is compromised or a step is skipped, the bundle is invalidated.
- Trustees regenerate from Step 1; the journal entry for the compromised key
  records the failure with a new session nonce.
- The bundle hash changes, so the on-chain anchoring must be re-submitted.
- **No partial ceremony is accepted.** The system does not activate until G1–G7 pass.

---

## 7. Data-driven / system-owned extensions

Per AGENTS.md §3 (G6: governance foundations):

- The **quorum N-of-M** is a data-driven parameter stored in the
  `genesis_keyset.json` bundle and the contracts. The Evolution Sub-Agent
  may propose a quorum change via the time-lock governance path — it cannot
  do so unilaterally.
- The **witness process** is the mechanism; the specific witness identities
  are data (rotated per ceremony, never hard-coded).
- New trustees are added via the same multi-sig + time-lock path — no code change.

**Genesis asks:** Does this change within 100 years? The quorum size might;
the trustee roster might; the specific keys might. None of those are hardcoded
in Genesis DNA — only the *mechanism* for establishing and changing them is.

---

## 8. Security notes

- **Never** generate governance keys on a networked machine. The ceremony's
  entire security model depends on the air-gap.
- The witness signature does **not** attest to the key's validity for trading —
  only to "this key was generated on this air-gap machine at this time."
  Governance validity comes from the quorum + time-lock, not from witnessing.
- If > floor(N/3) witnesses collude against a trustee, that trustee's key
  is still valid if the quorum (5 of 9) independently verifies it.
- The private key medium is sealed. If it is ever opened outside a formal
  governance procedure (e.g., recovery), the journal records it as a
  "key disclosure event" and the quorum must rotate the key.

---

## Sealed hash

> This field is populated at Step 6 of the ceremony. It is blank before
> the ceremony is executed.

```
GENESIS_CEREMONY_ROOT_HASH = ""
```
