import { Module } from '@nestjs/common';
import { ConstitutionModule } from './modules/constitution/constitution.module';
import { CortexModule } from './modules/cortex/cortex.module';

@Module({
  imports: [ConstitutionModule, CortexModule],
})
export class AppModule {}