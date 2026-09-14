use crate::{PortfolioState, TradeProposal, ConstitutionVerdict, RiskViolationCode};

pub struct RiskParameters {
    pub max_drawdown_threshold: f64,  
    pub global_leverage_cap: f64,     
    pub max_asset_concentration: f64, 
}

impl Default for RiskParameters {
    fn default() -> Self {
        Self { max_drawdown_threshold: 0.15, global_leverage_cap: 2.5, max_asset_concentration: 0.20 }
    }
}

pub fn evaluate_proposal(state: &PortfolioState, proposal: &TradeProposal, params: &RiskParameters) -> ConstitutionVerdict {
    if state.total_equity <= 0.0 || state.high_water_mark <= 0.0 || proposal.target_notional < 0.0 || state.total_equity.is_nan() || proposal.target_notional.is_nan() {
        return ConstitutionVerdict::Rejected { reason_code: RiskViolationCode::InvalidNumericalState };
    }
    let drawdown = (state.high_water_mark - state.total_equity) / state.high_water_mark;
    if drawdown >= params.max_drawdown_threshold {
        return ConstitutionVerdict::EmergencyLiquidationAll;
    }
    let current_gross_notional: f64 = state.open_positions.iter().map(|p| p.notional_value.abs()).sum();
    let projected_leverage = (current_gross_notional + proposal.target_notional) / state.total_equity;
    if projected_leverage > params.global_leverage_cap {
        return ConstitutionVerdict::Rejected { reason_code: RiskViolationCode::GlobalLeverageCapExceeded };
    }
    let existing_asset_notional: f64 = state.open_positions.iter().filter(|p| p.asset_id == proposal.asset_id).map(|p| p.notional_value.abs()).sum();
    let asset_concentration = (existing_asset_notional + proposal.target_notional) / state.total_equity;
    if asset_concentration > params.max_asset_concentration {
        return ConstitutionVerdict::Rejected { reason_code: RiskViolationCode::AssetConcentrationLimitExceeded };
    }
    ConstitutionVerdict::Approved { adjusted_notional: proposal.target_notional }
}
