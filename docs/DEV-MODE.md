# Development Mode — Running Before the Genesis Ceremony

> **This document clarifies the distinction between development mode and
> production mode.** Genesis DNA (G1–G9) is complete. The Genesis Ceremony
> (air-gap key generation) is a one-time production event. This guide lets you
> run the full system on any development laptop for testing and validation
> *without* the ceremony, with a clear migration path to production.

---

## 1. Architecture overview

```
┌─────────────────────────────────────────────────────────┐
│                    Dev Mode (any laptop/VPS)            │
║                                                         │
║  ┌──────────────┐       ┌──────────┐    ┌────────────┐ │
║  │ constitutiond │◄─────► Cortex   │◄──►│ Doomsday    │ │
║  │ (Rust G1)     │ IPC    │ engine   │    │ daemon     │ │
║  └──────────────┘        └──────────┘    └────────────┘ │
║       ▲                     │              ▲            │
║       │ REST/WS             │              │ heartbeat  │
║  ┌────┴────────┐     ┌─────┴─────┐    ┌───┴────┐       │
║  │ Gateway     │     │ Mesh node │◄──►│...x3  │       │
║  │ (NestJS G8) │     │ (G4)      │    │ (G4)   │       │
║  └─────────────┘     └───────────┘    └────────┘       │
║       ▲                     ▲              ▲            │
║       │ HTTP                │ WS gossip    │ WS gossip  │
║  ┌────┴────────┐    ┌─────┴────┐   ┌─────┴──┐        │
║  │ Evolution   │    │ Compliance│   │ (etc)  │        │
║  │ agent(G2)   │    │ (G6)      │   └────────┘        │
║  └─────────────┘    └───────────┘                     │
║                                                         │
║  KEYS: Placeholder HMAC-SHA3-512 (not real PQC)        │
║  GOVERNANCE: No genesis keyset; dev governance_key=""  │
╰─────────────────────────────────────────────────────────┰
                                                         ║
┌─────────────────────────────────────────────────────────╂┐
│              Production Mode (VPS, post-Ceremony)       ││
│                                                         ││
│  Same component stack, BUT:                              ││
│  • constitutiond embeds real CRYSTALS-Dilithium3 pubkeys ││
│  • Mesh nodes use real PQC identities                    ││
│  • Doomsday disarm requires real governance key          ││
│  • Genesis Ceremony (air-gap) is MANDATORY               ││
│  • Time-lock governance contract deployed on-chain       ││
╰───────────────────────────────────────────────────────────┘
```

---

## 2. Dev mode prerequisites

