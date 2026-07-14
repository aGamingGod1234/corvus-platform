## 2026-07-14 — M2 Hackathon Execution Core Slice

### What Was Implemented
- Added an authoritative SQLite-backed workflow service with versioned outcomes, dependency graphs, deterministic local execution, attempts, fenced leases, recovery, checkpoints, artifacts, lineage, conversations, and monotonic events.
- Added typed provider/filesystem effect bindings, deterministic effect idempotency, one-time approvals, conserved budget reservation/settlement/release, workflow controls, and kill switches.
- Added focused red-green tests for dependency scheduling, restart recovery, stale leases, approvals, budgets, kill switches, heartbeat, failure, and retry.

### Files Modified
- `corvus/mvp/models.py` — typed hackathon domain contracts.
- `corvus/mvp/store.py` — explicit SQLite schema migration and transactional store.
- `corvus/mvp/core.py` — authoritative execution application service.
- `corvus/mvp/__init__.py` — package entry point.
- `tests/mvp/test_execution_core.py` — critical M2 behavior tests.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- The hackathon MVP may use a dedicated additive `mvp_*` SQLite schema so M0.5/M1 tables and authority behavior remain untouched.
- Local provider/filesystem effect adapters return deterministic, digest-bound results until their later adapter lanes add external boundaries.

### Known Issues / Deferred
- CLI, HTTP/SSE, web, collaboration, connector/channel, deployment, and desktop adapters are deferred to their dependency-ordered lanes.
- Formal M2 certification-scale schemas and matrices are intentionally outside the objective's hackathon scope.

### Suggested Next Steps
- Expose the application service through thin CLI and FastAPI adapters with local pairing, CSRF, and replayable SSE.

## 2026-07-14 — M3 Thin CLI Adapter

### What Was Implemented
- Added `corvus-mvp` project, outcome, and workflow commands that call the authoritative application service.
- Added a single-command durable demo covering dependency execution, approval, budget settlement, and restart verification.
- Added CLI adapter tests that exercise real SQLite state rather than mocks.

### Files Modified
- `corvus/cli.py` — registers the additive MVP command group without altering retained commands.
- `corvus/mvp/cli.py` — thin Typer adapter and demo orchestration.
- `tests/mvp/test_cli_adapter.py` — CLI integration tests.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- The additive `corvus-mvp` console entry point preserves the frozen M0.5/M1 `corvus` command tree.

### Known Issues / Deferred
- FastAPI/uvicorn are not installed and require dependency approval before the M4 adapter can be executed.
- Additional inspection commands will be added alongside the remaining domain surfaces.

### Suggested Next Steps
- Add secure local authentication, CSRF protection, typed API routes, and replayable SSE after dependency approval.

## 2026-07-14 — M6–M9 Governed Local Domain Slices

### What Was Implemented
- Added tenant/project teams, owner-controlled membership, provider references, capability grants, an effect-boundary secret broker, simulated OAuth PKCE, stored autonomy evidence, and policy-driven shadow promotion.
- Added governed memory retrieval through an explicit untrusted-data context firewall, versioned skills, active-skill routines, and authorized routine runs.
- Added Ed25519-signed offline intent queue/reconciliation and signed channel ingress with expiry, digest verification, identity mapping, deduplication, and sensitive-action step-up state.

### Files Modified
- `corvus/mvp/store.py` — additive schema migration for M6–M9 state.
- `corvus/mvp/governance.py` — teams, providers, broker, autonomy, memory, skills, and routines.
- `corvus/mvp/ingress.py` — signed offline and channel envelope services.
- `tests/mvp/test_governance.py` — governed collaboration/autonomy/memory tests.
- `tests/mvp/test_ingress.py` — signature, reconciliation, dedupe, identity, and step-up tests.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- Ed25519 local actor keys are suitable test/demo credentials; only public keys are persisted.
- The simulated OAuth authorization code is a local adapter, while PKCE state/verifier binding uses the real contract and stores only the verifier digest.

### Known Issues / Deferred
- Device-flow demonstration, restore quarantine, HTTP channel ingress, and CLI/web access remain for adapter lanes.
- No real provider registration or credential value is persisted or externally exercised.

### Suggested Next Steps
- Expose these services through authenticated API/CLI/web surfaces after dependency approval.

## 2026-07-14 — M10–M11 Deployment and Desktop Contracts

### What Was Implemented
- Added fail-closed self-host configuration validation for SQLite/PostgreSQL URLs and HTTPS requirements.
- Added tenant-scoped project queries and a simulated OIDC claim mapper that ignores client-supplied authority claims.
- Added a desktop sidecar lifecycle state machine and expiring, rollback-protected, threshold-signed update manifest verification with ephemeral local test keys.

