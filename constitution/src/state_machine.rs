use crate::invariants::{evaluate_proposal, RiskParameters};
use crate::{ConstitutionVerdict, PortfolioState, RiskViolationCode, TradeProposal};
use std::collections::VecDeque;

/// Bounded depth of the operational state-change journal. Lifetime totals are
/// tracked by `transition_count`; the journal keeps only the most recent
/// window so memory stays constant over the 100-year operational lifespan and
/// IPC status frames stay within `MAX_FRAME_BYTES`.
const MAX_TRANSITION_HISTORY: usize = 64;

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
    transition_count: u64,
    transition_history: VecDeque<(SystemOperationalState, SystemOperationalState)>,
}

impl ConstitutionKernel {
    pub fn new(params: RiskParameters) -> Self {
        Self {
            state: SystemOperationalState::Normal,
            params,
            proposal_count: 0,
            emergency_count: 0,
            transition_count: 0,
            transition_history: VecDeque::new(),
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

    pub fn transition_count(&self) -> u64 {
        self.transition_count
    }

    pub fn transition_history(
        &self,
    ) -> &VecDeque<(SystemOperationalState, SystemOperationalState)> {
        &self.transition_history
    }

    fn record_transition(&mut self, from: SystemOperationalState, to: SystemOperationalState) {
        self.transition_count = self.transition_count.saturating_add(1);
        self.transition_history.push_back((from, to));
        while self.transition_history.len() > MAX_TRANSITION_HISTORY {
            self.transition_history.pop_front();
        }
    }

    fn enter_emergency(&mut self) {
        self.emergency_count = self.emergency_count.saturating_add(1);
        let from = self.state;
        self.state = SystemOperationalState::EmergencyHalt;
        if from != SystemOperationalState::EmergencyHalt {
            self.record_transition(from, SystemOperationalState::EmergencyHalt);
        }
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
                self.enter_emergency();
                ConstitutionVerdict::EmergencyLiquidationAll
            }
            ConstitutionVerdict::Rejected { ref reason_code } => {
                if *reason_code == RiskViolationCode::MaxDrawdownBreached {
                    self.enter_emergency();
                    ConstitutionVerdict::EmergencyLiquidationAll
                } else {
                    verdict
                }
            }
            ConstitutionVerdict::Approved { .. } => {
                if portfolio.high_water_mark > 0.0 {
                    let drawdown = (portfolio.high_water_mark - portfolio.total_equity)
                        / portfolio.high_water_mark;
                    match self.state {
                        SystemOperationalState::SoftDeleveraging => {
                            if drawdown < (self.params.max_drawdown_threshold * 0.80) {
                                self.record_transition(
                                    SystemOperationalState::SoftDeleveraging,
                                    SystemOperationalState::Normal,
                                );
                                self.state = SystemOperationalState::Normal;
                            }
                        }
                        SystemOperationalState::Normal => {
                            if drawdown >= (self.params.max_drawdown_threshold * 0.80) {
                                self.record_transition(
                                    SystemOperationalState::Normal,
                                    SystemOperationalState::SoftDeleveraging,
                                );
                                self.state = SystemOperationalState::SoftDeleveraging;
                            }
                        }
                        SystemOperationalState::EmergencyHalt
                        | SystemOperationalState::AutonomousRecovery => {}
                    }
                }
                verdict
            }
        }
    }

    /// Two-phase cryptographic recovery, per PRD FSM:
    ///   EmergencyHalt  --(valid proof)-->  AutonomousRecovery  --(valid proof)-->  Normal.
    /// A single valid proof advances one phase. Invalid proofs never advance the FSM
    /// (fail-safe default: unknown/invalid state stays halted).
    pub fn attempt_recovery(&mut self, cryptographic_proof_valid: bool) -> bool {
        if !cryptographic_proof_valid {
            return false;
        }
        match self.state {
            SystemOperationalState::EmergencyHalt => {
                self.record_transition(
                    SystemOperationalState::EmergencyHalt,
                    SystemOperationalState::AutonomousRecovery,
                );
                self.state = SystemOperationalState::AutonomousRecovery;
                true
            }
            SystemOperationalState::AutonomousRecovery => {
                self.record_transition(
                    SystemOperationalState::AutonomousRecovery,
                    SystemOperationalState::Normal,
                );
                self.state = SystemOperationalState::Normal;
                true
            }
            _ => false,
        }
    }

