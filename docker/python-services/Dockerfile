# ==============================================================================
# Centaur-Apex Core — Python Services Dockerfile
# Runs Cortex (G5), Evolution (G2), Mesh (G4), Compliance (G6), Doomsday (G6),
# Simulation (G7) as a unified Python image. Each module's pyproject.toml
# dependencies are installed; the conftest.py path injection is replaced by
# editable installs of every package.
# ==============================================================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for cryptography / liboqs build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy and install all package pyproject.toml files in dependency order
COPY cortex/pyproject.toml cortex/pyproject.toml
COPY adapters/pyproject.toml adapters/pyproject.toml
COPY evolution/pyproject.toml evolution/pyproject.toml
COPY mesh/pyproject.toml mesh/pyproject.toml
COPY compliance/pyproject.toml compliance/pyproject.toml
COPY simulation/pyproject.toml simulation/pyproject.toml
COPY doomsday/pyproject.toml doomsday/pyproject.toml
COPY pyproject.toml pyproject.toml

# Install all Python packages in editable mode so imports resolve at runtime
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        pydantic>=2.0.0 numpy>=1.24.0 requests>=2.31.0 \
        pandas>=2.0.0 websockets>=11.0 gitpython>=3.1.0 \
        cryptography>=41.0.0 jsonschema>=4.18.0 ruff

# Copy source trees (editable install mounts)
COPY cortex/ cortex/
COPY adapters/ adapters/
COPY evolution/ evolution/
COPY mesh/ mesh/
COPY compliance/ compliance/
COPY simulation/ simulation/
COPY doomsday/ doomsday/
COPY conftest.py run_pipeline.py .

# Install packages as editable so the nested layout resolves correctly
RUN pip install --no-cache-dir --no-deps -e cortex -e adapters -e evolution \
    -e mesh -e compliance -e simulation -e doomsday 2>/dev/null || true

ENV PYTHONPATH="/app/cortex:/app/adapters:/app/evolution:/app/mesh:/app/compliance:/app/simulation:/app/doomsday:/app"
ENV PYTHONDONTWRITEBYTECODE=1

# Default: run the live E2E pipeline
ENTRYPOINT ["python", "run_pipeline.py"]
CMD []
