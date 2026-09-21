import { Injectable, Logger } from '@nestjs/common';
import * as net from 'net';
import {
  ConstitutionTransport,
  ConstitutionStatus,
  EvaluateResult,
  HeartbeatResult,
} from './constitution-transport';

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

/** Injectable socket factory so unit tests can substitute fake sockets. */
@Injectable()
export class SocketFactory {
  private impl: () => net.Socket = () => new net.Socket();
  setImplementation(impl: () => net.Socket): void {
    this.impl = impl;
  }
  create(): net.Socket {
    return this.impl();
  }
}

@Injectable()
export class RustBridgeService implements ConstitutionTransport {
  private readonly logger = new Logger(RustBridgeService.name);
  private readonly host: string;
  private readonly port: number;
  private readonly timeoutMs: number;

  constructor(private readonly socketFactory: SocketFactory = new SocketFactory()) {
    this.host = process.env.CONSTITUTION_HOST ?? '127.0.0.1';
    this.port = Number(process.env.CONSTITUTION_PORT ?? 15565);
    this.timeoutMs = Number(process.env.CONSTITUTION_TIMEOUT_MS ?? 5000);
    this.logger.log(`Rust bridge targeting constitutiond at ${this.host}:${this.port}`);
  }

  async evaluateProposal(
    portfolio: PortfolioState,
    proposal: TradeProposal,
  ): Promise<EvaluateResult> {
    const payload = JSON.stringify({ portfolio, proposal });
    const raw = await this.rpc('EvaluateProposal', payload);
    return JSON.parse(raw) as EvaluateResult;
  }

  async getStatus(): Promise<ConstitutionStatus> {
    const raw = await this.rpc('GetStatus', '{}');
    return JSON.parse(raw) as ConstitutionStatus;
  }

  async heartbeat(): Promise<HeartbeatResult> {
    const raw = await this.rpc('Heartbeat', '{}');
    const parsed = JSON.parse(raw) as HeartbeatResult;
    if (!parsed.alive) {
      throw new Error('constitution daemon reported not alive');
    }
    return parsed;
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

      const socket = this.socketFactory.create();
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
        if (responseLength === null && chunks.reduce((a, c) => a + c.length, 0) >= 4) {
          responseLength = chunks[0].readUInt32BE(0);
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