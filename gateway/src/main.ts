import { NestFactory } from '@nestjs/core';
import { Logger } from '@nestjs/common';
import { AppModule } from './app.module';
import { setupOpenApi } from './swagger';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  setupOpenApi(app);

  const logger = new Logger('Bootstrap');
  await app.listen(process.env.PORT ?? 3000);
  logger.log('Centaur-Apex Gateway listening on port ' + (process.env.PORT ?? 3000));
  logger.log('OpenAPI docs available at /docs');
}

void bootstrap();