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
- Added `corvus mvp` project, outcome, and workflow commands that call the authoritative application service.
- Added a single-command durable demo covering dependency execution, approval, budget settlement, and restart verification.
- Added CLI adapter tests that exercise real SQLite state rather than mocks.

### Files Modified
- `corvus/cli.py` — registers the additive MVP command group without altering retained commands.
- `corvus/mvp/cli.py` — thin Typer adapter and demo orchestration.
- `tests/mvp/test_cli_adapter.py` — CLI integration tests.
- `PROJECT_LOG.md` — implementation record.

### Assumptions Made (flag these for review)
- The additive `corvus mvp` namespace preserves retained M0.5/M1 CLI compatibility while the hackathon surfaces are built.

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
