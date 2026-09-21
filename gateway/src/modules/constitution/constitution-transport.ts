import {
  ConstitutionVerdict,
  PortfolioState,
  TradeProposal,
} from './rust-bridge.service';

export interface ConstitutionStatus {
  system_state: string;
  proposals_seen: number;
  emergencies: number;
  transitions: number;
  state_history: Array<[string, string]>;
}

export interface EvaluateResult {
  verdict: ConstitutionVerdict;
  system_state: string;
}

export interface HeartbeatResult {
  alive: boolean;
  protocol_version: number;
}

export const CONSTITUTION_TRANSPORT = Symbol('CONSTITUTION_TRANSPORT');

/**
 * Pluggable transport to the Iron Constitution (G3-style abstraction, scoped to
 * the gateway). Implementations talk to the TCP daemon (`constitutiond`) or to
 * the single-shot CLI bridge (`constitution_cli`); the module selects the
 * transport via the `CONSTITUTION_BRIDGE` env var (`tcp` | `cli`).
 */
export interface ConstitutionTransport {
  evaluateProposal(
    portfolio: PortfolioState,
    proposal: TradeProposal,
  ): Promise<EvaluateResult>;
  getStatus(): Promise<ConstitutionStatus>;
  heartbeat(): Promise<HeartbeatResult>;
}