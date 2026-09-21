# Time-Locked Governance Contract — Design (Phase 15.2)

> **Genesis-aligned:** this document specifies the *on-chain mechanism* that
> enforces the time-delayed, multi-sig-governed parameter-change path for the
> Centaur-Apex Constitution. It is a **contract design**, not trading strategy.
> Classification: **G6** (governance & zero-human operational control).
> Implements AGENTS.md I7 (zero-human override) at the enforcement layer.

---

## 1. Purpose

The Constitution's on-chain governance layer must:

1. **Require a threshold quorum** of the Genesis-Ceremony multi-sig keys for any
   parameter change.
2. **Enforce a time-lock** — a mandatory delay between proposal scheduling and
   execution, so the system (and its human observers) can audit, react, or
   initiate emergency procedures (e.g., Doomsday escalation).
3. **Record every action on-chain** for immutable auditability.
4. **Never allow unilateral human control** — the contract itself is the gatekeeper.

This contract sits **above** `constitution/src/secure_keys.rs`. The Rust
kernel checks: "does this proposal's signature bundle pass the on-chain
governance quorum?" The answer comes from this contract.

---

## 2. Contract architecture

```
GovernanceConfig (immutable at deploy)
    |
      └── G1 = quorum threshold (e.g. 5-of-9)
      └── G2 = time-lock delay (e.g. 7 days)
      └── G3 = guardian addresses (trustee PQC public keys, as on-chain hashes)
      └── G4 = cancel threshold (e.g. 3-of-9 can cancel a scheduled proposal)

TimelockController (OpenZeppelin-style)
    |
      └── schedule(target, value, data, predecessor, salt, delay)
      └── cancel(target, value, data, predecessor)
      └── execute(target, value, data, predecessor, salt)
      └── isOperationPending / isOperationReady / isOperationDone

GovernanceRouter (custom thin layer)
    |
      └── proposeParameterChange(paramName, newValue, justification)
      └── voteWithSignatures(signatureBundle) — verifies off-chain PQC signatures
      └── scheduleParameterChange(paramName, newValue) → calls TimelockController
```

### Why a router + OZ Timelock?

- The **TimelockController** is a battle-tested, audited OpenZeppelin contract.
  We do not write the time-lock logic by hand — that is an invitation to bugs.
- The **GovernanceRouter** is the thin adapter that:
  - Accepts a `paramName` + `newValue` (e.g., `max_leverage = 3.0`).
  - Verifies the off-chain PQC signature bundle against the on-chain
    `genesis_keyset` (embedded from the Genesis Ceremony).
  - Schedules the change through the TimelockController.
- The actual parameter change is delivered as a call to a target contract
  (e.g., a `ParameterStore` contract that emits `ParameterUpdated`).

### Why verify signatures off-chain then on-chain?

CRYSTALS-Dilithium3 signatures are large (~$2,400 bytes) and gas-expensive to
verify natively on EVM. We use a **two-tier verification**:

1. **Off-chain:** Trustees generate Dilithium3 signatures on
   `keccak256(paramName + newValue + nonce)`. The `signatureBundle` is
   collected.
2. **On-chain:** The GovernanceRouter verifies a **compressed aggregate** —
   each trustee signs an **Ed25519** attestation of the
   `keccak256(Dilithium3_publicKey || parameterChangeDigest)` on an EVM-
   friendly curve. The EVM-verifiable proof is: "≥ quorum trustees, each
   of whom is in the Genesis keyset, co-signed this parameter change."

This delegates the heavyweight PQC verification to the air-gapped
constitution client (which already has `liboqs`) and uses the EVM only for
threshold enforcement + time-lock.

---

## 3. Parameter change vocabulary

Only the following on-chain-stored parameters may be changed via governance.
All other system behavior is **immutable code** and is changed only via the
Evolution Sub-Agent's self-refactoring (S3), which is itself gated by the
Constitution's formal verification + Chronos gates — not by this contract.