### Files Modified
- `corvus/mvp/deployment.py` — deployment settings, tenant queries, and OIDC mapping.
- `corvus/mvp/desktop.py` — sidecar lifecycle and update verification contracts.
- `tests/mvp/test_deployment_desktop.py` — isolation, OIDC, lifecycle, and threshold-signature tests.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- PostgreSQL is represented as a validated production configuration path while SQLite remains the locally executable database.
- Update keys generated by tests are explicitly non-production and remain in process memory only.

### Known Issues / Deferred
- Container startup waits for the executable FastAPI server command; static-web integration waits for the M5 build.
- Rust/Cargo are unavailable, so the Tauri shell and packaging check cannot yet be built.

### Suggested Next Steps
- Complete the authenticated API/web runtime, then wire it into container and Tauri shells.

## 2026-07-14 — Extended Local Capabilities and Supply Chain

### What Was Implemented
- Added simulated provider device flow with owner approval and expiry-aware polling.
- Added idempotent restore quarantine and explicit reviewed import-candidate promotion without replacing workspace authority.
- Added CLI inspection for durable workflows and a capabilities demo spanning teams, providers, autonomy, memory, skills, routines, offline intents, channel ingress, and restore quarantine.
- Added deterministic CycloneDX SBOM and SLSA/in-toto-style provenance generation.

### Files Modified
- `corvus/mvp/store.py` — additive device-flow and restore-quarantine migration.
- `corvus/mvp/governance.py` — device-flow and quarantine services.
- `corvus/mvp/cli.py` — workflow inspection and governed capabilities demo.
- `scripts/generate_supply_chain.py` — deterministic SBOM/provenance generator.
- `tests/mvp/test_cli_adapter.py` — CLI coverage for durable inspection and capability paths.
- `tests/mvp/test_governance.py` — device-flow and quarantine tests.
- `tests/mvp/test_supply_chain.py` — SBOM/provenance tests.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- Quarantined restores may become reviewed import candidates but never authority-bearing replacements.
- Local SBOM/provenance generation binds committed source inputs; external transparency-log publication is outside the local-only scope.

### Known Issues / Deferred
- HTTP/web/desktop adapters remain dependency-gated.
- Container startup is deferred until the FastAPI server command exists.

### Suggested Next Steps
- Install the approved API/web/desktop dependencies and complete the remaining connected adapters.

## 2026-07-14 — Operator Demo and Truthful Status Checkpoint

### What Was Implemented
- Extended the capabilities demo to prove offline and channel replay counts remain exactly one.
- Added an operator-facing self-host configuration validation command.
- Created a milestone-by-milestone status document with current commands, verification evidence, and explicit dependency-gated gaps.

### Files Modified
- `corvus/mvp/cli.py` — replay evidence and `config-check` command.
- `tests/mvp/test_cli_adapter.py` — replay and configuration command tests.
- `HACKATHON_STATUS.md` — truthful partial implementation and verification status.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- A status document should exist before completion and explicitly mark unimplemented adapters rather than waiting to document risk.

### Known Issues / Deferred
- M4, M5, executable container integration, and Tauri packaging remain dependency-gated.

### Suggested Next Steps
- Obtain dependency approval, then implement and verify the connected HTTP, web, and desktop paths.

## 2026-07-14 — Authenticated Local API and SSE Runtime

### What Was Implemented
- Added a loopback FastAPI adapter over the authoritative SQLite-backed application service.
- Added one-time pairing, signed cookie sessions, tenant checks, CSRF/origin enforcement, typed errors, and bounded resumable SSE replay.
- Added project, outcome, workflow, approval, budget, artifact, and conversation endpoints.
- Added a runnable `corvus-mvp server` command that resolves pairing and signing material only through secret references.

### Files Modified
- `corvus/mvp/api.py` — authenticated HTTP and SSE adapter.
- `corvus/mvp/cli.py` — secret-reference server factory and local server command.
- `corvus/mvp/store.py` — additive local-user migration.
- `tests/mvp/test_api.py` — HTTP authorization, execution, replay, approval, and budget coverage.
- `tests/mvp/test_cli_adapter.py` — server factory and credential-boundary coverage.
- `pyproject.toml` and `uv.lock` — approved FastAPI, Uvicorn, and current test-client dependencies.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- The local MVP binds to loopback by default and uses an environment or keyring reference for each runtime credential.
- Browser clients use the signed session cookie and obtain the CSRF value from the authenticated session endpoint.

### Known Issues / Deferred
- The React client and broader collaboration-resource endpoints remain to be connected.
- Production TLS termination is a deployment concern; the local loopback cookie is intentionally usable over HTTP.

### Suggested Next Steps
- Build the generated-contract React client and verify the same durable workflow through the browser adapter.
