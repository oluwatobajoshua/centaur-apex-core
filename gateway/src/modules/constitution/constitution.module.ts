import { Module } from '@nestjs/common';
import { CliBridgeService, CliRunner } from './cli-bridge.service';
import { CONSTITUTION_TRANSPORT } from './constitution-transport';
import { ConstitutionController } from './constitution.controller';
import { RustBridgeService, SocketFactory } from './rust-bridge.service';

/**
 * Selects the transport at boot from `CONSTITUTION_BRIDGE` (`tcp` | `cli`).
 * Defaults to the TCP daemon. Data-driven config: no hardcoded wiring.
 */
function transportFactory(): CliBridgeService | RustBridgeService {
  const mode = (process.env.CONSTITUTION_BRIDGE ?? 'tcp').toLowerCase();
  return mode === 'cli' ? new CliBridgeService() : new RustBridgeService();
}

@Module({
  controllers: [ConstitutionController],
  providers: [
    SocketFactory,
    CliRunner,
    { provide: CONSTITUTION_TRANSPORT, useFactory: transportFactory },
  ],
  exports: [CONSTITUTION_TRANSPORT],
})
export class ConstitutionModule {}