    pub fn params(&self) -> &RiskParameters {
        &self.params
    }
}

#[cfg(kani)]
mod verification {
    use super::*;
    use crate::{PortfolioState, Position, TradeProposal};

    #[kani::proof]
    fn verify_process_proposal_no_panic() {
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
        let mut kernel = ConstitutionKernel::new(params);
        let _ = kernel.process_proposal(&state, &proposal);
    }

    #[kani::proof]
    fn verify_attempt_recovery_no_panic() {
        let params: RiskParameters = kani::any();
        let mut kernel = ConstitutionKernel::new(params);
        let proof: bool = kani::any();
        for _ in 0..4 {
            let _ = kernel.attempt_recovery(proof);
        }
    }
}

/// Regression: the proptest fuzzer found that infinite/NaN equity bypassed the
/// validation guard and produced `Approved { adjusted_notional: inf }`,
/// violating Invariant D (numerical validity). This test pins the fix.
#[cfg(test)]
mod infinity_regression {
    use super::*;
    use crate::{OrderDirection, Position, TradeProposal};

    fn state(equity: f64, hwm: f64) -> PortfolioState {
        PortfolioState {
            timestamp: 1,
            total_equity: equity,
            cash_balance: equity,
            high_water_mark: hwm,
            open_positions: Vec::<Position>::new(),
        }
    }

    #[test]
    fn infinite_equity_rejected() {
        let kernel = ConstitutionKernel::new(RiskParameters::default());
        let _ = kernel;
        let verdict = crate::invariants::evaluate_proposal(
            &state(f64::INFINITY, 1_000_000.0),
            &TradeProposal {
                proposal_id: "inf".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: 100.0,
                max_acceptable_slippage: 0.001,
            },
            &RiskParameters::default(),
        );
        assert!(matches!(
            verdict,
            ConstitutionVerdict::Rejected {
                reason_code: RiskViolationCode::InvalidNumericalState,
            }
        ));
    }

    #[test]
    fn nan_equity_rejected() {
        let verdict = crate::invariants::evaluate_proposal(
            &state(f64::NAN, 1_000_000.0),
            &TradeProposal {
                proposal_id: "nan".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: 100.0,
                max_acceptable_slippage: 0.001,
            },
            &RiskParameters::default(),
        );
        assert!(matches!(
            verdict,
            ConstitutionVerdict::Rejected {
                reason_code: RiskViolationCode::InvalidNumericalState,
            }
        ));
    }

