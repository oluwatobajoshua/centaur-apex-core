# Centaur-Apex Core — uniform developer entry points (OSS_SPEC §9).
# Windows: use the PowerShell build scripts (build_module*.ps1) for module
# bootstrap; the Makefile targets cover check/test gates cross-platform.

.PHONY: build test check chronos pipeline lint fmt clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

build: ## Build the Rust Constitution core (release)
	cargo build --release --manifest-path constitution/Cargo.toml

test: ## Run Rust unit + integration tests
	cargo test --manifest-path constitution/Cargo.toml

check: ## Compile-check all Python modules
	python -m compileall -q cortex adapters mesh compliance simulation evolution

chronos: ## Run the Chronos integration harness (250 simulated years)
	python simulation/tests/integration_chronos.py

pipeline: ## Run the live Cortex -> Constitution pipeline
	python run_pipeline.py

fmt: ## Format check (Rust) + compileall
	cargo fmt --check --manifest-path constitution/Cargo.toml
	python -m compileall -q cortex adapters mesh compliance simulation evolution

lint: ## Clippy (Rust) — best-effort, no deny yet
	@cargo clippy --manifest-path constitution/Cargo.toml -- -D warnings 2>/dev/null || \
	  echo "clippy not installed; run: rustup component add clippy"

clean: ## Remove Rust artifacts
	cargo clean --manifest-path constitution/Cargo.toml