| Parameter | On-chain key | Type | Rationale |
|-----------|-------------|------|-----------|
| `max_drawdown` | `invA_threshold` | u16 (bips) | I1 invariant threshold |
| `max_leverage` | `invB_threshold` | u8 (x100) | I2 invariant ceiling |
| `max_concentration` | `invC_threshold` | u16 (bips) | I3 invariant limit |
| `quorum_threshold` | `governance_quorum` | u8 | May the quorum shrink/grow? |
| `time_lock_delay` | `governance_delay` | u64 (seconds) | Security delay length |
| `trustee_list_hash` | `genesis_keyset_hash` | bytes32 | New trustee roster (only via full ceremony) |

> Invariant I5 (Independence): The Constitution kernel never *reads* these
> parameters via a live RPC at proposal-evaluation time. The kernel reads them
> at **daemon startup** from `CONSTITUTION_MAX_{DRAWDOWN,LEVERAGE,CONCENTRATION}`
> env vars (Phase 10.4). Governance updates the env via a hot-reload signal —
> the kernel re-reads only after a clean validation cycle. This preserves
> I5: no code outside `constitution/` routes or signs anything.

---

## 4. State machine

```
NO_PROPOSAL
    |
      └── proposeParameterChange(...) → PROPOSAL_SCHEDULED
    |
      └── [delay elapsed] → READY
    |
      └── execute(...) → EXECUTED (parameter updated on-chain, kernel re-reads)
    |
      └── [anyone can cancel if quorum-threshold cancel signatures] → CANCELLED
    |
      └── [if quorum lost / keyset rotated] PROPOSAL_SCHEDULED → CANCELLED
```

### 4.1 Propose (off-chain quorum verification)

```solidity
function proposeParameterChange(
    string paramName,
    uint256 newValue,
    bytes[] memory signatureBundle,
    bytes32 genesisKeysetHash
) external pure returns (bool) {
    // 1. Verify genesisKeysetHash matches the embedded GENESIS_CEREMONY_ROOT
    //    stored at deploy time. If mismatch, revert "invalid keyset".
    // 2. Verify signatureBundle contains >= governance_quorum valid Ed25519
    //    attestations, each binding the signer to a key in genesisKeysetHash.
    // 3. Compute the operation id: keccak256(paramName, newValue, block.timestamp)
    // 4. Store pending proposal + quorum proof.
}
```

If the quorum is not met, `revert GovernanceInsufficientSignatures`.

### 4.2 Schedule (on-chain time-lock)

```solidity
function scheduleParameterChange(
    string paramName,
    uint256 newValue
) external returns (bytes32 operationId) {
    // 1. Verify a valid proposal exists for (paramName, newValue).
    // 2. Call TimelockController.schedule(
    //      address(parameterStore),
    //      0,
    //      abi.encodeWithSignature("setParameter(string,uint256)", paramName, newValue),
    //      bytes32(0),     // predecessor: none
    //      keccak256(abi.encode(paramName, newValue)),  // salt
    //      governance_delay  // default 7 days
    //    )
    // 3. Emit GovProposalScheduled(operationId, delay, paramName).
}
```

### 4.3 Cancel

Any holder of ≥ `governance_cancel_threshold` (e.g., 3-of-9) signatures may
cancel a **pending** (scheduled but not yet executed) parameter change:

```solidity
function cancelParameterChange(bytes32 operationId, bytes[] memory sigBundle)
    external returns (bool)
```

Cancellation is only valid for `isOperationPending`. Once `isOperationReady`,
it **cannot** be cancelled — the time-lock has expired and execution is
public, final, and auditable. This is the emergency window.

### 4.4 Execute

```solidity
function executeParameterChange(bytes32 operationId) external {
    require(isOperationReady(operationId), "not ready");
    // TimelockController.execute(...) → ParameterStore.setParameter(...)
    // Kernel is signaled to re-read via the hot-reload path.
    emit ParameterUpdated(paramName, newValue, block.timestamp);
}
```

