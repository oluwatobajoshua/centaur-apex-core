import { Injectable, Logger } from '@nestjs/common';
import { execFile } from 'child_process';
import * as path from 'path';
import { promisify } from 'util';
import {
  ConstitutionTransport,
  ConstitutionStatus,
  EvaluateResult,
  HeartbeatResult,
} from './constitution-transport';
import { PortfolioState, TradeProposal } from './rust-bridge.service';

const execFileAsync = promisify(execFile);

export interface CliRunResult {
  stdout: string;
  stderr: string;
}

/** Injectable command runner so unit/e2e tests can stub the subprocess. */
@Injectable()
export class CliRunner {
  async run(bin: string, arg: string): Promise<CliRunResult> {
    const { stdout, stderr } = await execFileAsync(bin, [arg], {
      timeout: this.timeoutMs(),
      windowsHide: true,
      maxBuffer: 64 * 1024,
    });
    return { stdout, stderr };
  }

  private timeoutMs(): number {
    return Number(process.env.CONSTITUTION_TIMEOUT_MS ?? 5000);
  }
}

/**
 * Resolves the `constitution_cli` binary. Priority:
 * 1. `CONSTITUTION_CLI_PATH` env var (absolute path).
 * 2. `CONSTITUTION_CLI` on PATH.
 * 3. The local cargo target binaries (debug then release) relative to repo root.
 */
export function resolveCliPath(): string {
  const fromEnv = process.env.CONSTITUTION_CLI_PATH;
  if (fromEnv) {
    return fromEnv;
  }
  const exe = process.platform === 'win32' ? 'constitution_cli.exe' : 'constitution_cli';
  const repoRoot = path.resolve(__dirname, '..', '..', '..', '..');
  const candidates = [
    path.join(repoRoot, 'constitution', 'target', 'debug', exe),
    path.join(repoRoot, 'constitution', 'target', 'release', exe),
  ];
  for (const candidate of candidates) {
    // Resolves up to PATH too if the file exists next to the repo.
    if (candidate) {
      return candidate;
    }
  }
  return exe;
}

const PROTOCOL_VERSION = 1;

@Injectable()
export class CliBridgeService implements ConstitutionTransport {
  private readonly logger = new Logger(CliBridgeService.name);
  private readonly bin: string;

  constructor(private readonly runner: CliRunner = new CliRunner()) {
    this.bin = resolveCliPath();
    this.logger.log(`Rust bridge running constitution_cli at ${this.bin}`);
  }

  async evaluateProposal(
    portfolio: PortfolioState,
    proposal: TradeProposal,
  ): Promise<EvaluateResult> {
    const payload = JSON.stringify({ portfolio, proposal });
    const raw = await this.call('EvaluateProposal', payload);
    return JSON.parse(raw) as EvaluateResult;
  }

  async getStatus(): Promise<ConstitutionStatus> {
    const raw = await this.call('GetStatus', '{}');
    return JSON.parse(raw) as ConstitutionStatus;
  }

  async heartbeat(): Promise<HeartbeatResult> {
    const raw = await this.call('Heartbeat', '{}');
    const parsed = JSON.parse(raw) as HeartbeatResult;
    if (!parsed.alive) {
      throw new Error('constitution_cli reported not alive');
    }
    return parsed;
  }

  /** Envelope -> one-shot CLI invocation -> parsed response line. */
  private async call(opcode: string, payload: string): Promise<string> {
    const envelope = {
      protocol_version: PROTOCOL_VERSION,
      request_id: 'gateway-0001',
      opcode,
      payload,
    };
    const { stdout, stderr } = await this.runner.run(this.bin, JSON.stringify(envelope));
    const trimmed = stdout.trim();
    if (!trimmed) {
      this.logger.error(`constitution_cli produced no stdout: ${stderr}`);
      throw new Error(`constitution_cli invocation failed: ${stderr}`);
    }
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    if (parsed.error) {
      throw new Error(`constitution_cli error: ${String(parsed.error)}`);
    }
    return trimmed;
  }
}