import { registerAs } from '@nestjs/config';

export default registerAs('constitution', () => ({
  host: process.env.CONSTITUTION_HOST ?? '127.0.0.1',
  port: Number(process.env.CONSTITUTION_PORT ?? 15565),
  timeoutMs: Number(process.env.CONSTITUTION_TIMEOUT_MS ?? 5000),
}));