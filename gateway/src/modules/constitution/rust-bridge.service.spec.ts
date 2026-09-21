import * as net from 'net';
import {
  RustBridgeService,
  SocketFactory,
  TradeProposal,
  PortfolioState,
} from './rust-bridge.service';

describe('RustBridgeService (TCP framing)', () => {
  let server: net.Server;
  let port = 0;
  const originalEnv = { ...process.env };

  const proposal: TradeProposal = {
    proposal_id: 't1',
    asset_id: 'BTC-PERP',
    direction: 'Buy',
    target_notional: 10_000,
    max_acceptable_slippage: 0.001,
  };

  const portfolio: PortfolioState = {
    timestamp: 1,
    total_equity: 1_000_000,
    cash_balance: 1_000_000,
    high_water_mark: 1_000_000,
    open_positions: [],
  };

  afterEach(() => {
    process.env = { ...originalEnv };
    if (server) {
      server.close();
    }
  });

  /** Boots a fake constitutiond that hands the exchange off to `handler`. */
  async function startFakeDaemon(
    handler: (socket: net.Socket, envelope: any) => void,
  ): Promise<void> {
    server = net.createServer((socket) => {
      const chunks: Buffer[] = [];
      let length: number | null = null;
      socket.on('data', (d: Buffer) => {
        chunks.push(d);
        const total = chunks.reduce((a, c) => a + c.length, 0);
        if (length === null && total >= 4) {
          length = Buffer.concat(chunks).readUInt32BE(0);
        }
        if (length !== null && total >= length + 4) {
          const frame = Buffer.concat(chunks).subarray(4, 4 + length).toString('utf-8');
          const envelope = JSON.parse(frame);
          handler(socket, envelope);
        }
      });
    });
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
    port = (server.address() as net.AddressInfo).port;
  }

  function writeResponse(socket: net.Socket, payload: unknown): void {
    const body = Buffer.from(JSON.stringify(payload), 'utf-8');
    const header = Buffer.alloc(4);
    header.writeUInt32BE(body.length, 0);
    socket.write(Buffer.concat([header, body]));
  }

  describe('envelope construction', () => {
    it('sends a length-prefixed, versioned JSON envelope for EvaluateProposal', async () => {
      let captured: any = null;
      await startFakeDaemon((socket, envelope) => {
        captured = envelope;
        writeResponse(socket, { verdict: { Approved: { adjusted_notional: 10_000 } }, system_state: 'Normal' });
      });
      process.env.CONSTITUTION_PORT = String(port);

      const bridge = new RustBridgeService();
      await bridge.evaluateProposal(portfolio, proposal);

      expect(captured).toBeDefined();
      expect(captured.protocol_version).toBe(1);
      expect(captured.opcode).toBe('EvaluateProposal');
      expect(JSON.parse(captured.payload).proposal.proposal_id).toBe('t1');
      expect(JSON.parse(captured.payload).portfolio.total_equity).toBe(1_000_000);
    });
  });

  describe('frame parsing', () => {
    it('parses a response split across multiple TCP chunks', async () => {
      await startFakeDaemon((socket) => {
        const body = Buffer.from(
          JSON.stringify({ system_state: 'Normal', proposals_seen: 3, emergencies: 0, transitions: 2, state_history: [['Normal', 'SoftDeleveraging']] }),
          'utf-8',
        );
        const header = Buffer.alloc(4);
        header.writeUInt32BE(body.length, 0);
        const parts = Buffer.concat([header, body]);
        // Deliver in arbitrary small slices to exercise the accumulate path.
        parts.forEach((byte: number, index: number) => {
          socket.write(Buffer.from([byte]));
        });
      });
      process.env.CONSTITUTION_PORT = String(port);

      const bridge = new RustBridgeService();
      const status = await bridge.getStatus();

      expect(status.system_state).toBe('Normal');
      expect(status.proposals_seen).toBe(3);
      expect(status.transitions).toBe(2);
      expect(status.state_history).toEqual([['Normal', 'SoftDeleveraging']]);
    });

    it('parses heartbeat responses', async () => {
      await startFakeDaemon((socket) => {
        writeResponse(socket, { alive: true, protocol_version: 1 });
      });
      process.env.CONSTITUTION_PORT = String(port);

      const bridge = new RustBridgeService();
      const heartbeat = await bridge.heartbeat();
      expect(heartbeat.alive).toBe(true);
    });

    it('rejects non-alive heartbeats', async () => {
      await startFakeDaemon((socket) => {
        writeResponse(socket, { alive: false, protocol_version: 1 });
      });
      process.env.CONSTITUTION_PORT = String(port);

      const bridge = new RustBridgeService();
      await expect(bridge.heartbeat()).rejects.toThrow('reported not alive');
    });
  });

  describe('timeout handling', () => {
    it('rejects when the daemon never responds', async () => {
      await startFakeDaemon(() => {
        /* accept and stay silent */
      });
      process.env.CONSTITUTION_PORT = String(port);
      process.env.CONSTITUTION_TIMEOUT_MS = '150';

      const bridge = new RustBridgeService();
      await expect(bridge.getStatus()).rejects.toThrow(/timed out|timeout/i);
    });

    it('rejects frames that exceed the protocol max', async () => {
      const big = 'x'.repeat(16_385);
      const bridge = new RustBridgeService(new SocketFactory());
      await expect(
        bridge.evaluateProposal(
          { ...portfolio, open_positions: [] },
          { ...proposal, asset_id: big },
        ),
      ).rejects.toThrow('Frame exceeds MAX_FRAME_BYTES');
    });
  });
});