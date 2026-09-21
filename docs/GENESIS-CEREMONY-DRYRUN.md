# Genesis Ceremony Dry-Run — Testnet Procedure (Phase 15.3)

> **Genesis-aligned:** this document specifies the *mechanism* for rehearsing
> the Genesis Ceremony on a testnet before executing on mainnet. It is a
> **dry-run procedure**, not trading strategy.
> Classification: **G6** (governance & zero-human operational control).
> Depends on: 15.1 (ceremony procedure), 15.2 (time-locked contract).

---

## 1. Purpose

The Genesis Ceremony is a **one-time, point-of-no-return** event. Before it is
executed on mainnet, the entire procedure — from air-gap key generation to
on-chain anchoring — must be rehearsed end-to-end on a testnet.

This dry-run validates:

1. **Tooling works** — `constitution_cli --genesis-init` / `--witness-sign`
   produce valid CRYSTALS-Dilithium3 key pairs and Ed25519 witness signatures.
2. **The on-chain time-lock contract** accepts the Genesis keyset, verifies the
   quorum, enforces the delay, and rejects insufficient signatures.
3. **The Rust kernel** correctly reads the embedded (testnet) public keys and
   enforces the quorum threshold during `authorize_signing`.
4. **The full verification gate** (Kani + Chronos 1000-year + full test suite)
   passes on the patched `secure_keys.rs`.
5. **No step is skipped** — the journal from the dry-run is cross-checked
   against `docs/GENESIS-CEREMONY.md` Step 0–7.

**Outcome of a successful dry-run:** The procedure is confirmed viable. The
mainnet ceremony uses the **same tooling, same air-gap process, same
contracts** — only the key material and the chain change.

---

## 2. Environment

| Component | Testnet | Mainnet target |
|-----------|---------|----------------|
| EVM chain | Sepolia (`chainId 11155111`) | To be chosen at mainnet ceremony |
| Gas token | Sepolia ETH (faucet) | Real ETH |
| Contract address (test) | Deployed by dry-run | Deployed at mainnet ceremony |
| Keyset | 5-of-9 test PQC keys | 5-of-9 production PQC keys |
| Air-gap | N/A (dry-run uses test keys) | N+1 air-gap machines, physical venue |

> **Note:** The dry-run does **not** use real air-gap machines for the
> *key generation* step — that would consume a ceremony-grade air-gap.
> Instead, the dry-run uses a **simulated air-gap**: keys are generated in a
> `--dry-run` mode of `constitution_cli` that produces the same format and
> structure but is clearly labelled `DRY-RUN-KEY`. The *mechanism* (witness
> attestation, aggregation, embedding, on-chain anchoring) is identical.

---

## 3. Dry-run procedure

### D0 — Pre-dry-run check (T−1 day)

1. **Branch:** `git checkout -b genesis-dryrun` from `main`.
2. **Tag:** `git tag genesis-ceremony-dryrun-input`.
3. **CI gate:** Run the full CI pipeline
   (`actions/workflows/ci.yml`) on this tag. All 5 jobs must be green:
   - Rust lint+test
   - Python lint+test
   - Integration test (Chronos × Cortex × Constitution)
   - Kani formal verification
   - Security scan
4. **Chronos gate:** `python simulation/tests/integration_chronos.py 1000`
   must report `passed=true`.

### D1 — Simulated key generation & witnessing (T+0h)

1. Using `constitution_cli --genesis-init --dry-run` on a development
   machine (not air-gap, since these are dummy keys):
   ```bash
   for i in $(seq 1 9); do
       constitution_cli --genesis-init --dry-run \
         --output-dir ./dryrun_keys/T$i
   done
   ```
2. Each `T_i`'s witness (a team member playing the role) runs:
   ```bash
   constitution_cli --witness-sign ./dryrun_keys/T$i/public_T$i.json \
     --witness-key ./dryrun_keys/witness_W$i.key
   ```
   This proves the **witness flow** works end-to-end.
3. **Journal:** Record all `DRY-RUN-KEY` identifiers, witness signatures,
   and timestamps in `docs/GENESIS-CEREMONY-DRYRUN.md#dryrun-journal`.

### D2 — Aggregation & on-chain anchoring (T+2h)

1. Run the aggregate tool:
   ```bash
   constitution_cli --aggregate-keys ./dryrun_keys/ \
     --output ./dryrun_genesis_keyset.json
   ```
2. **Deploy the contracts** (scripts in `scripts/deploy-governance.ts`):
   ```bash
   npx hardhat run scripts/deploy-governance.ts --network sepolia
   ```
   Output: `ParameterStore`, `TimelockController`, `GovernanceRouter`
   addresses. Record them in the journal.
3. **Anchor the bundle hash:**
   ```bash
   npx hardhat run scripts/anchor-genesis.ts --network sepolia \
     --keyset-hash $(sha256sum dryrun_genesis_keyset.json | cut -d' ' -f1)
   ```
   This calls `GovernanceRouter.attestGenesisKeyset(bytes32)`.
   Verify the `GenesisCeremonyCompleted` event fires.