    #[test]
    fn infinite_notional_rejected() {
        let verdict = crate::invariants::evaluate_proposal(
            &state(1_000_000.0, 1_000_000.0),
            &TradeProposal {
                proposal_id: "inf-n".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: f64::INFINITY,
                max_acceptable_slippage: 0.001,
            },
            &RiskParameters::default(),
        );
        assert!(matches!(
            verdict,
            ConstitutionVerdict::Rejected {
                reason_code: RiskViolationCode::InvalidNumericalState,
            }
        ));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{OrderDirection, Position, TradeProposal};

    fn state(equity: f64, hwm: f64) -> PortfolioState {
        PortfolioState {
            timestamp: 1,
            total_equity: equity,
            cash_balance: equity,
            high_water_mark: hwm,
            open_positions: Vec::<Position>::new(),
        }
    }

    fn proposal(notional: f64) -> TradeProposal {
        TradeProposal {
            proposal_id: "t".to_string(),
            asset_id: "BTC-PERP".to_string(),
            direction: OrderDirection::Buy,
            target_notional: notional,
            max_acceptable_slippage: 0.001,
        }
    }

    #[test]
    fn fresh_kernel_is_normal() {
        let kernel = ConstitutionKernel::new(RiskParameters::default());
        assert_eq!(kernel.current_state(), SystemOperationalState::Normal);
        assert_eq!(kernel.proposal_count(), 0);
        assert_eq!(kernel.emergency_count(), 0);
    }

    #[test]
    fn approved_proposal_enters_soft_deleveraging_near_threshold() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        // drawdown = (1_000_000 - 880_000) / 1_000_000 = 0.12 >= 0.15 * 0.80
        let verdict = kernel.process_proposal(&state(880_000.0, 1_000_000.0), &proposal(10_000.0));
        assert!(matches!(verdict, ConstitutionVerdict::Approved { .. }));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::SoftDeleveraging
        );
    }

    #[test]
    fn drawdown_breach_triggers_emergency_halt() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        // drawdown = 0.3 >= 0.15 threshold -> EmergencyLiquidationAll
        let verdict = kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        assert_eq!(verdict, ConstitutionVerdict::EmergencyLiquidationAll);
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::EmergencyHalt
        );
        assert_eq!(kernel.emergency_count(), 1);
    }

    #[test]
    fn proposals_rejected_while_emergency_halt() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::EmergencyHalt
        );
        let verdict = kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        assert!(matches!(verdict, ConstitutionVerdict::Rejected { .. }));
    }

    #[test]
    fn recovery_is_two_phase_through_autonomous_recovery() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::EmergencyHalt
        );

        // Phase 1: EmergencyHalt -> AutonomousRecovery
        assert!(kernel.attempt_recovery(true));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::AutonomousRecovery
        );

        // Still halted for trading during diagnostic pass
        let verdict = kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        assert!(matches!(verdict, ConstitutionVerdict::Rejected { .. }));

        // Phase 2: AutonomousRecovery -> Normal
        assert!(kernel.attempt_recovery(true));
        assert_eq!(kernel.current_state(), SystemOperationalState::Normal);
        assert_eq!(kernel.transition_count(), 3); // Normal->Halt, Halt->Recovery, Recovery->Normal
    }

    #[test]
    fn invalid_proof_never_advances_fsm() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::EmergencyHalt
        );

        assert!(!kernel.attempt_recovery(false));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::EmergencyHalt
        );
        assert_eq!(kernel.transition_count(), 1);
    }

    #[test]
    fn soft_deleveraging_recovers_to_normal_on_low_drawdown() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        kernel.process_proposal(&state(880_000.0, 1_000_000.0), &proposal(10_000.0));
        assert_eq!(
            kernel.current_state(),
            SystemOperationalState::SoftDeleveraging
        );

        // drawdown = 0.05 < 0.12 (80% of threshold) -> back to Normal
        kernel.process_proposal(&state(950_000.0, 1_000_000.0), &proposal(10_000.0));
        assert_eq!(kernel.current_state(), SystemOperationalState::Normal);
    }

    #[test]
    fn transition_history_records_all_transitions() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
        kernel.attempt_recovery(true);
        kernel.attempt_recovery(true);
        let history = kernel.transition_history();
        assert_eq!(history.len(), 3);
        assert_eq!(
            *history.front().unwrap(),
            (
                SystemOperationalState::Normal,
                SystemOperationalState::EmergencyHalt,
            )
        );
        assert_eq!(
            *history.get(1).unwrap(),
            (
                SystemOperationalState::EmergencyHalt,
                SystemOperationalState::AutonomousRecovery,
            )
        );
        assert_eq!(
            *history.get(2).unwrap(),
            (
                SystemOperationalState::AutonomousRecovery,
                SystemOperationalState::Normal,
            )
        );
    }

    #[test]
    fn transition_history_is_bounded() {
        let mut kernel = ConstitutionKernel::new(RiskParameters::default());
        for _ in 0..(MAX_TRANSITION_HISTORY * 2) {
            kernel.process_proposal(&state(700_000.0, 1_000_000.0), &proposal(10_000.0));
            kernel.attempt_recovery(true);
            kernel.attempt_recovery(true);
        }
        assert_eq!(kernel.transition_history().len(), MAX_TRANSITION_HISTORY);
        assert_eq!(
            kernel.transition_count(),
            (MAX_TRANSITION_HISTORY * 2) as u64 * 3
        );
        // Oldest entry was evicted; the newest is the final Recovery->Normal.
        assert_eq!(
            *kernel.transition_history().back().unwrap(),
            (
                SystemOperationalState::AutonomousRecovery,
                SystemOperationalState::Normal,
            )
        );
    }
}