---

## 5. Emergency / Doomsday interaction

The contract must account for the case where trustees are **unreachable** but
the system is in `EmergencyHalt` and governance recovery is needed.

| Scenario | Path |
|----------|------|
| Normal quorum available | Standard propose → schedule → execute (7-day delay) |
| Quorum lost (≤ floor(N/3) trustees reachable) | Governance is frozen. System remains in current configuration forever. Doomsday protocol (I7) is the only liveness path — it does NOT require trustee signatures. |
| Trustee key compromised | Any trustee may broadcast a `KeyCompromised(pubkey)` event. A proposal to rotate that key requires the **remaining** quorum (e.g., 4-of-9) + the standard time-lock. |
| Doomsday enters LIQUIDATING | The time-lock is **irrelevant** — Doomsday operates autonomously per its FSM. The contract merely records the on-chain evidence sealing. |

**Key invariant:** The time-lock contract never *shortens* the Doomsday
escalation path. The Doomsday daemon's `seal` step writes to this contract's
`emitSeal(hash)` method, which is callable **only** by the Doomsday daemon's
on-chain address (a separate, pre-ceremony-deployed contract).

---

## 6. Deployment & anchoring

### 6.1 Deploy order

1. `ParameterStore` — holds the mutable parameter values (owned by
   TimelockController).
2. `TimelockController` — deployed with `minDelay = 7 days`, proposer role
   assigned to `GovernanceRouter`, executor role assigned to `address(0)`
   (open execution — anyone can call execute).
3. `GovernanceRouter` — deployed with:
   - `immutable GENESIS_KEYSET_HASH = <root hash from Genesis Ceremony>`
   - `immutable quorum = 5`
   - `immutable cancelThreshold = 3`
   - `address(TimelockController)` reference
   - `address(ParameterStore)` reference
4. The deployer calls `genesisKeysetHash = <from secure_keys.rs>` and
   `timelock.updateDelay()` is locked — `changeDelay()` requires a
   self-scheduled proposal.

### 6.2 Verification gate

The contract source is compiled with Solidity `^0.8.20` and verified on the
block explorer. The deployed bytecode hash is recorded in the ceremony journal
and in `docs/GENESIS-CEREMONY.md`.

---

## 7. Data-driven config

Per AGENTS.md §3 (G6 is a *foundation*, not a final artifact):

- The **quorum size** (5-of-9) is a constructor argument, not hardcoded.
- The **time-lock delay** (7 days) is a constructor argument.
- The **parameter vocabulary** is a string-keyed map — new parameters can be
  added to `ParameterStore` via a governance proposal that schedules a new
  `setParameter` call. The contract does not need a new deploy for new params.
- The **trustee keyset hash** is immutable at deploy (set from the Genesis
  Ceremony bundle). New keys require a new contract deploy + new keyset hash —
  which is the intended ceremony-grade ceremony.

**Genesis asks:** Does this change within 100 years? The quorum size might,
the delay might, the parameter set might. Those are constructor args / config.
The *mechanism* (threshold + delay + cancellation + on-chain audit) is Genesis.

---

## 8. Security notes

- The TimelockController is deployed behind a **2-step role handoff**: the
  deployer renounces the `PROPOSER_ROLE` and `TIMELOCK_ADMIN_ROLE` after
  setting up GovernanceRouter. After this, only multi-sig + time-lock can
  act — the deployer is powerless.
- `openZeppelin/contracts-governance` contracts are used unmodified where
  possible to minimize the attack surface we hand-write.
- The contract does **not** hold funds. It is a state machine, not a vault.
  (Funds custody, if needed, is G8's gateway boundary — not this contract's concern.)
- The delay is the **only** defense against a compromised quorum executing
  malicious parameter changes. 7 days is chosen to allow the Doomsday
  protocol to detect anomalous parameter updates.
