# IPC Protocol Reference — Centaur-Apex Core

**Version:** 1
**Transport:** TCP (length-prefixed framing)
**Default address:** `127.0.0.1:15565`

---

## Framing

Each message is a single JSON object with a 4-byte big-endian unsigned
length prefix:

```
[ 4 bytes: payload length (big-endian u32) ] [ N bytes: JSON payload ]
```

`MAX_FRAME_BYTES = 16,384` (16 KB). If a frame exceeds this, the receiver
rejects it immediately without parsing; the sender receives
`FrameSizeExceeded`.

The length prefix is 4 bytes (`unsigned int`, format `>I`). The maximum
encodeable payload length is `16,384` bytes (the JSON envelope alone).
Longer payloads must be split into multiple requests (not implemented yet).

---

## Envelope

Every message is an `IpcEnvelope`:

```json
{
  "protocol_version": 1,
  "request_id": "unique-request-id",
  "opcode": "<opcode>",
  "payload": "<JSON-stringified request or response>"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `protocol_version` | `u32` | Must be `1`. Mismatch returns `VersionMismatch`. |
| `request_id` | `String` | Caller-assigned unique ID for idempotency. |
| `opcode` | `IpcOpcode` | One of: `EvaluateProposal`, `GetStatus`, `AttemptRecovery`, `Heartbeat`. |
| `payload` | `String` | A JSON-encoded request or response object (string-encoded for serialization safety). |

---

## Opcodes

### `Heartbeat`

**Purpose:** Verify daemon liveness. Returns server status.

**Request payload:** `{}` (empty)

**Response:**
```json
{
  "alive": true,
  "protocol_version": 1
}
```

---

### `EvaluateProposal`

**Purpose:** Submit a trade proposal for risk evaluation.

**Request payload:**
```json
{
  "portfolio": {
    "timestamp": 1789450800,
    "total_equity": 50000.0,
    "cash_balance": 45000.0,
    "high_water_mark": 52000.0,
    "open_positions": [
      {
        "asset_id": "EURUSD",
        "notional_value": 5000.0,
        "entry_price": 1.0820
      }
    ]
  },
  "proposal": {
    "proposal_id": "p1",
    "asset_id": "EURUSD",
    "direction": "Buy",
    "target_notional": 10000.0,
    "max_acceptable_slippage": 0.0015
  }
}
```

**Response:**
```json
{
  "verdict": {
    "Approved": {
      "adjusted_notional": 10000.0
    }
  },
  "system_state": "Normal"
}
```

or

```json
{
  "verdict": {
    "Rejected": {
      "reason_code": "GlobalLeverageCapExceeded"
    }
  },
  "system_state": "Normal"
}
```

**`direction` values:** `"Buy"` or `"Sell"` (case-sensitive; matches Rust
`OrderDirection` enum serialization).

**`reason_code` values:** `DrawdownCircuitBreaker`, `GlobalLeverageCapExceeded`,
`AssetConcentrationLimitExceeded`, `InvalidNumericalState`.

---

### `GetStatus`

**Purpose:** Query current Constitution operational status.

**Request payload:** `{}` (empty)

**Response:**
```json
{
  "system_state": "Normal",
  "proposals_seen": 120,
  "emergencies": 0
}
```

---

### `AttemptRecovery`

**Purpose:** Attempt to transition out of `EmergencyHalt` state. Requires
cryptographic proof of legitimacy (see `docs/GOVERNANCE.md`).

**Request payload:**
```json
{
  "cryptographic_proof_valid": true
}
```

**Response:**
```json
{
  "recovery_success": true
}
```

Recovery succeeds only if the system is in `EmergencyHalt` state AND the
proof is valid.

---

## Versioning policy

| Change type | Action |
|-------------|--------|
| New opcode | Bump `protocol_version` |
| Changed envelope schema | Bump `protocol_version` |
| New optional field added to existing envelope | Patch (no version bump) |
| Removed or renamed field | Bump `protocol_version` |

When `protocol_version` mismatches, the server responds with:
```json
{
  "error": "VersionMismatch"
}
```

---

## Error responses

Malformed requests return:

```json
{
  "error": "<error_code>"
}
```

| Error code | Meaning |
|------------|---------|
| `VersionMismatch` | `protocol_version` not equal to `1` |
| `MalformedEnvelope` | JSON is not a valid `IpcEnvelope` |
| `MalformedPayload` | The `payload` string is not valid for the given `opcode` |
| `FrameSizeExceeded` | Frame exceeds `MAX_FRAME_BYTES` (16KB) |

---

## Connection model

The server (`constitutiond`) is **stateless across connections** — each
connection creates a fresh `ConstitutionService` instance. Callers that
need multi-request state (proposal → feedback → re-proposal) must use a
single persistent connection via `ConstitutionIPCClient.open_session()`.

This is a known limitation; a long-lived actor-based kernel is the
intended production evolution (see `docs/ADRS.md` ADR-002).