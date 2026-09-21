import { Test } from '@nestjs/testing';
import { CONSTITUTION_TRANSPORT, ConstitutionTransport } from './constitution-transport';
import { ConstitutionController } from './constitution.controller';

describe('ConstitutionController', () => {
  let controller: ConstitutionController;
  const transport = {
    getStatus: jest.fn(),
    evaluateProposal: jest.fn(),
    heartbeat: jest.fn(),
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    const moduleRef = await Test.createTestingModule({
      controllers: [ConstitutionController],
      providers: [{ provide: CONSTITUTION_TRANSPORT, useValue: transport }],
    }).compile();
    controller = moduleRef.get(ConstitutionController);
  });

  it('routes GET /constitution/status to the transport', async () => {
    transport.getStatus.mockResolvedValue({
      system_state: 'Normal',
      proposals_seen: 12,
      emergencies: 0,
      transitions: 4,
      state_history: [],
    });
    const result = await controller.status();
    expect(transport.getStatus).toHaveBeenCalledTimes(1);
    expect(result.system_state).toBe('Normal');
  });

  it('routes POST /constitution/evaluate with portfolio + proposal', async () => {
    transport.evaluateProposal.mockResolvedValue({
      verdict: { Approved: { adjusted_notional: 5_000 } },
      system_state: 'Normal',
    });
    const body = {
      portfolio: {
        timestamp: 1,
        total_equity: 1_000_000,
        cash_balance: 1_000_000,
        high_water_mark: 1_000_000,
        open_positions: [],
      },
      proposal: {
        proposal_id: 'p1',
        asset_id: 'BTC-PERP',
        direction: 'Buy',
        target_notional: 5_000,
        max_acceptable_slippage: 0.001,
      },
    };
    const result = await controller.evaluate(body as any);
    expect(transport.evaluateProposal).toHaveBeenCalledWith(body.portfolio, body.proposal);
    expect(result.verdict).toEqual({ Approved: { adjusted_notional: 5_000 } });
  });

  it('propagates transport errors to the caller', async () => {
    transport.getStatus.mockRejectedValue(new Error('constitutiond RPC timed out'));
    await expect(controller.status()).rejects.toThrow('constitutiond RPC timed out');
  });
});