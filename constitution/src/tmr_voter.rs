use crate::{ConstitutionVerdict, RiskViolationCode};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TMRVerdict {
    pub unanimous: bool,
    pub majority_consistent: bool,
    pub divergent_replicas: u8,
}

pub struct TripleModularRedundancyVoter {
    reconcile_threshold: u8,
}

impl Default for TripleModularRedundancyVoter {
    fn default() -> Self {
        Self {
            reconcile_threshold: 2,
        }
    }
}

pub fn vote_on_verdicies(verdicts: &[ConstitutionVerdict; 3]) -> TMRVerdict {
    let all_identical = verdicts[0] == verdicts[1] && verdicts[1] == verdicts[2];

    let approved_votes = verdicts
        .iter()
        .filter(|v| matches!(v, ConstitutionVerdict::Approved { .. }))
        .count();
    let rejected_votes = verdicts
        .iter()
        .filter(|v| matches!(v, ConstitutionVerdict::Rejected { .. }))
        .count();
    let emergency_votes = verdicts
        .iter()
        .filter(|v| matches!(v, ConstitutionVerdict::EmergencyLiquidationAll))
        .count();

    let majority_consistent = approved_votes >= 2 || rejected_votes >= 2 || emergency_votes >= 2;

    let divergent = 3usize.saturating_sub(approved_votes.max(rejected_votes).max(emergency_votes));

    TMRVerdict {
        unanimous: all_identical,
        majority_consistent,
        divergent_replicas: divergent as u8,
    }
}

pub fn reconcile(
    verdicts: [ConstitutionVerdict; 3],
    voter: &TripleModularRedundancyVoter,
) -> ConstitutionVerdict {
    let ballot = vote_on_verdicies(&verdicts);

    if ballot.unanimous {
        return verdicts[0].clone();
    }

    if !ballot.majority_consistent {
        return ConstitutionVerdict::Rejected {
            reason_code: RiskViolationCode::InvalidNumericalState,
        };
    }

    let approved = verdicts
        .iter()
        .filter(|v| matches!(v, ConstitutionVerdict::Approved { .. }))
        .count();
    let rejected = verdicts
        .iter()
        .filter(|v| matches!(v, ConstitutionVerdict::Rejected { .. }))
        .count();
    let emergency = verdicts
        .iter()
        .filter(|v| matches!(v, ConstitutionVerdict::EmergencyLiquidationAll))
        .count();

    if approved >= voter.reconcile_threshold as usize {
        let minimum_adjusted = verdicts
            .iter()
            .filter_map(|v| match v {
                ConstitutionVerdict::Approved { adjusted_notional } => Some(*adjusted_notional),
                _ => None,
            })
            .fold(f64::INFINITY, f64::min);
        return ConstitutionVerdict::Approved {
            adjusted_notional: minimum_adjusted,
        };
    }

    if rejected >= voter.reconcile_threshold as usize {
        let reason = verdicts
            .iter()
            .find_map(|v| match v {
                ConstitutionVerdict::Rejected { reason_code } => Some(reason_code.clone()),
                _ => None,
            })
            .unwrap_or(RiskViolationCode::InvalidNumericalState);
        return ConstitutionVerdict::Rejected {
            reason_code: reason,
        };
    }

    if emergency >= voter.reconcile_threshold as usize {
        return ConstitutionVerdict::EmergencyLiquidationAll;
    }

    ConstitutionVerdict::Rejected {
        reason_code: RiskViolationCode::InvalidNumericalState,
    }
}

#[cfg(kani)]
#[kani::proof]
fn verify_voter_no_panic() {
    let a: ConstitutionVerdict = kani::any();
    let b: ConstitutionVerdict = kani::any();
    let c: ConstitutionVerdict = kani::any();
    let voter = TripleModularRedundancyVoter::default();
    let _ = reconcile([a, b, c], &voter);
}
