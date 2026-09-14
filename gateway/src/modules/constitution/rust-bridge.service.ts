import { Injectable, Logger } from '@nestjs/common';
import * as net from 'net';

export interface Position {
  asset_id: string;
  notional_value: number;
  entry_price: number;
}

export interface PortfolioState {
  timestamp: number;
  total_equity: number;
  cash_balance: number;
  high_water_mark: number;
  open_positions: Position[];
}

export interface TradeProposal {
  proposal_id: string;
  asset_id: string;
  direction: 'Buy' | 'Sell';
  target_notional: number;
  max_acceptable_slippage: number;
}

export type ConstitutionVerdict =
  | { Approved: { adjusted_notional: number } }
  | { Rejected: { reason_code: string } }
  | 'EmergencyLiquidationAll';

interface IpcEnvelope {
  protocol_version: number;
  request_id: string;
  opcode: string;
  payload: string;
}

const PROTOCOL_VERSION = 1;
const MAX_FRAME_BYTES = 16_384;

@Injectable()
export class RustBridgeService {
  private readonly logger = new Logger(RustBridgeService.name);
  private readonly host: string;
  private readonly port: number;
  private readonly timeoutMs: number;

  constructor() {
    this.host = process.env.CONSTITUTION_HOST ?? '127.0.0.1';
    this.port = Number(process.env.CONSTITUTION_PORT ?? 15565);
    this.timeoutMs = Number(process.env.CONSTITUTION_TIMEOUT_MS ?? 5000);
    this.logger.log(`Rust bridge targeting constitutiond at ${this.host}:${this.port}`);
  }

  async evaluateProposal(
    portfolio: PortfolioState,
    proposal: TradeProposal,
  ): Promise<{ verdict: ConstitutionVerdict; system_state: string }> {
    const payload = JSON.stringify({ portfolio, proposal });
    const raw = await this.rpc('EvaluateProposal', payload);
    return JSON.parse(raw) as { verdict: ConstitutionVerdict; system_state: string };
  }

  async getStatus(): Promise<{
    system_state: string;
    proposals_seen: number;
    emergencies: number;
  }> {
    const raw = await this.rpc('GetStatus', '{}');
    return JSON.parse(raw) as {
      system_state: string;
      proposals_seen: number;
      emergencies: number;
    };
  }

  async heartbeat(): Promise<{ alive: boolean; protocol_version: number }> {
    const raw = await this.rpc('Heartbeat', '{}');
    return JSON.parse(raw) as { alive: boolean; protocol_version: number };
  }

  /** Length-prefixed TCP framing exchange with the Rust daemon. */
  private rpc(opcode: string, payload: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const envelope: IpcEnvelope = {
        protocol_version: PROTOCOL_VERSION,
        request_id: 'gateway-0001',
        opcode,
        payload,
      };
      const frame = Buffer.from(JSON.stringify(envelope), 'utf-8');

      if (frame.length > MAX_FRAME_BYTES) {
        reject(new Error('Frame exceeds MAX_FRAME_BYTES'));
        return;
      }

      const socket = new net.Socket();
      const timer = setTimeout(() => {
        socket.destroy();
        reject(new Error('constitutiond RPC timed out'));
      }, this.timeoutMs);

      socket.setTimeout(this.timeoutMs);
      socket.on('timeout', () => {
        socket.destroy();
        reject(new Error('constitutiond socket timeout'));
      });

      socket.connect(this.port, this.host, () => {
        const header = Buffer.alloc(4);
        header.writeUInt32BE(frame.length, 0);
        socket.write(Buffer.concat([header, frame]));
      });

      const chunks: Buffer[] = [];
      let responseLength: number | null = null;

      socket.on('data', (data: Buffer) => {
        chunks.push(data);
        if (responseLength === null && chunks[0] && chunks[0].length >= 4) {
          responseLength = chunks.reduce((a, c) => a + c.length, 0) >= 4
            ? chunks[0].readUInt32BE(0)
            : null;
        }
        const total = chunks.reduce((a, c) => a + c.length, 0);
        if (responseLength !== null && total >= responseLength + 4) {
          const body = Buffer.concat(chunks).subarray(4, 4 + responseLength);
          clearTimeout(timer);
          socket.destroy();
          resolve(body.toString('utf-8'));
        }
      });

      socket.on('error', (err: Error) => {
        clearTimeout(timer);
        reject(err);
      });
    });
  }
}