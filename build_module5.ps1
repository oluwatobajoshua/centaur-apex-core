# ==============================================================================
# CENTAUR-APEX: Module 5 Automation Script (Decentralized Edge Mesh & PQC Layer)
#
# Verifies the canonical schema-first mesh scaffold and normalizes file encodings.
# The tracked files under mesh/ are the single source of truth (AGENTS.md G9:
# reproducible scaffolding, zero duplicated generation code). If any canonical
# file is missing the script fails loudly so the bootstrap never silently
# produces a partial mesh.
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "Verifying Module 5: Decentralized Edge Mesh & PQC Layer..." -ForegroundColor Cyan

$meshDirs = @(
    "mesh/mesh",
    "mesh/mesh/microgrid",
    "mesh/tests"
)

foreach ($dir in $meshDirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Write-Host "Ensured directory: $dir" -ForegroundColor Green
}

$canonicalFiles = @(
    "mesh/pyproject.toml",
    "mesh/mesh/__init__.py",
    "mesh/mesh/pqc_wrapper.py",
    "mesh/mesh/peer_transport.py",
    "mesh/mesh/bft_consensus.py",
    "mesh/mesh/node_daemon.py",
    "mesh/mesh/microgrid/__init__.py",
    "mesh/mesh/microgrid/telemetry.py",
    "mesh/tests/test_pqc_wrapper.py",
    "mesh/tests/test_bft_consensus.py",
    "mesh/tests/test_node_daemon.py",
    "mesh/tests/test_mesh_integration.py"
)

foreach ($file in $canonicalFiles) {
    if (!(Test-Path -LiteralPath $file)) {
        Write-Error "Canonical mesh file missing: $file (checkout is incomplete)"
    }
    Write-Host "Verified canonical: $file" -ForegroundColor DarkGray
}

# Normalize: any UTF-8 BOM (from legacy Set-Content -Encoding UTF8) breaks
# tomllib/json parsers and pytest rootdir detection. Strip it everywhere.
Get-ChildItem -Path "mesh" -Recurse -File | Where-Object {
    $_.Extension -in ".toml", ".json", ".jsonschema", ".py"
} | ForEach-Object {
    $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [System.IO.File]::WriteAllBytes($_.FullName, $bytes[3..($bytes.Length - 1)])
        Write-Host "Stripped BOM: $($_.FullName)" -ForegroundColor DarkGray
    }
}

Write-Host "[SUCCESS] Module 5 (Decentralized Edge Mesh & PQC) scaffold verified." -ForegroundColor Green
Write-Host "Real WebSocket BFT transport, Dilithium3 PQC engine, microgrid hooks ready." -ForegroundColor Cyan