#[cfg(test)]
mod proptests {
    use super::*;
    use crate::{OrderDirection, Position, TradeProposal};
    use proptest::prelude::*;

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
        (any::<String>(), arb_f64(), arb_f64()).prop_map(|(id, val, price)| Position {
            asset_id: id,
            notional_value: val,
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
            .prop_map(|(id, asset, dir, notional, slip)| TradeProposal {
                proposal_id: id,
                asset_id: asset,
                direction: dir,
                target_notional: notional,
                max_acceptable_slippage: slip,
            })
    }

    // P5: process_proposal never panics on any input
    proptest! {
        #[test]
        fn prop_process_proposal_never_panics(
            state in arb_state(),
            proposal in arb_proposal(),
        ) {
            let mut kernel = ConstitutionKernel::new(RiskParameters::default());
            // proptest catches any panic as a test failure
            kernel.process_proposal(&state, &proposal);
        }
    }

    // P6: invalid recovery proofs never advance the FSM from EmergencyHalt
    proptest! {
        #[test]
        fn prop_invalid_proof_keeps_emergency_halt(
            proof in any::<bool>(),
        ) {
            let mut kernel = ConstitutionKernel::new(RiskParameters::default());
            let state = PortfolioState {
                timestamp: 1,
                total_equity: 700_000.0,
                cash_balance: 700_000.0,
                high_water_mark: 1_000_000.0,
                open_positions: Vec::new(),
            };
            let prop = TradeProposal {
                proposal_id: "emerg".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: 10_000.0,
                max_acceptable_slippage: 0.001,
            };
            // Force EmergencyHalt via drawdown breach
            kernel.process_proposal(&state, &prop);
            assert_eq!(kernel.current_state(), SystemOperationalState::EmergencyHalt);

            // Invalid proof must not advance
            let advanced = kernel.attempt_recovery(proof);
            if !proof {
                assert!(!advanced, "invalid proof must not advance FSM");
                assert_eq!(
                    kernel.current_state(),
                    SystemOperationalState::EmergencyHalt,
                    "state must remain EmergencyHalt after invalid proof"
                );
            }
        }
    }

    // P7: valid recovery follows the exact two-phase path (no skipping)
    proptest! {
        #[test]
        fn prop_recovery_is_two_phase(
            _ in any::<()>(),
        ) {
            let mut kernel = ConstitutionKernel::new(RiskParameters::default());

            // Drive into EmergencyHalt via drawdown breach
            let state = PortfolioState {
                timestamp: 1,
                total_equity: 500_000.0,
                cash_balance: 500_000.0,
                high_water_mark: 1_000_000.0,
                open_positions: Vec::new(),
            };
            let prop = TradeProposal {
                proposal_id: "halt".to_string(),
                asset_id: "BTC".to_string(),
                direction: OrderDirection::Buy,
                target_notional: 10_000.0,
                max_acceptable_slippage: 0.001,
            };
            kernel.process_proposal(&state, &prop);
            assert_eq!(kernel.current_state(), SystemOperationalState::EmergencyHalt);

            // Phase 1: EmergencyHalt → AutonomousRecovery
            assert!(kernel.attempt_recovery(true));
            assert_eq!(kernel.current_state(), SystemOperationalState::AutonomousRecovery);
            // Must NOT skip to Normal
            assert_ne!(kernel.current_state(), SystemOperationalState::Normal);

            // Phase 2: AutonomousRecovery → Normal
            assert!(kernel.attempt_recovery(true));
            assert_eq!(kernel.current_state(), SystemOperationalState::Normal);
        }
    }
}
