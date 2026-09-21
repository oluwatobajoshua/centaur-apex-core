#!/usr/bin/env bash
# ==============================================================================
# CENTAUR-APEX: Zero-Time Bootstrap for the full 6-Module + Chronos monorepo.
# Mirrors the PowerShell build scripts for POSIX/dev-container environments.
# ==============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "Bootstrapping Centaur-Apex Core Workspace..."

# 1. Create complete directory hierarchy
mkdir -p constitution/src/bin constitution/proofs \
         cortex/cortex cortex/models cortex/tests \
         evolution/evolution evolution/patches evolution/tests \
         adapters/adapters/venue_plugins adapters/schemas adapters/tests \
         mesh/mesh mesh/mesh/microgrid mesh/tests \
         compliance/compliance compliance/governance compliance/tests \
         simulation/simulation simulation/tests \
          docs .github/workflows docker \
          docker/constitution docker/gateway docker/python-services

# 2. constitution/Cargo.toml
cat > constitution/Cargo.toml <<'EOF'
[package]
name = "iron_constitution"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

[dev-dependencies]

[[bin]]
name = "constitutiond"
path = "src/bin/constitutiond.rs"
EOF

# 3. constitution/src/lib.rs
cat > constitution/src/lib.rs <<'EOF'
pub mod invariants;
pub mod ipc;
pub mod secure_keys;
pub mod state_machine;
pub mod tmr_voter;

use serde::{Deserialize, Serialize};
use state_machine::{ConstitutionKernel, SystemOperationalState};
use invariants::RiskParameters;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum OrderDirection {
    Buy,
    Sell,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Position {
    pub asset_id: String,
    pub notional_value: f64,
    pub entry_price: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct PortfolioState {
    pub timestamp: u64,
    pub total_equity: f64,
    pub cash_balance: f64,
    pub high_water_mark: f64,
    pub open_positions: Vec<Position>,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct TradeProposal {
    pub proposal_id: String,
    pub asset_id: String,
    pub direction: OrderDirection,
    pub target_notional: f64,
    pub max_acceptable_slippage: f64,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum RiskViolationCode {
    MaxDrawdownBreached,
    GlobalLeverageCapExceeded,
    AssetConcentrationLimitExceeded,
    InvalidNumericalState,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum ConstitutionVerdict {
    Approved { adjusted_notional: f64 },
    Rejected { reason_code: RiskViolationCode },
    EmergencyLiquidationAll,
}

pub struct ConstitutionService {
    kernel: ConstitutionKernel,
}

impl ConstitutionService {
    pub fn new(params: RiskParameters) -> Self {
        Self {
            kernel: ConstitutionKernel::new(params),
        }
    }

    pub fn handle_incoming_request(
        &mut self,
        portfolio: &PortfolioState,
        proposal: &TradeProposal,
    ) -> ConstitutionVerdict {
        self.kernel.process_proposal(portfolio, proposal)
    }

    pub fn get_status(&self) -> SystemOperationalState {
        self.kernel.current_state()
    }

    pub fn attempt_cryptographic_recovery(&mut self, proof_valid: bool) -> bool {
        self.kernel.attempt_recovery(proof_valid)
    }

    pub fn proposal_counter(&self) -> u64 {
        self.kernel.proposal_count()
    }

    pub fn emergency_counter(&self) -> u64 {
        self.kernel.emergency_count()
    }
}
EOF

# 4. constitution/src/invariants.rs
cat > constitution/src/invariants.rs <<'EOF'
use crate::{PortfolioState, TradeProposal, ConstitutionVerdict, RiskViolationCode};

pub struct RiskParameters {
    pub max_drawdown_threshold: f64,
    pub global_leverage_cap: f64,
    pub max_asset_concentration: f64,
}

impl Default for RiskParameters {
    fn default() -> Self {
        Self {
            max_drawdown_threshold: 0.15,
            global_leverage_cap: 2.5,
            max_asset_concentration: 0.20,
        }
    }
}

pub fn evaluate_proposal(
    state: &PortfolioState,
    proposal: &TradeProposal,
    params: &RiskParameters,
) -> ConstitutionVerdict {
    if state.total_equity <= 0.0 || state.high_water_mark <= 0.0
        || proposal.target_notional < 0.0
        || state.total_equity.is_nan() || proposal.target_notional.is_nan()
    {
        return ConstitutionVerdict::Rejected {
            reason_code: RiskViolationCode::InvalidNumericalState,
        };
    }

    let drawdown = (state.high_water_mark - state.total_equity) / state.high_water_mark;
    if drawdown >= params.max_drawdown_threshold {
        return ConstitutionVerdict::EmergencyLiquidationAll;
    }

    let current_gross_notional: f64 = state.open_positions.iter().map(|p| p.notional_value.abs()).sum();
    let projected_leverage = (current_gross_notional + proposal.target_notional) / state.total_equity;
    if projected_leverage > params.global_leverage_cap {
        return ConstitutionVerdict::Rejected {
            reason_code: RiskViolationCode::GlobalLeverageCapExceeded,
        };
    }

    let existing_asset_notional: f64 = state
        .open_positions
        .iter()
        .filter(|p| p.asset_id == proposal.asset_id)
        .map(|p| p.notional_value.abs())
        .sum();

    let asset_concentration = (existing_asset_notional + proposal.target_notional) / state.total_equity;
    if asset_concentration > params.max_asset_concentration {
        return ConstitutionVerdict::Rejected {
            reason_code: RiskViolationCode::AssetConcentrationLimitExceeded,
        };
    }

    ConstitutionVerdict::Approved {
        adjusted_notional: proposal.target_notional,
    }
}
EOF

echo "Bootstrap artifacts written to: $ROOT"
echo "Next: cargo build --manifest-path constitution/Cargo.toml"