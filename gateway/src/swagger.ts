import { INestApplication } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';

/** Single mechanism for OpenAPI/Swagger docs, shared by bootstrap and e2e. */
export function setupOpenApi(app: INestApplication): void {
  const config = new DocumentBuilder()
    .setTitle('Centaur-Apex Core Gateway')
    .setDescription('REST orchestration hub: Iron Constitution bridge + Cortex proposal emission')
    .setVersion('0.1.0')
    .build();
  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('docs', app, document);
}