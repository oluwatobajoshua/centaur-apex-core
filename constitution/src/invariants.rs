use crate::{ConstitutionVerdict, PortfolioState, RiskViolationCode, TradeProposal};

#[derive(Debug)]
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

impl RiskParameters {
    /// Reads thresholds from environment variables, falling back to the
    /// constitutional defaults. Data-driven config per AGENTS.md §7
    /// ("schema over code") — no hardcoded venue/market assumptions.
    ///
    /// Variables: `CONSTITUTION_MAX_DRAWDOWN`, `CONSTITUTION_MAX_LEVERAGE`,
    /// `CONSTITUTION_MAX_CONCENTRATION`.
    pub fn from_env_or_default() -> Self {
        let read = |name: &str, default: f64| -> f64 {
            std::env::var(name)
                .ok()
                .and_then(|v| v.trim().parse::<f64>().ok())
                .unwrap_or(default)
        };
        Self {
            max_drawdown_threshold: read("CONSTITUTION_MAX_DRAWDOWN", 0.15),
            global_leverage_cap: read("CONSTITUTION_MAX_LEVERAGE", 2.5),
            max_asset_concentration: read("CONSTITUTION_MAX_CONCENTRATION", 0.20),
        }
    }
}

pub fn evaluate_proposal(
    state: &PortfolioState,
    proposal: &TradeProposal,
    params: &RiskParameters,
) -> ConstitutionVerdict {
    if state.total_equity <= 0.0
        || state.high_water_mark <= 0.0
        || proposal.target_notional <= 0.0
        || state.total_equity.is_nan()
        || state.total_equity.is_infinite()
        || state.high_water_mark.is_nan()
        || state.high_water_mark.is_infinite()
        || proposal.target_notional.is_nan()
        || proposal.target_notional.is_infinite()
    {
        return ConstitutionVerdict::Rejected {
            reason_code: RiskViolationCode::InvalidNumericalState,
        };
    }
    let drawdown = (state.high_water_mark - state.total_equity) / state.high_water_mark;
    if drawdown >= params.max_drawdown_threshold {
        return ConstitutionVerdict::EmergencyLiquidationAll;
    }
    let current_gross_notional: f64 = state
        .open_positions
        .iter()
        .map(|p| p.notional_value.abs())
        .sum();
    let projected_leverage =
        (current_gross_notional + proposal.target_notional) / state.total_equity;
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
    let asset_concentration =
        (existing_asset_notional + proposal.target_notional) / state.total_equity;
    if asset_concentration > params.max_asset_concentration {
        return ConstitutionVerdict::Rejected {
            reason_code: RiskViolationCode::AssetConcentrationLimitExceeded,
        };
    }
    ConstitutionVerdict::Approved {
        adjusted_notional: proposal.target_notional,
    }
}

#[cfg(kani)]
mod verification {
    use super::*;
    use crate::{PortfolioState, Position, TradeProposal};

    #[kani::proof]
    fn verify_evaluate_proposal_no_panic() {
        let mut positions: Vec<Position> = Vec::new();
        for _ in 0..4 {
            positions.push(kani::any::<Position>());
        }
        let state = PortfolioState {
            timestamp: kani::any::<u64>(),
            total_equity: kani::any::<f64>(),
            cash_balance: kani::any::<f64>(),
            high_water_mark: kani::any::<f64>(),
            open_positions: positions,
        };
        let proposal: TradeProposal = kani::any();
        let params: RiskParameters = kani::any();
        let _ = evaluate_proposal(&state, &proposal, &params);
    }
}

#[cfg(test)]
mod proptests {
    use super::*;
    use crate::{OrderDirection, Position, TradeProposal};
    use proptest::prelude::*;

    /// Strategy: any f64 including NaN and infinities — mirrors Kani's
    /// `any::<f64>()` coverage for the property tests.
    fn arb_f64() -> impl Strategy<Value = f64> {
        prop_oneof![
            any::<f64>(),
            Just(f64::NAN),
            Just(f64::INFINITY),
            Just(f64::NEG_INFINITY),
            Just(0.0f64),
            Just(-0.0f64),
        ]
    }

    fn arb_position() -> impl Strategy<Value = Position> {
        (any::<String>(), arb_f64(), arb_f64()).prop_map(|(asset_id, notional, price)| Position {
            asset_id,
            notional_value: notional,
            entry_price: price,
        })
    }

    fn arb_state() -> impl Strategy<Value = PortfolioState> {
        (
            any::<u64>(),
            arb_f64(),
            arb_f64(),
            arb_f64(),
            proptest::collection::vec(arb_position(), 0..8),
        )
            .prop_map(|(ts, equity, cash, hwm, positions)| PortfolioState {
                timestamp: ts,
                total_equity: equity,
                cash_balance: cash,
                high_water_mark: hwm,
                open_positions: positions,
            })
    }

