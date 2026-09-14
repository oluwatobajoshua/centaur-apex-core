use crate::{ConstitutionService, ConstitutionVerdict, PortfolioState, TradeProposal};
use serde::{Deserialize, Serialize};

pub const IPC_PROTOCOL_VERSION: u32 = 1;
pub const MAX_FRAME_BYTES: usize = 16_384;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum IpcOpcode {
    EvaluateProposal,
    GetStatus,
    AttemptRecovery,
    Heartbeat,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct IpcEnvelope {
    pub protocol_version: u32,
    pub request_id: String,
    pub opcode: IpcOpcode,
    pub payload: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct EvaluateProposalRequest {
    pub portfolio: PortfolioState,
    pub proposal: TradeProposal,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct EvaluateProposalResponse {
    pub verdict: ConstitutionVerdict,
    pub system_state: String,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct AttemptRecoveryRequest {
    pub cryptographic_proof_valid: bool,
}

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct HeartbeatResponse {
    pub alive: bool,
    pub protocol_version: u32,
}

pub struct IpcServer {
    constitution: ConstitutionService,
}

impl IpcServer {
    pub fn new(constitution: ConstitutionService) -> Self {
        Self { constitution }
    }

    pub fn handle_frame(&mut self, raw_frame: &[u8]) -> Result<String, IpcError> {
        if raw_frame.len() > MAX_FRAME_BYTES {
            return Err(IpcError::FrameSizeExceeded);
        }

        let envelope: IpcEnvelope =
            serde_json::from_slice(raw_frame).map_err(|_| IpcError::MalformedEnvelope)?;

        if envelope.protocol_version != IPC_PROTOCOL_VERSION {
            return Err(IpcError::VersionMismatch {
                expected: IPC_PROTOCOL_VERSION,
                actual: envelope.protocol_version,
            });
        }

        match envelope.opcode {
            IpcOpcode::EvaluateProposal => {
                let req: EvaluateProposalRequest =
                    serde_json::from_str(&envelope.payload).map_err(|_| IpcError::MalformedPayload)?;
                let verdict = self
                    .constitution
                    .handle_incoming_request(&req.portfolio, &req.proposal);
                let response = EvaluateProposalResponse {
                    verdict,
                    system_state: format!("{:?}", self.constitution.get_status()),
                };
                Ok(serde_json::to_string(&response).map_err(|_| IpcError::SerializationFailed)?)
            }
            IpcOpcode::GetStatus => {
                let response = serde_json::json!({
                    "system_state": format!("{:?}", self.constitution.get_status()),
                    "proposals_seen": self.constitution.proposal_counter(),
                    "emergencies": self.constitution.emergency_counter(),
                });
                Ok(serde_json::to_string(&response).map_err(|_| IpcError::SerializationFailed)?)
            }
            IpcOpcode::AttemptRecovery => {
                let req: AttemptRecoveryRequest = serde_json::from_str(&envelope.payload)
                    .map_err(|_| IpcError::MalformedPayload)?;
                let success = self
                    .constitution
                    .attempt_cryptographic_recovery(req.cryptographic_proof_valid);
                Ok(serde_json::json!({ "recovery_success": success }).to_string())
            }
            IpcOpcode::Heartbeat => {
                let response = HeartbeatResponse {
                    alive: true,
                    protocol_version: IPC_PROTOCOL_VERSION,
                };
                Ok(serde_json::to_string(&response).map_err(|_| IpcError::SerializationFailed)?)
            }
        }
    }

    pub fn constitution_mut(&mut self) -> &mut ConstitutionService {
        &mut self.constitution
    }
}

#[derive(Debug, Clone)]
pub enum IpcError {
    FrameSizeExceeded,
    MalformedEnvelope,
    MalformedPayload,
    SerializationFailed,
    VersionMismatch { expected: u32, actual: u32 },
}

impl std::fmt::Display for IpcError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:?}", self)
    }
}

impl std::error::Error for IpcError {}

#[cfg(kani)]
#[kani::proof]
fn verify_ipc_no_panic() {
    let frame: [u8; 128] = kani::any();
    let service = ConstitutionService::new(crate::invariants::RiskParameters::default());
    let mut server = IpcServer::new(service);
    let _ = server.handle_frame(&frame);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{ConstitutionService, OrderDirection, Position, TradeProposal};
    use crate::invariants::RiskParameters;

    fn state(equity: f64) -> PortfolioState {
        PortfolioState {
            timestamp: 1,
            total_equity: equity,
            cash_balance: equity,
            high_water_mark: 1_000_000.0,
            open_positions: Vec::<Position>::new(),
        }
    }

    fn proposal(notional: f64) -> TradeProposal {
        TradeProposal {
            proposal_id: "test-1".to_string(),
            asset_id: "BTC-PERP".to_string(),
            direction: OrderDirection::Buy,
            target_notional: notional,
            max_acceptable_slippage: 0.001,
        }
    }

    fn envelope(opcode: IpcOpcode, payload: String) -> String {
        let env = IpcEnvelope {
            protocol_version: IPC_PROTOCOL_VERSION,
            request_id: "req-1".to_string(),
            opcode,
            payload,
        };
        serde_json::to_string(&env).unwrap()
    }

    #[test]
    fn heartbeat_roundtrip() {
        let mut server = IpcServer::new(ConstitutionService::new(RiskParameters::default()));
        let raw = envelope(IpcOpcode::Heartbeat, "{}".to_string());
        let resp = server.handle_frame(raw.as_bytes()).unwrap();
        let parsed: HeartbeatResponse = serde_json::from_str(&resp).unwrap();
        assert!(parsed.alive);
        assert_eq!(parsed.protocol_version, 1);
    }

    #[test]
    fn evaluate_approved_proposal() {
        let mut server = IpcServer::new(ConstitutionService::new(RiskParameters::default()));
        let req = EvaluateProposalRequest {
            portfolio: state(1_000_000.0),
            proposal: proposal(50_000.0),
        };
        let raw = envelope(
            IpcOpcode::EvaluateProposal,
            serde_json::to_string(&req).unwrap(),
        );
        let resp = server.handle_frame(raw.as_bytes()).unwrap();
        let parsed: EvaluateProposalResponse = serde_json::from_str(&resp).unwrap();
        assert!(matches!(parsed.verdict, ConstitutionVerdict::Approved { .. }));
    }

    #[test]
    fn evaluate_rejected_on_high_leverage() {
        let mut server = IpcServer::new(ConstitutionService::new(RiskParameters::default()));
        let req = EvaluateProposalRequest {
            portfolio: state(1_000_000.0),
            proposal: proposal(4_000_000.0),
        };
        let raw = envelope(
            IpcOpcode::EvaluateProposal,
            serde_json::to_string(&req).unwrap(),
        );
        let resp = server.handle_frame(raw.as_bytes()).unwrap();
        let parsed: EvaluateProposalResponse = serde_json::from_str(&resp).unwrap();
        assert!(matches!(
            parsed.verdict,
            ConstitutionVerdict::Rejected { .. }
        ));
    }

    #[test]
    fn version_mismatch_rejected() {
        let mut server = IpcServer::new(ConstitutionService::new(RiskParameters::default()));
        let mut env = IpcEnvelope {
            protocol_version: 99,
            request_id: "req-bad".to_string(),
            opcode: IpcOpcode::Heartbeat,
            payload: "{}".to_string(),
        };
        let raw = serde_json::to_string(&env).unwrap();
        env.protocol_version = IPC_PROTOCOL_VERSION;
        let result = server.handle_frame(raw.as_bytes());
        assert!(matches!(result, Err(IpcError::VersionMismatch { .. })));
    }

    #[test]
    fn oversized_frame_rejected() {
        let mut server = IpcServer::new(ConstitutionService::new(RiskParameters::default()));
        let big = vec![0u8; MAX_FRAME_BYTES + 1];
        let result = server.handle_frame(&big);
        assert!(matches!(result, Err(IpcError::FrameSizeExceeded)));
    }

    #[test]
    fn recovery_requires_cryptographic_proof() {
        let mut server = IpcServer::new(ConstitutionService::new(RiskParameters::default()));
        let req = AttemptRecoveryRequest {
            cryptographic_proof_valid: true,
        };
        let raw = envelope(
            IpcOpcode::AttemptRecovery,
            serde_json::to_string(&req).unwrap(),
        );
        let resp = server.handle_frame(raw.as_bytes()).unwrap();
        assert!(resp.contains("recovery_success"));
    }
}