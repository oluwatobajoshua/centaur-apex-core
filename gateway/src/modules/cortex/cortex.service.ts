import { Injectable, Logger } from '@nestjs/common';
import { execFile } from 'child_process';
import * as path from 'path';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

export interface AnthropomorphicProposal {
  proposal_id: string;
  asset_id: string;
  direction: 'Buy' | 'Sell';
  target_notional: number;
  max_acceptable_slippage: number;
}

export interface CortexEmissionResult {
  status: 'ProposalGenerated' | 'NoAction';
  timestamp?: number;
  proposal?: AnthropomorphicProposal;
}

export interface CortexEmissionInput {
  assetId: string;
  price: number;
  equity: number;
  trend: 'bullish' | 'bearish' | 'neutral';
  momentum: boolean;
  volatility?: number;
}

export interface CortexCommandResult {
  stdout: string;
  stderr: string;
}

/** Injectable command runner so unit tests can stub the Python engine. */
@Injectable()
export class CortexCliRunner {
  async run(args: string[]): Promise<CortexCommandResult> {
    const { stdout, stderr } = await execFileAsync('python', args, {
      // Flat-import convention: the cortex package home is `cortex/` at repo
      // root; running `python -m cortex.engine` from that home resolves
      // `cortex.proposal_api` without PATH hacks.
      cwd: path.resolve(this.repoRoot(), 'cortex'),
      windowsHide: true,
      timeout: Number(process.env.CORTEX_ENGINE_TIMEOUT_MS ?? 10_000),
      maxBuffer: 64 * 1024,
    });
    return { stdout, stderr };
  }

  private repoRoot(): string {
    return path.resolve(__dirname, '..', '..', '..', '..');
  }
}

@Injectable()
export class CortexService {
  private readonly logger = new Logger(CortexService.name);

  constructor(private readonly runner: CortexCliRunner = new CortexCliRunner()) {}

  /**
   * Emits a proposal by invoking the real Cortex engine (`cortex.engine`,
   * S2 bootstrap stub) as a subprocess. The gateway holds zero strategy logic;
   * it only orchestrates the mechanisms that already exist (G8).
   */
  async emitProposal(input: CortexEmissionInput): Promise<CortexEmissionResult> {
    const args = [
      '-m',
      'cortex.engine',
      '--asset', input.assetId,
      '--price', String(input.price),
      '--equity', String(input.equity),
      '--trend', input.trend,
      '--momentum', input.momentum ? '1' : '0',
      '--volatility', String(input.volatility ?? 0.0),
    ];
    const { stdout, stderr } = await this.runner.run(args);
    const trimmed = stdout.trim();
    if (!trimmed) {
      this.logger.error(`cortex.engine produced no stdout: ${stderr}`);
      throw new Error(`cortex.engine failed: ${stderr}`);
    }
    const parsed = JSON.parse(trimmed) as CortexEmissionResult & { proposal?: AnthropomorphicProposal | null };
    return {
      status: parsed.status,
      timestamp: parsed.timestamp,
      proposal: parsed.proposal ?? undefined,
    };
  }

  /** Orchestration placeholder retained for forward-compatibility. */
  forward(): { status: 'orchestrated' } {
    return { status: 'orchestrated' };
  }
}