    fn arb_proposal() -> impl Strategy<Value = TradeProposal> {
        (
            any::<String>(),
            any::<String>(),
            prop_oneof![Just(OrderDirection::Buy), Just(OrderDirection::Sell)],
            arb_f64(),
            arb_f64(),
        )
            .prop_map(|(id, asset, dir, notional, slippage)| TradeProposal {
                proposal_id: id,
                asset_id: asset,
                direction: dir,
                target_notional: notional,
                max_acceptable_slippage: slippage,
            })
    }

    fn arb_params() -> impl Strategy<Value = RiskParameters> {
        (arb_f64(), arb_f64(), arb_f64()).prop_map(|(dd, lev, conc)| RiskParameters {
            max_drawdown_threshold: dd,
            global_leverage_cap: lev,
            max_asset_concentration: conc,
        })
    }

    // P1: evaluate_proposal never panics on any input
    proptest! {
        #[test]
        fn prop_evaluate_never_panics(
            state in arb_state(),
            proposal in arb_proposal(),
            params in arb_params(),
        ) {
            // proptest catches any panic as a test failure
            evaluate_proposal(&state, &proposal, &params);
        }
    }

    // P2: drawdown breach always triggers EmergencyLiquidationAll
    proptest! {
        #[test]
        fn prop_drawdown_breach_triggers_emergency(
            equity in 1.0f64..1_000_000.0,
            hwm in 1.0f64..1_000_000.0,
            threshold in 0.01f64..0.50,
        ) {
            let hwm = hwm.max(equity + 1.0); // ensure hwm > equity so drawdown > 0
            let drawdown = (hwm - equity) / hwm;
            if drawdown >= threshold {
                let state = PortfolioState {
                    timestamp: 1,
                    total_equity: equity,
                    cash_balance: equity,
                    high_water_mark: hwm,
                    open_positions: vec![],
                };
                let proposal = TradeProposal {
                    proposal_id: "t".to_string(),
                    asset_id: "BTC".to_string(),
                    direction: OrderDirection::Buy,
                    target_notional: 100.0,
                    max_acceptable_slippage: 0.001,
                };
                let params = RiskParameters {
                    max_drawdown_threshold: threshold,
                    global_leverage_cap: 2.5,
                    max_asset_concentration: 0.20,
                };
                let verdict = evaluate_proposal(&state, &proposal, &params);
                assert!(
                    matches!(verdict, ConstitutionVerdict::EmergencyLiquidationAll),
                    "drawdown {drawdown} >= threshold {threshold} must trigger EmergencyLiquidationAll"
                );
            }
        }
    }

    // P3: approved verdict preserves target_notional exactly
    proptest! {
        #[test]
        fn prop_approved_preserves_notional(
            equity in 100_000.0f64..10_000_000.0,
            notional in 1.0f64..1_000.0,
        ) {
            let state = PortfolioState {
                timestamp: 1,
                total_equity: equity,
                cash_balance: equity,
                high_water_mark: equity,
                open_positions: vec![],
            };
            let proposal = TradeProposal {
                proposal_id: "t".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: notional,
                max_acceptable_slippage: 0.001,
            };
            let params = RiskParameters::default();
            let verdict = evaluate_proposal(&state, &proposal, &params);
            if let ConstitutionVerdict::Approved { adjusted_notional } = verdict {
                assert!(
                    (adjusted_notional - notional).abs() < 1e-6,
                    "approved notional {adjusted_notional} must equal proposal {notional}"
                );
            }
        }
    }

    // P4: NaN / inf / negative equity always → Rejected with InvalidNumericalState
    proptest! {
        #[test]
        fn prop_invalid_numerical_state_rejected(
            equity in prop_oneof![Just(f64::NAN), Just(f64::INFINITY), Just(-100.0), Just(0.0)],
            hwm in prop_oneof![Just(f64::NAN), Just(0.0), Just(100.0)],
            notional in prop_oneof![Just(f64::NAN), Just(-50.0), Just(f64::INFINITY)],
        ) {
            let state = PortfolioState {
                timestamp: 1,
                total_equity: equity,
                cash_balance: 0.0,
                high_water_mark: hwm,
                open_positions: vec![],
            };
            let proposal = TradeProposal {
                proposal_id: "t".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: notional,
                max_acceptable_slippage: 0.001,
            };
            let verdict = evaluate_proposal(&state, &proposal, &RiskParameters::default());
            assert!(
                matches!(verdict, ConstitutionVerdict::Rejected { reason_code: RiskViolationCode::InvalidNumericalState }),
                "invalid numerical inputs must yield InvalidNumericalState, got {verdict:?}"
            );
        }
    }
}