| Tool | How to check |
|------|-------------|
| Rust/cargo | `cargo --version` (install via [rustup](https://rustup.rs)) |
| Python 3.11+ | `python --version`; `pip install -e cortex/ adapters/ doomsday/ mesh/ compliance/ simulation/ evolution/` |
| Node 18+ | `node --version` (only for gateway) |
| (Optional) Docker | `docker --version` (for docker-compose) |

No air-gap laptop required. No new hardware required. The system boots with
placeholder cryptographic keys and a default dev governance key.

---

## 3. Starting all services locally

### Option A: Docker Compose (simplest)

```powershell
# Build all images (first run, ~5 min)
docker-compose build

# Start all 7 services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f constitution
docker-compose logs -f cortex
docker-compose logs -f doomsday
```

Services will auto-restart on failure (`restart: unless-stopped`).

### Option B: SupervisorD (without Docker, native VPS)

```powershell
# Install supervisor
pip install supervisor

# Start all 7 programs
supervisord -c supervisord.conf

# Check status
supervisorctl status

# Restart a single service
supervisorctl restart cortex-trading
```

### Option C: Manual (one service at a time)

```powershell
# 1. Constitution (Rust risk kernel)
cargo build --release --manifest-path constitution/Cargo.toml
.\constitution\target\release\constitutiond.exe

# 2. Cortex trading daemon (continuous loop)
python -m cortex.trading_daemon --asset EURUSD --equity 100000

# 3. Doomsday dead-man switch
python -m doomsday --run --heartbeat-interval 5

# 4. Mesh nodes (x3, separate terminals)
python -c "from mesh.node_daemon import EdgeNodeDaemon; d=EdgeNodeDaemon(node_id='mesh-0'); d.start_heartbeat(); import time; time.sleep(float('inf'))"
# (repeat with node_id='mesh-1' and 'mesh-2')
```

---

## 4. Dev mode verification

After starting services, verify each component:

```powershell
# Constitution health (TCP 127.0.0.1:15565)
echo '{"protocol_version":1,"request_id":"hc","opcode":"Heartbeat","payload":"{}"}' | & "constitution\target\release\constitution_cli.exe"
# Expected: {"alive":true,"protocol_version":1}

# Doomsday self-test
python -m doomsday --self-test
# Expected: DoM: self-test PASSED

# Full pipeline (Cortex -> Constitution -> verdict)
python run_pipeline.py
# Expected: 2 proposals approved, 1 NoAction, SUCCESS message

# Chaos engine (failure injection)
python simulation/tests/chaos_engine.py
# Expected: 3 scenarios tested, all pass

# Chronos 250-year stress
python simulation/tests/integration_chronos.py
# Expected: 250 simulated years, passed=true

# Full test suite
python -m pytest -q
# Expected: 216 passed, 2 skipped
```

---

## 5. Dev mode configuration

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `CONSTITUTION_HOST` | `127.0.0.1` | Constitution daemon bind address |
| `CONSTITUTION_PORT` | `15565` | Constitution daemon bind port |
| `CONSTITUTION_MAX_DRAWDOWN` | `0.15` | Max drawdown threshold (I1) |
| `CONSTITUTION_MAX_LEVERAGE` | `2.5` | Global leverage cap (I2) |
| `CONSTITUTION_MAX_CONCENTRATION` | `0.20` | Asset concentration limit (I3) |
| `DOOMSDAY_GOVERNANCE_KEY` | `""` | Default dev key (empty string) |
| `PYTHONPATH` | See docker-compose.yml | Python module search path |

**Key point:** Dev mode uses `DOOMSDAY_GOVERNANCE_KEY=""` (empty string). In
production, the Genesis Ceremony generates a real governance key that `disarm`
requires.

---

## 6. Migration to production

The migration path from dev to production is a **single step**: the Genesis
Ceremony.

### Step 1: Run the Genesis Ceremony
- Use `docs/GENESIS-CEREMONY.md` procedure
- Air-gap laptops required (brand-new, factory-reset)
- Generates N=5 trustee PQC key pairs (CRYSTALS-Dilithium3)
- Produces `genesis_keyset.json` bundle + `GENESIS_CEREMONY_ROOT_HASH`

### Step 2: Embed keys in `secure_keys.rs`
The `authorize_signing` method in `constitution/src/secure_keys.rs` is currently
a threshold-only check (`proof_claim >= 2`). After the ceremony, it will be
replaced with real PQC signature verification:

```rust
// BEFORE (dev mode):
if proof_claim >= self.signing_threshold { ... }

// AFTER (post-ceremony):
let quorum = verify_pqc_signatures(proof_claim, &EMBEDDED_PUBLIC_KEYS)?;
if quorum >= self.signing_threshold { ... }
```

This is the **only** code change required for production. All other Genesis DNA
components remain unchanged.

### Step 3: Update Doomsday governance key
```powershell
# Dev:
python -m doomsday --run --governance-key ""

# Production (real key from ceremony):
python -m doomsday --run --governance-key "<64-byte hex string>"
```

### Step 4: Deploy to edge mesh
- Replace `docker-compose.yml` dev config with production endpoints
- Distribute mesh nodes across geographic regions (AWS us-east-1, eu-west-1,
  ap-southeast-1, etc.)
- Deploy the time-lock governance contract on-chain
- Anchor `GENESIS_CEREMONY_ROOT_HASH` in the contract

### Security checklist for migration

| Item | Dev mode | Production |
|------|----------|------------|
| Air-gap key generation | Not used | **Required** (Section 3.1) |
| Private key storage | On VPS disk | Trustee HSMs (Section 5) |
| PQC signatures | HMAC-SHA3 placeholder | CRYSTALS-Dilithium3 (Section 5) |
| Governance key | `""` (empty) | 64-byte hex from ceremony |
| Quorum | N/A | 5-of-9 (Section 4) |
| Time-lock contract | Not deployed | Sepolia → Mainnet (Phase 15.2) |

---

## 7. Important caveats

1. **Dev mode has NO governance security.** Anyone with access to the VPS can
   disarm the Doomsday daemon (since `governance_key=""`). The Constitution's
   `authorize_signing` does not verify real signatures. **Do not deploy real
   capital in dev mode.**

2. **The Invariant I7 (zero-human override) is NOT enforced in dev mode.** In
   production, only the cryptographic quorum can change governance — not humans,
   not even you. Dev mode bypasses this for convenience.

3. **The Invariant I5 (Independence)** IS enforced even in dev mode — only the
   Constitution process can approve trades. No other service may sign or route
   orders directly.

4. **Dev mode is for:** testing the pipeline, validating strategy logic,
   running simulations, verifying CI/CD, training the Cortex engine. It is NOT
   for running with real trading capital.

5. **Production migration is irreversible.** Once the Genesis Ceremony keys are
   embedded and the on-chain contract is anchored, governance requires the
   cryptographic quorum. You cannot "go back" to dev mode for production.
