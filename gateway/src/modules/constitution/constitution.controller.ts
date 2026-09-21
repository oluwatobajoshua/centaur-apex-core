import { Body, Controller, Get, Inject, Post } from '@nestjs/common';
import { ApiBody, ApiOkResponse, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CONSTITUTION_TRANSPORT, ConstitutionTransport } from './constitution-transport';
import { PortfolioState, TradeProposal } from './rust-bridge.service';

class EvaluateBody {
  portfolio!: PortfolioState;
  proposal!: TradeProposal;
}

@ApiTags('constitution')
@Controller('constitution')
export class ConstitutionController {
  constructor(
    @Inject(CONSTITUTION_TRANSPORT) private readonly transport: ConstitutionTransport,
  ) {}

  @Get('status')
  @ApiOperation({ summary: 'Read Iron Constitution operational status' })
  @ApiOkResponse({ description: 'system_state, counters, and transition journal' })
  status() {
    return this.transport.getStatus();
  }

  @Post('evaluate')
  @ApiOperation({
    summary: 'Adjudicate a Cortex proposal against the Iron Constitution invariants',
  })
  @ApiBody({
    description: 'Portfolio snapshot + trade proposal (same schema as EvaluateProposal IPC)',
    type: EvaluateBody,
  })
  @ApiOkResponse({ description: 'ConstitutionVerdict + resulting system_state' })
  evaluate(@Body() body: EvaluateBody) {
    return this.transport.evaluateProposal(body.portfolio, body.proposal);
  }
}