### D3 — Parameter change end-to-end (T+3h)

1. **Propose** a dummy parameter change:
   ```bash
   npx hardhat run scripts/propose-parameter.ts --network sepolia \
     --param max_leverage --value 300 \
     --signatures ./dryrun_keys/T{1,2,3,4,5}/recovery_sig.ed25519
   ```
   (Use 5 trustee signatures to hit the 5-of-9 quorum.)
2. **Schedule** it — the TimelockController emits
   `CallScheduled(operationId)`. Verify `delay = 7 days`.
3. **Cancel test** — with 3-of-9 signatures, call `cancelParameterChange`.
   Verify the operation is cancelled.
4. **Re-propose + execute test:**
   - Schedule the parameter change again.
   - **Do NOT cancel.** Wait for the delay (simulated — use Hardhat mainnet
     forking or just verify the delay logic by checking timestamps).
   - Call `executeParameterChange`. Verify
     `ParameterUpdated(max_leverage, 300)` fires.
5. Verify the **kernel reads the new value**: restart `constitutiond` with
   `CONSTITUTION_MAX_LEVERAGE=3.0` and confirm
   `GetStatus` reports the updated threshold.

### D4 — Failure-mode tests (T+4h)

| Test | Input | Expected result |
|------|-------|-----------------|
| D4.1 | Propose with 4-of-9 signatures | `revert GovernanceInsufficientSignatures` |
| D4.2 | Execute before delay elapsed | `revert OperationIsNotReady()` |
| D4.3 | Cancel after delay elapsed | `revert OperationIsNotPending()` |
| D4.4 | Anchor with wrong keyset hash | `revert InvalidGenesisKeyset()` |
| D4.5 | Trustee key not in genesis set signs | `revert UnknownSigner()` |

### D5 — Rust kernel patching & verification (T+5h)

1. Patch `constitution/src/secure_keys.rs`:
   - Replace the placeholder PQC key with the 9 dry-run test public keys.
   - Set `GENESIS_CEREMONY_ROOT_HASH` to the dry-run bundle hash.
2. **Verification gate:**
   | Gate | Command | Expected |
   |------|---------|----------|
   | G-Kani | `cargo kani` | All proofs pass (no panic, no overflow) |
   | G-Test | `cargo test` | 17/17 pass |
   | G-Chronos | `python simulation/tests/integration_chronos.py 1000` | `passed=true` |
   | G-Python | `pytest` | 181 passed, 2 skipped |
   | G-Gateway | `npm run test:unit && npm run test:e2e` from `gateway/` | 18 unit + 4 e2e pass |
   | G-Format | `cargo fmt --check` | Clean |
   | G-Lint | `cargo clippy --all-targets` | No warnings |

### D6 — Rollback & journal lock (T+6h)

1. **Discard** the dry-run patch (do NOT merge it to `main`). The
   `secure_keys.rs` on `main` keeps its placeholder until the real ceremony.
2. **Lock the journal:** Commit all dry-run artifacts to
   `docs/GENESIS-CEREMONY-DRYRUN.md` (this file). The journal is append-only.
3. **Tag:** `git tag genesis-dryrun-complete`.
4. **Close the branch** — `genesis-dryrun` is archived (not deleted, for
   audit history).

---

## 4. Dry-Run Journal

> **Status:** Not yet executed. Populated at D1–D6.

| Step | Timestamp (UTC) | Operator | Artifact | Result |
|------|-----------------|----------|----------|--------|
| *(filled during dry-run)* | *(filled)* | *(filled)* | *(filled)* | *(filled)* |

---

## 5. What this validates

| Real ceremony step | Dry-run equivalent | Validated? |
|---|---|---|
| Air-gap key generation (Step 1) | `--dry-run` simulated generation (D1) | Machinery ✓; air-gap physics ✗ (out of scope) |
| Witness attestation (Step 2) | Witness signing tool (D1) | ✓ |
| Aggregation & embedding (Step 4) | Aggregate tool + `secure_keys.rs` patch (D5) | ✓ |
| On-chain anchoring (Step 5) | Sepolia deploy + `attestGenesisKeyset` (D2) | ✓ |
| Verification gate (Step 6) | Full G1–G7 gate on patched kernel (D5) | ✓ |
| Failure modes | D4 tests | ✓ |

**Out of scope for the dry-run:** the physical security of the air-gap
environment, the destruction of machines, and the use of real PQC key
material. These are ceremony-step concerns documented in 15.1 §3.1; the
dry-run confirms the *process* that will be followed.

---

## 6. Mainnet go/no-go

The mainnet Genesis Ceremony may proceed **only if**:

- [ ] D1–D6 all pass with no unresolved failures.
- [ ] All D4.1–D4.4 failure-mode tests behave as expected.
- [ ] The verification gate (G-Kani, G-Test, G-Chronos, G-Python, G-Gateway)
  all pass on the dry-run patched kernel.
- [ ] The on-chain anchoring transaction is confirmed on Sepolia.
- [ ] The dry-run journal (this file) is complete and signed by the Notary.

**A failed dry-run is a no-go.** Fix the tooling, re-run from D0.
