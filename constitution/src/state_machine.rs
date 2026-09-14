use crate::invariants::{evaluate_proposal, RiskParameters};
use crate::{PortfolioState, TradeProposal, ConstitutionVerdict, RiskViolationCode};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SystemOperationalState {
    Normal,
    SoftDeleveraging,
    EmergencyHalt,
    AutonomousRecovery,
}

pub struct ConstitutionKernel {
    state: SystemOperationalState,
    params: RiskParameters,
    proposal_count: u64,
    emergency_count: u64,
}

impl ConstitutionKernel {
    pub fn new(params: RiskParameters) -> Self {
        Self {
            state: SystemOperationalState::Normal,
            params,
            proposal_count: 0,
            emergency_count: 0,
        }
    }

    pub fn current_state(&self) -> SystemOperationalState {
        self.state
    }

    pub fn proposal_count(&self) -> u64 {
        self.proposal_count
    }

    pub fn emergency_count(&self) -> u64 {
        self.emergency_count
    }

    pub fn process_proposal(
        &mut self,
        portfolio: &PortfolioState,
        proposal: &TradeProposal,
    ) -> ConstitutionVerdict {
        self.proposal_count = self.proposal_count.saturating_add(1);

        if self.state == SystemOperationalState::EmergencyHalt
            || self.state == SystemOperationalState::AutonomousRecovery
        {
            return ConstitutionVerdict::Rejected {
                reason_code: RiskViolationCode::MaxDrawdownBreached,
            };
        }

        let verdict = evaluate_proposal(portfolio, proposal, &self.params);

        match verdict {
            ConstitutionVerdict::EmergencyLiquidationAll => {
                self.emergency_count = self.emergency_count.saturating_add(1);
                self.state = SystemOperationalState::EmergencyHalt;
                ConstitutionVerdict::EmergencyLiquidationAll
            }
            ConstitutionVerdict::Rejected { ref reason_code } => {
                if *reason_code == RiskViolationCode::MaxDrawdownBreached {
                    self.emergency_count = self.emergency_count.saturating_add(1);
                    self.state = SystemOperationalState::EmergencyHalt;
                    ConstitutionVerdict::EmergencyLiquidationAll
                } else {
                    verdict
                }
            }
            ConstitutionVerdict::Approved { .. } => {
                if portfolio.high_water_mark > 0.0 {
                    let drawdown =
                        (portfolio.high_water_mark - portfolio.total_equity) / portfolio.high_water_mark;
                    if drawdown >= (self.params.max_drawdown_threshold * 0.80) {
                        self.state = SystemOperationalState::SoftDeleveraging;
                    }
                }
                verdict
            }
        }
    }

    pub fn attempt_recovery(&mut self, cryptographic_proof_valid: bool) -> bool {
        if self.state == SystemOperationalState::EmergencyHalt && cryptographic_proof_valid {
            self.state = SystemOperationalState::AutonomousRecovery;
            self.state = SystemOperationalState::Normal;
            true
        } else {
            false
        }
    }

    pub fn params(&self) -> &RiskParameters {
        &self.params
    }
}
