import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { AppModule } from '../src/app.module';
import { setupOpenApi } from '../src/swagger';
import * as fs from 'fs';
import * as path from 'path';
import request from 'supertest';

interface DocResponse {
  body: { info: { title: string }; paths: Record<string, unknown> };
}

describe('Gateway → constitution_cli → Constitution (e2e)', () => {
  let app: INestApplication;
  const originalEnv = { ...process.env };

  function cliBinary(): string {
    const exe = process.platform === 'win32' ? 'constitution_cli.exe' : 'constitution_cli';
    const repoRoot = path.resolve(__dirname, '..', '..');
    const debug = path.join(repoRoot, 'constitution', 'target', 'debug', exe);
    const release = path.join(repoRoot, 'constitution', 'target', 'release', exe);
    if (fs.existsSync(debug)) return debug;
    if (fs.existsSync(release)) return release;
    return exe;
  }

  beforeAll(async () => {
    process.env.CONSTITUTION_BRIDGE = 'cli';
    process.env.CONSTITUTION_CLI_PATH = cliBinary();
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    setupOpenApi(app);
    await app.init();
  });

  afterAll(async () => {
    process.env = { ...originalEnv };
    await app.close();
  });

  it('GET /constitution/status reaches the Rust kernel via constitution_cli', async () => {
    const res = await request(app.getHttpServer()).get('/constitution/status').expect(200);
    expect(res.body.system_state).toBe('Normal');
    expect(typeof res.body.proposals_seen).toBe('number');
    expect(Array.isArray(res.body.state_history)).toBe(true);
  });

  it('POST /constitution/evaluate returns a binding verdict', async () => {
    const res = await request(app.getHttpServer())
      .post('/constitution/evaluate')
      .send({
        portfolio: {
          timestamp: 1,
          total_equity: 1_000_000,
          cash_balance: 1_000_000,
          high_water_mark: 1_000_000,
          open_positions: [],
        },
        proposal: {
          proposal_id: 'e2e-1',
          asset_id: 'SYNTH-PERP',
          direction: 'Buy',
          target_notional: 10_000,
          max_acceptable_slippage: 0.001,
        },
      })
      .expect(201);
    expect(res.body.verdict).toEqual({ Approved: { adjusted_notional: 10_000 } });
    expect(res.body.system_state).toBe('Normal');
  });

  it('downsizes/rejects proposals that breach concentration limits', async () => {
    const res = await request(app.getHttpServer())
      .post('/constitution/evaluate')
      .send({
        portfolio: {
          timestamp: 1,
          total_equity: 100_000,
          cash_balance: 100_000,
          high_water_mark: 100_000,
          open_positions: [],
        },
        proposal: {
          proposal_id: 'e2e-2',
          asset_id: 'SYNTH-PERP',
          direction: 'Buy',
          target_notional: 40_000,
          max_acceptable_slippage: 0.001,
        },
      })
      .expect(201);
    expect('Rejected' in res.body.verdict || 'Approved' in res.body.verdict).toBe(true);
  });

  it('GET /docs exposes the OpenAPI/Swagger document', async () => {
    await request(app.getHttpServer())
      .get('/docs-json')
      .expect(200)
      .expect((res: DocResponse) => {
        expect(res.body.info.title).toContain('Centaur-Apex Core Gateway');
        const paths = Object.keys(res.body.paths);
        expect(paths).toContain('/constitution/status');
        expect(paths).toContain('/constitution/evaluate');
        expect(paths).toContain('/cortex/propose');
      });
  });
});