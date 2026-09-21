import { CliBridgeService, CliRunner, resolveCliPath } from './cli-bridge.service';

describe('CliBridgeService (constitution_cli transport)', () => {
  const originalEnv = { ...process.env };
  afterEach(() => {
    process.env = { ...originalEnv };
  });

  function stubRunner(stdout: string, stderr = '') {
    return { run: jest.fn().mockResolvedValue({ stdout, stderr }) } as unknown as CliRunner;
  }

  it('resolves an explicit CONSTITUTION_CLI_PATH', () => {
    process.env.CONSTITUTION_CLI_PATH = 'C:\\custom\\constitution_cli.exe';
    expect(resolveCliPath()).toBe('C:\\custom\\constitution_cli.exe');
  });

  it('posts an EvaluateProposal envelope and parses the verdict line', async () => {
    const runner = stubRunner(
      JSON.stringify({ verdict: { Approved: { adjusted_notional: 2_500 } }, system_state: 'Normal' }),
    );
    const bridge = new CliBridgeService(runner);
    const result = await bridge.evaluateProposal(
      {
        timestamp: 1, total_equity: 1_000_000, cash_balance: 1_000_000,
        high_water_mark: 1_000_000, open_positions: [],
      },
      { proposal_id: 'p1', asset_id: 'BTC-PERP', direction: 'Buy', target_notional: 2_500, max_acceptable_slippage: 0.001 },
    );

    expect(runner.run).toHaveBeenCalledTimes(1);
    const [bin, envelopeJson] = (runner.run as jest.Mock).mock.calls[0];
    expect(bin).toBeTruthy();
    const envelope = JSON.parse(envelopeJson);
    expect(envelope.protocol_version).toBe(1);
    expect(envelope.opcode).toBe('EvaluateProposal');
    expect(JSON.parse(envelope.payload).proposal.proposal_id).toBe('p1');
    expect(result.verdict).toEqual({ Approved: { adjusted_notional: 2_500 } });
  });

  it('parses GetStatus including the transition journal', async () => {
    const runner = stubRunner(
      JSON.stringify({
        system_state: 'Normal', proposals_seen: 7, emergencies: 1,
        transitions: 3, state_history: [['EmergencyHalt', 'AutonomousRecovery']],
      }),
    );
    const bridge = new CliBridgeService(runner);
    const status = await bridge.getStatus();
    expect(status.transitions).toBe(3);
    expect(status.state_history).toEqual([['EmergencyHalt', 'AutonomousRecovery']]);
  });

  it('rejects non-alive heartbeats', async () => {
    const runner = stubRunner(JSON.stringify({ alive: false, protocol_version: 1 }));
    const bridge = new CliBridgeService(runner);
    await expect(bridge.heartbeat()).rejects.toThrow('reported not alive');
  });

  it('surfaces CLI stderr when stdout is empty', async () => {
    const runner = stubRunner('', 'boom');
    const bridge = new CliBridgeService(runner);
    await expect(bridge.getStatus()).rejects.toThrow(/boom/);
  });

  it('surfaces constitution error objects', async () => {
    const runner = stubRunner(JSON.stringify({ error: 'version_mismatch' }));
    const bridge = new CliBridgeService(runner);
    await expect(bridge.getStatus()).rejects.toThrow(/version_mismatch/);
  });
});