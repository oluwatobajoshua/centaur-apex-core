import { Body, Controller, Get, Query, Post } from '@nestjs/common';
import { ApiBody, ApiOkResponse, ApiOperation, ApiQuery, ApiTags } from '@nestjs/swagger';
import {
  CortexEmissionInput,
  CortexEmissionResult,
  CortexService,
} from './cortex.service';

@ApiTags('cortex')
@Controller('cortex')
export class CortexController {
  constructor(private readonly cortex: CortexService) {}

  @Get('propose')
  @ApiOperation({ summary: 'Emit a Cortex proposal from normalized market inputs' })
  @ApiQuery({ name: 'asset', required: false, example: 'SYNTH-PERP' })
  @ApiQuery({ name: 'price', required: true, example: '100.0' })
  @ApiQuery({ name: 'equity', required: true, example: '1000000.0' })
  @ApiQuery({ name: 'trend', required: false, enum: ['bullish', 'bearish', 'neutral'] })
  @ApiQuery({ name: 'momentum', required: false, enum: ['0', '1'] })
  @ApiOkResponse({ description: 'ProposalGenerated with TradeProposal, or NoAction' })
  async propose(@Query() q: Record<string, string>): Promise<CortexEmissionResult> {
    const input: CortexEmissionInput = {
      assetId: q.asset ?? 'SYNTH-PERP',
      price: Number(q.price),
      equity: Number(q.equity),
      trend: (q.trend as CortexEmissionInput['trend']) ?? 'bullish',
      momentum: (q.momentum ?? '1') === '1',
      volatility: q.volatility ? Number(q.volatility) : undefined,
    };
    return this.cortex.emitProposal(input);
  }

  @Post('orchestrate')
  @ApiOperation({ summary: 'Orchestration placeholder (routing decisions)' })
  @ApiBody({ description: 'Unstructured orchestration payload', required: false })
  orchestrate(@Body() _body: Record<string, unknown>): { status: 'orchestrated' } {
    return this.cortex.forward();
  }
}