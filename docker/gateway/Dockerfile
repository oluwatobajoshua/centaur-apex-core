# ==============================================================================
# Centaur-Apex Core — NestJS Gateway Dockerfile
# G8 Genesis DNA: orchestration skeleton + IPC framing only. No hardcoded
# business alpha — just REST/WebSocket routing to the Constitution boundary.
# ==============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY gateway/package*.json ./
RUN npm ci --omit=dev

COPY gateway/package*.json ./
RUN npm ci

# Build TypeScript → dist/
COPY gateway/ ./
RUN npm run build

# Runtime stage — Node 20 slim
FROM node:20-slim AS runtime

WORKDIR /app

# Copy production dependencies
COPY --from=builder /app/node_modules ./node_modules
# Copy compiled output
COPY --from=builder /app/dist ./dist
# Copy non-compiled config
COPY gateway/nest-cli.json ./
COPY gateway/tsconfig*.json ./

# The gateway spawns constitution_cli as a subprocess; install the Rust binary
# at runtime via the init script, or expect it at CONSTITUTION_CLI_PATH.
ENV CONSTITUTION_CLI_PATH=/usr/local/bin/constitution_cli
ENV CONSTITUTION_TRANSPORT=tcp
ENV CONSTITUTION_HOST=constitution
ENV CONSTITUTION_PORT=15565
ENV PORT=3000

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10 --retries=3 \
  CMD ["node", "-e", "require('http').get('http://localhost:3000/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"]

ENTRYPOINT ["node", "dist/main"]
