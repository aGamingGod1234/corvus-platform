# Corvus M2–M11 Hackathon MVP Status

This is a hackathon MVP implementation record, not formal M2–M11 certification.

## Baseline and Branch

- Baseline: `repair/m1-certification` at `8c18f53`.
- Implementation branch: `hackathon/m2-m11-mvp`.
- M0.5 and M1 history and behavior were preserved; the MVP uses additive `corvus.mvp` code and `mvp_*` SQLite tables.

## Architecture

- `corvus.mvp.core.CorvusService` is the authoritative local workflow/effect/budget core.
- `GovernanceService`, `OfflineConnectorService`, and `ChannelIngressService` are server-side application services over the same transactional SQLite store.
- `corvus-mvp` is a separate thin Typer adapter that preserves the frozen V1 `corvus` command tree.
- FastAPI is a thin authenticated adapter over the same core; the React and Tauri adapters are still pending.
- Credentials persist only as `env://` or `keyring://` references. The local broker resolves values only at the effect boundary.

## Current Commands

Install the locked Python environment:

```powershell
uv sync --all-groups --locked
```

Migration is automatic and explicit when an MVP service opens its SQLite database:

```powershell
uv run corvus-mvp config-check --mode local --database-url sqlite:///corvus-mvp.sqlite3 --json
```

Run the durable workflow demo and inspect the same persisted run:

```powershell
uv run corvus-mvp demo --database corvus-mvp.sqlite3 --json
uv run corvus-mvp workflow inspect <WORKFLOW_ID> --database corvus-mvp.sqlite3 --json
```

Run governed M6–M10 local capabilities:

```powershell
uv run corvus-mvp capabilities-demo --database corvus-capabilities.sqlite3 --json

Run the authenticated loopback API with runtime credential references:

```powershell
$env:CORVUS_BOOTSTRAP_TOKEN = '<one-time-pairing-value>'
$env:CORVUS_SESSION_SECRET = '<at-least-32-byte-signing-value>'
uv run corvus-mvp server --database corvus-mvp.sqlite3
```
```

Build the Python package and supply-chain artifacts:

```powershell
uv build
uv run python scripts/generate_supply_chain.py --output-dir dist/supply-chain
```

The pnpm and Rust toolchains are installed. Web and desktop commands remain undocumented until their connected builds pass.

## Concise Local Demo

1. Run `uv run corvus-mvp demo --database corvus-mvp.sqlite3 --json`.
2. Copy `workflow_id` from the JSON result.
3. Run `uv run corvus-mvp workflow inspect <WORKFLOW_ID> --database corvus-mvp.sqlite3 --json`.
4. Run `uv run corvus-mvp capabilities-demo --database corvus-mvp.sqlite3 --json`.
5. Re-run either inspect/capabilities command to observe persisted and duplicate-safe state.

## Milestone Status

### Implemented and Locally Verified

- **M2:** Versioned outcomes; durable dependency graphs; states; scheduling; attempts; fenced leases/heartbeat/recovery; checkpoints; artifacts/lineage; conversations/events; typed effects; deterministic idempotency; one-time approvals; budgets; kill switches; pause/resume/cancel/retry; deterministic executor; restart persistence.
- **M3:** Additive CLI project/outcome/workflow creation, execution, status, inspection, configuration checking, and two end-to-end demos over application services.
- **M4:** One-time pairing, signed cookie session, CSRF/origin enforcement, tenant-scoped REST mutations, typed errors, bounded resumable SSE, and a secret-reference local server command.
- **M6:** Teams/memberships; owner authorization; provider references/grants; local secret broker; simulated OAuth PKCE and device flow; evidence-backed shadow/autonomy promotion.
- **M7:** Governed memory with untrusted context-firewall output; versioned/activated skills; routines and authorized routine runs.
- **M8:** Ed25519-signed offline intents; local disconnect/queue/reconnect; signature/expiry/digest validation; idempotent reconciliation; restore quarantine.
- **M9:** Ed25519-signed channel envelopes; expiry/digest/signature validation; identity mapping; deduplication; persisted result; sensitive-action step-up state.
- **M10 contracts:** Local/self-host configuration validation, SQLite path, PostgreSQL configuration recognition, simulated OIDC mapping, tenant-scoped project reads, wheel build, deterministic SBOM and provenance generation.
- **M11 contracts:** Sidecar lifecycle state machine and expiring, rollback-protected, threshold-signed update metadata with non-production ephemeral test keys.

### Implemented but Not Externally Exercised

- PostgreSQL configuration recognition, real OAuth/OIDC providers, external secret stores, and production signing infrastructure.

### Scaffolded/Partial

- **M5:** Not started; the approved pnpm toolchain is installed and implementation is next.
- **M10:** Container/static-web integration waits for M4/M5 executable adapters.
- **M11:** Tauri shell/packaging waits for the web build and Rust/Cargo/Tauri toolchain.

### Blocked

- No current dependency-installation blocker; remaining adapters are in progress.

## Verification Performed

- Focused baseline: `3 passed`.
- Latest M4 focused gate: `9 passed`; frozen V1 contract gate: `2 passed`; repository-wide Ruff and strict source mypy passed.
- Real Uvicorn subprocess probe returned `200` for health, one-time pairing, and authenticated session while creating the requested SQLite database.
- Python build: `dist/corvus-0.2.0a1-py3-none-any.whl` and source archive built successfully; the wheel contained `corvus/mvp/core.py`.
- Generated CycloneDX SBOM and in-toto/SLSA-style provenance parsed as valid JSON.
- Web production build: not run; dependencies absent.
- Desktop check/build: not run; Rust/Cargo absent.

## Known Limitations

- No generated TypeScript client, connected web UI, or executable Tauri shell exists yet.
- The local deterministic effect adapter produces digest-bound results but does not perform an external provider call or privileged host write.
- No production cloud, real OAuth registration, PostgreSQL server, signing ceremony, notarization, or multi-OS certification was attempted.
