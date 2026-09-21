import { CortexCliRunner, CortexService } from './cortex.service';

describe('CortexService (real proposal emission)', () => {
  let runner: { run: jest.Mock };
  let service: CortexService;

  beforeEach(() => {
    runner = { run: jest.fn() };
    service = new CortexService(runner as unknown as CortexCliRunner);
  });

  it('invokes the python engine and parses a generated proposal', async () => {
    runner.run.mockResolvedValue({
      stdout: JSON.stringify({
        status: 'ProposalGenerated',
        timestamp: 123,
        proposal: {
          proposal_id: 'uuid-1',
          asset_id: 'SYNTH-PERP',
          direction: 'Buy',
          target_notional: 50_000,
          max_acceptable_slippage: 0.0015,
        },
      }),
      stderr: '',
    });

    const result = await service.emitProposal({
      assetId: 'SYNTH-PERP',
      price: 100,
      equity: 1_000_000,
      trend: 'bullish',
      momentum: true,
    });

    expect(runner.run).toHaveBeenCalledTimes(1);
    const args = runner.run.mock.calls[0][0];
    expect(args.slice(0, 2)).toEqual(['-m', 'cortex.engine']);
    expect(args).toContain('--asset');
    expect(args).toContain('--trend');
    expect(args[args.indexOf('--momentum') + 1]).toBe('1');
    expect(result.status).toBe('ProposalGenerated');
    expect(result.proposal?.target_notional).toBe(50_000);
  });

  it('propagates NoAction when the engine declines to trade', async () => {
    runner.run.mockResolvedValue({ stdout: JSON.stringify({ status: 'NoAction', proposal: null }), stderr: '' });
    const result = await service.emitProposal({
      assetId: 'SYNTH-PERP', price: 50, equity: 1_000, trend: 'neutral', momentum: false,
    });
    expect(result.status).toBe('NoAction');
    expect(result.proposal).toBeUndefined();
  });

  it('throws when the engine emits no stdout', async () => {
    runner.run.mockResolvedValue({ stdout: '', stderr: 'traceback' });
    await expect(
      service.emitProposal({ assetId: 'X', price: 1, equity: 1, trend: 'bullish', momentum: true }),
    ).rejects.toThrow(/traceback/);
  });
});