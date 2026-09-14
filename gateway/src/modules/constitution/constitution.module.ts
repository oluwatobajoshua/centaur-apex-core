import { Module } from '@nestjs/common';
import { ConstitutionController } from './constitution.controller';
import { RustBridgeService } from './rust-bridge.service';

@Module({
  controllers: [ConstitutionController],
  providers: [RustBridgeService],
  exports: [RustBridgeService],
})
export class ConstitutionModule {}