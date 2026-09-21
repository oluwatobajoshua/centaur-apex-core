import { Module } from '@nestjs/common';
import { CortexController } from './cortex.controller';
import { CortexCliRunner, CortexService } from './cortex.service';

@Module({
  controllers: [CortexController],
  providers: [CortexService, CortexCliRunner],
  exports: [CortexService],
})
export class CortexModule {}