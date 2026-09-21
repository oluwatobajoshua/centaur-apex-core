#![deny(unsafe_code)]

pub mod invariants;
pub mod ipc;
pub mod secure_keys;
pub mod state_machine;
pub mod tmr_voter;

use invariants::RiskParameters;
use serde::{Deserialize, Serialize};
use state_machine::{ConstitutionKernel, SystemOperationalState};

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

    pub fn transition_counter(&self) -> u64 {
        self.kernel.transition_count()
    }

    pub fn transition_history(&self) -> Vec<(String, String)> {
        self.kernel
            .transition_history()
            .iter()
            .map(|(from, to)| (format!("{from:?}"), format!("{to:?}")))
            .collect()
    }
}
