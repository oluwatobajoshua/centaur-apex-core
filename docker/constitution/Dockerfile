# ==============================================================================
# Centaur-Apex Core — Iron Constitution (Rust) Dockerfile
# G1 Genesis DNA: deterministic risk kernel. This Dockerfile builds the
# minimal release binary for the TCP daemon (constitutiond) and CLI bridge
# (constitution_cli). No runtime deps — statically linked where possible.
# ==============================================================================
FROM rust:1.75 AS builder

WORKDIR /app

# Cache dependencies: copy only Cargo.toml + lockfile-equivalent manifest
RUN cargo new --bin constitutiond-tmp --vcs none 2>/dev/null || true
COPY constitution/Cargo.toml /app/constitution/Cargo.toml
COPY constitution/src /app/constitution/src

# Build release binary (single binary, no dynamic linking needed)
RUN cargo build --release --manifest-path constitution/Cargo.toml --bin constitutiond 2>&1 \
    | sed '/^\s*Compiling/d; /^\s*Finished/d; /^\s*Running/d' \
    || cargo build --release --manifest-path constitution/Cargo.toml

# Runtime stage — distroless for minimal attack surface
FROM gcr.io/distroless/cc-debian12:nonroot

# Copy the release binary
COPY --from=builder /app/constitution/target/release/constitutiond /usr/local/bin/constitutiond
COPY --from=builder /app/constitution/target/release/constitution_cli /usr/local/bin/constitution_cli

LABEL org.opencontainers.image.source="https://github.com/oluwatobajoshua/centaur-apex-core"
LABEL org.opencontainers.image.description="Iron Constitution risk kernel daemon"

EXPOSE 15565

USER nonroot:nonroot

# constitutiond reads CONSTITUTION_HOST / CONSTITUTION_PORT env vars (defaults:
# 127.0.0.1:15565). Binds to 0.0.0.0 for container networking.
HEALTHCHECK --interval=5s --timeout=2s --start-period=1 --retries=3 \
  CMD ["/bin/sh", "-c", "echo '{\"protocol_version\":1,\"request_id\":\"health\",\"opcode\":\"Heartbeat\",\"payload\":\"{}\"}' | constitution_cli"] || exit 1

ENV CONSTITUTION_HOST=0.0.0.0
ENV CONSTITUTION_PORT=15565

ENTRYPOINT ["/usr/local/bin/constitutiond"]
CMD []
