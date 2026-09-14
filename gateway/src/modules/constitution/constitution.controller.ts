import { Controller, Get, Body, Post } from '@nestjs/common';
import {
  PortfolioState,
  RustBridgeService,
  TradeProposal,
} from './rust-bridge.service';

@Controller('constitution')
export class ConstitutionController {
  constructor(private readonly rustBridge: RustBridgeService) {}

  @Get('status')
  status(): Promise<{ system_state: string; proposals_seen: number; emergencies: number }> {
    return this.rustBridge.getStatus();
  }

  @Post('evaluate')
  evaluate(
    @Body() body: { portfolio: PortfolioState; proposal: TradeProposal },
  ): Promise<{ verdict: unknown; system_state: string }> {
    return this.rustBridge.evaluateProposal(body.portfolio, body.proposal);
  }
}