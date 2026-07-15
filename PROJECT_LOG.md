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

## 2026-07-14 - M5 Connected Operator Console and Extended API

### What Was Implemented
- Added deterministic FastAPI OpenAPI export and a generated, typed React client.
- Added authenticated workflow pause/resume/cancel/retry, kill-switch, rejection, team/provider/autonomy, memory, skill, routine, offline visibility, and signed channel-ingress routes.
- Added an approval-bearing browser workflow, live SSE activity, approval inbox, budget controls, artifact/conversation inspection, and a responsive Operations view over real API data.
- Added design-blueprint provenance, component adoption, fixed viewport evidence, desktop/mobile browser acceptance, and regression coverage for dependency ordering and SSE event coalescing.

### Files Modified
- `corvus/mvp/api.py` - typed authenticated API and governed resource routes.
- `corvus/mvp/core.py` - topological display ordering and atomic effect rejection.
- `corvus/mvp/governance.py` - typed governed resource read models.
- `corvus/mvp/ingress.py` - offline and channel visibility queries.
- `corvus/mvp/openapi.py` and `openapi/corvus-mvp.json` - deterministic API contract export.
- `apps/web/` - generated-client React/Vite operator console, styles, and tests.
- `tests/mvp/test_api.py` and `tests/mvp/test_openapi_export.py` - API, security, control, ingress, and contract tests.
- `.antigravity/website-blueprint/` - design packet, sources, audit evidence, and screenshots.
- `.gitignore`, `HACKATHON_STATUS.md`, and `PROJECT_LOG.md` - generated-output policy and milestone records.

### Assumptions Made (flag these for review)
- The browser's default two-item demo may reserve 10 units and require approval for a 2-unit deterministic filesystem effect so the governed path is immediately demonstrable.
- The authenticated local user is the owner for teams created through the local UI; provider configuration accepts references only, never credential values.

### Known Issues / Deferred
- The installed design auditor has an unconditional restaurant `dish-selector` rule and a single-file React static scanner; its automated verdict remains failed despite real desktop/mobile browser verification. No inapplicable restaurant data was fabricated.
- Container/static-web integration and the executable Tauri shell remain M10/M11 work.

### Suggested Next Steps
- Commit and safely integrate the verified M5 milestone onto GitHub main.
- Add the container runtime and Tauri sidecar shell, then run the final restart-safe acceptance path.

## 2026-07-14 - M10 Self-Host and Static-Web Packaging

### What Was Implemented
- Added validated optional static-web serving so the compiled React client, authenticated API, health, readiness, and SSE share one origin.
- Added a multi-stage, non-root container build, read-only Compose service, persistent SQLite volume, health check, and environment template.
- Built the Python wheel and extended provenance generation to bind named build artifacts plus a deterministic static asset manifest.
- Exercised the production-style source-tree server through readiness, compiled web delivery, pairing, and clean listener shutdown.

### Files Modified
- `corvus/mvp/api.py` and `corvus/mvp/cli.py` - validated static root, configurable trusted origins, and server option.
- `Dockerfile`, `compose.yaml`, `.dockerignore`, and `.env.example` - reproducible self-host packaging.
- `scripts/generate_supply_chain.py` - worktree-safe commit discovery, static manifest, and artifact-bound provenance.
- `tests/mvp/test_packaging.py` and `tests/mvp/test_supply_chain.py` - static/API coexistence, traversal, packaging, and provenance coverage.
- `HACKATHON_STATUS.md` and `PROJECT_LOG.md` - exact startup, verification, and limitation record.

### Assumptions Made (flag these for review)
- The hackathon container uses SQLite at `/data/corvus.sqlite3` and serves the prebuilt web client from `/app/web` on port 8080.
- PostgreSQL remains a recognized production configuration contract; adding a second persistence implementation is outside the coherent local-demo path.

### Known Issues / Deferred
- Docker and Podman are not installed on this workstation, so the image definition could not be built locally; the equivalent wheel/web/server path was exercised directly.
- External OIDC registration and production TLS termination remain deployment integrations, as required by the hackathon scope boundary.

### Suggested Next Steps
- Commit and fast-forward M10 to GitHub main.
- Add the real Tauri shell, sidecar supervision, readiness/reconnect flow, graceful shutdown, and current-OS build check.

## 2026-07-14 - M11 Supervised Tauri Desktop Shell

### What Was Implemented
- Added a Tauri v2 Windows shell that starts the authoritative Python sidecar with fixed arguments and generated in-memory secrets, waits for readiness, and loads the real compiled web client.
- Added starting, ready, reconnecting, failed, and stopped lifecycle supervision with bounded health checks and a graceful stdin shutdown before kill fallback.
- Added fragment-only automatic desktop pairing; the client removes the secret before API traffic and exposes no Tauri IPC capability to the loopback web origin.
- Added pinned Rust/Node manifests, constrained navigation/CSP, generated app icons, current-user NSIS configuration, and current-Windows build evidence.
- Bound readiness to a per-launch private instance nonce, added a decoy-server regression, and retained bounded redacted child diagnostics for failed startup.
- Added desktop-only session repair for an existing local user, verified two launches against one persisted database, and kept the ordinary server's one-time pairing boundary closed.
- Applied the effective CSP at the HTTP origin, removed pairing material from React state, and made real main-window close synchronously supervise sidecar shutdown before exiting.

### Files Modified
- `corvus/mvp/api.py`, `corvus/mvp/desktop_runtime.py`, and `corvus/mvp/cli.py` - authenticated readiness, secure repeat pairing, CSP, supervised sidecar command, and shared server adapter.
- `apps/web/src/App.tsx` and `apps/web/src/App.test.tsx` - one-time desktop fragment pairing and regression coverage.
- `apps/desktop/` - Tauri configuration, Rust supervisor, capabilities, package locks, icons, and runbook.
- `tests/mvp/test_api.py`, `tests/mvp/test_packaging.py`, and `tests/mvp/test_desktop_runtime.py` - standard pairing boundary, CSP, instance proof, real two-launch persistence, web, pairing, and shutdown paths.
- `.gitignore`, `HACKATHON_STATUS.md`, and `PROJECT_LOG.md` - generated-output policy and verified milestone record.

### Assumptions Made (flag these for review)
- The current hackathon desktop build may resolve the local Corvus CLI through `CORVUS_SIDECAR_EXECUTABLE`; a production installer would bundle a separately built standalone sidecar.
- A dynamic loopback port plus same-origin web/API delivery is preferable to granting a remote web origin any Tauri IPC permissions.
- The desktop may issue a fresh ephemeral session for the single persisted local identity at each supervised launch; this permission is not enabled on the normal server path.

### Known Issues / Deferred
- The NSIS artifact is intentionally unsigned and not notarized; only the current Windows workstation was built and launched.
- The installer does not bundle a standalone Python runtime/sidecar, so installed launches require the local executable path until distribution packaging adds one.

### Suggested Next Steps
- Commit and fast-forward M11 to GitHub main.
- Run the final 20-point acceptance path, restart persistence proof, full suite, and clean-tree audit.

## 2026-07-14 - Final M2-M11 Acceptance and Release Evidence

### What Was Implemented
- Executed the documented durable demo and capability demo against one fresh SQLite database and asserted the complete M2-M11 local path.
- Verified restart persistence, exactly-once approved effect execution, budget settlement, durable CLI inspection, governed collaboration/memory/routine behavior, offline reconciliation, and signed channel step-up/deduplication.
- Rebuilt and launched the HMAC-authenticated Tauri/sidecar release, confirmed the connected WebView on a repeat launch, and proved real-window close leaves no desktop or sidecar process.
- Ran the full Python repository suite once in an isolated temp root and recorded exact web, Rust, installer, and security-review evidence.

### Files Modified
- `HACKATHON_STATUS.md` - exact 20-point acceptance mapping, final test/build counts, installer digest, and current published milestone.
- `PROJECT_LOG.md` - final acceptance and release record.

### Assumptions Made (flag these for review)
- The locally executable adapters and explicitly documented external-infrastructure limits satisfy hackathon-MVP depth without claiming production certification.

### Known Issues / Deferred
- Docker/Podman remains unavailable for a local image launch.
- The unsigned NSIS installer still expects a separately available local Python sidecar and is not a production distribution artifact.

### Suggested Next Steps
- Bundle and sign a standalone sidecar before distributing the installer beyond this development workstation.
- Exercise the existing container definition when a container engine is available.

## 2026-07-14 - Cross-Platform Certification Fixture Stabilization

### What Was Implemented
- Canonicalized Rich's equivalent rounded/square borders, help-panel wrapping, and non-JSON command-output line wrapping before comparison, while retaining the exact frozen fixture hash, output wording, exit codes, and command/schema checks.
- Fixed the MVP server-help assertion to use an explicit wide, no-color terminal on every CI operating system.
- Applied the repository's configured Ruff formatter to every file reported by the certification formatting gate; changes were mechanical only.

### Files Modified
- `tests/contract/test_v1_public_golden.py` - platform-neutral presentation normalization without changing the frozen command/schema contract.
- `tests/mvp/test_cli_adapter.py` - deterministic help rendering width and color environment.
- `corvus/infrastructure/repositories/audit.py`, `corvus/mvp/api.py`, `corvus/mvp/cli.py`, `corvus/mvp/core.py`, `corvus/mvp/governance.py`, and `corvus/mvp/ingress.py` - configured Ruff formatting only.
- `scripts/generate_supply_chain.py`, `tests/mvp/test_api.py`, `tests/mvp/test_desktop_runtime.py`, and `tests/mvp/test_execution_core.py` - configured Ruff formatting only.
- `PROJECT_LOG.md` - CI portability record.

### Assumptions Made (flag these for review)
- Rich's rounded and square panel corners are presentation-equivalent and not part of Corvus command semantics.

### Known Issues / Deferred
- None for this portability correction.

### Suggested Next Steps
- Confirm the complete GitHub Actions operating-system/Python matrix is green.

## 2026-07-14 - Certification Race and Byte-Stability Repair

### What Was Implemented
- Made the frozen delivery-review fixture byte-identical on every operating system by writing its CRLF input explicitly.
- Split the public-contract assertion by scenario so cross-platform failures identify the exact frozen command without relaxing command order or payload equality.
- Made read-only SQLite classification retry a bounded number of times when a WAL disappears during snapshot creation, covering the Windows close/checkpoint race.
- Added a deterministic WAL-disappearance regression and exercised the affected migration test repeatedly.
- Made the doctor smoke assertion follow the active supported Python interpreter instead of hardcoding 3.12.
- Replaced runtime-equivalent `os.name` guards with mypy-understood `sys.platform` guards around Windows-only locking and DLL APIs.

### Files Modified
- `tests/contract/test_v1_public_golden.py` - byte-stable delivery input and strict scenario-level diagnostics.
- `corvus/database.py` - bounded retry for a changing read-only SQLite snapshot.
- `tests/integration/test_database_bootstrap.py` - WAL-disappearance regression coverage.
- `tests/cli/test_cli_smoke.py` - Python 3.12/3.13-compatible doctor assertion.
- `corvus/delivery.py`, `corvus/codex_cli.py`, and `corvus/infrastructure/local_authority.py` - cross-platform static-analysis guards with unchanged runtime branches.
- `PROJECT_LOG.md` - certification repair record.

### Assumptions Made (flag these for review)
- None.

### Known Issues / Deferred
- None for this certification repair.

### Suggested Next Steps
- Confirm the complete GitHub Actions operating-system/Python matrix is green for the final `main` commit.

## 2026-07-14 — Persona and Team Desktop Implementation Plan

### What Was Implemented
- Audited the existing connected React console, generated API adapter, FastAPI domain surface, team primitives, and supervised Tauri shell.
- Defined a two-axis product architecture for Everyday/Developer and Personal/Team workspaces without duplicating authoritative business logic.
- Added one design milestone plus five implementation milestones covering the blueprint packet, shared shell, personal workspaces, governed collaboration core, team workspaces, desktop hardening, verification gates, and per-milestone GitHub main commits.

### Files Modified
- `docs/superpowers/plans/2026-07-14-persona-team-desktop-implementation-plan.md` — detailed implementation plan, decision gates, verification matrix, and stop boundaries.
- `PROJECT_LOG.md` — planning milestone record.

### Assumptions Made (flag these for review)
- The recommended product model is one binary composed along two axes: Everyday/Developer experience and Personal/Team workspace.
- Team means remote-capable, tenant-scoped multi-user collaboration; SQLite remains the local/demo path.
- In-app notifications plus SSE are sufficient for the first complete Team release; external notification delivery is deferred.

### Known Issues / Deferred
- Product code was intentionally not changed; the mandatory pre-coding confirmation gate remains active.
- Team hosting, production identity provider registration, external notification channels, billing, and live presence require later product/deployment decisions.

### Suggested Next Steps
- Review and approve the implementation plan and its seven recommended kickoff decisions.
- Execute Milestone 0 to produce and approve the four-workspace design-blueprint packet before changing application code.

## 2026-07-15 — Adaptive Workspace and Runtime Design Approval

### What Was Implemented
- Expanded the approved plan to include same-machine Local operation, E2B-backed Corvus Cloud, Google account continuity, truthful Cloud Preview entitlements, real Team collaboration foundations, and distinct web/desktop verification.
- Completed and approved the source-backed design-blueprint packet for one adaptive shell with Everyday/Developer and Personal/Team compositions.
- Defined exact onboarding, runtime, navigation, responsive, accessibility, identity, session, E2B lifecycle, security, capability-gating, and verification contracts.
- Captured baseline desktop, tablet, and mobile screenshots before application changes.
- Verified the packet, recorded Lucas's approval, and passed the blueprint build gate.

### Files Modified
- `docs/superpowers/plans/2026-07-14-persona-team-desktop-implementation-plan.md` — expanded milestones, runtime/account architecture, release gates, and stop boundaries.
- `docs/superpowers/specs/2026-07-15-corvus-adaptive-runtime-design.md` — implementation-level product, UX, security, runtime, and test specification.
- `.antigravity/website-blueprint/` — refreshed project context, research provenance, approved section plan, craft brief, storyboard, interaction contract, component adoption, visual target/composition, change plan, and before screenshots.
- `PROJECT_LOG.md` — design approval milestone record.

### Assumptions Made (flag these for review)
- Local means the current machine only; the local desktop sidecar and a browser on that machine may share the loopback service.
- Corvus Cloud will use one authoritative E2B sandbox per workspace behind a Corvus control plane; Local and Cloud will not silently dual-write or merge.
- Google identities will be linked by validated issuer and subject, while Corvus memberships remain authoritative for access.
- The first adaptive-shell milestone adds no dependency and presents Cloud as Preview until real identity and runtime capabilities exist.

### Known Issues / Deferred
- The current Tauri shell starts its Local sidecar before React loads; real pre-launch Cloud selection requires the later native runtime milestone.
- Live Google and E2B verification requires OAuth credentials, an E2B API key/template, and a control-plane endpoint.
- Payment collection, automatic Local/Cloud migration, external notifications, and multi-user Team UI remain deferred to their planned milestones.
- Final blueprint visual audit runs after Milestone 1 creates the approved shell.

### Suggested Next Steps
- Implement Milestone 1 test-first: versioned preferences, three-step onboarding, four navigation compositions, Local runtime gate, truthful Cloud Preview, responsive shell, and accessibility states.
- Stop after the tested Milestone 1 commit is pushed to `main` for hands-on review before identity or database migrations.

## 2026-07-15 — Adaptive Desktop and Web Shell

### What Was Implemented
- Added versioned, migration-safe workspace preferences and a three-step chooser for Everyday/Developer, Personal/Team, and Local/Corvus Cloud.
- Added one shared responsive shell with four profile-specific navigation models, preserved project context, desktop rail, mobile bottom navigation/profile sheet, and a full-screen mobile inspector.
- Kept Local on the authoritative `CorvusApi` path with fragment-only desktop pairing; no service request is made before runtime selection.
- Added a truthful Cloud Preview with E2B/Google continuity described as planned, no fake sign-in, no price/card collection, disabled billing, and a Local fallback.
- Added focus restoration, semantic landmarks, keyboard radio selection, skip navigation, reduced-motion handling, connection/loading/error states, and a route render boundary.
- Completed fixed-viewport blueprint review plus real FastAPI browser and rebuilt Tauri Windows interaction tests.

### Files Modified
- `apps/web/src/App.tsx`, `apps/web/src/main.tsx`, and `apps/web/src/icons.tsx` — adaptive bootstrap integration, protected workspace routing, and sourced UI icons.
- `apps/web/src/app/` — preference model, onboarding, four workspace profiles, shared shell/router, and render error containment.
- `apps/web/src/components/` — desktop/mobile navigation, workspace switching, and truthful connection state.
- `apps/web/src/runtime/CloudPreview.tsx` — capability-honest Cloud Preview and Local fallback.
- `apps/web/src/styles/` — Corvus visual system, responsive composition, motion, reduced-motion, and mobile inspector behavior.
- `apps/web/src/**/*.test.tsx` and `apps/web/src/test/memoryStorage.ts` — 23 preference, shell, accessibility, adapter, and workflow regression tests.
- `.antigravity/website-blueprint/` — after screenshots, runtime evidence, human scorecard, and final audit report.
- `docs/superpowers/plans/2026-07-14-persona-team-desktop-implementation-plan.md` — completed Milestone 1 checklist and gate evidence.
- `HACKATHON_STATUS.md` and `PROJECT_LOG.md` — release record and explicit deferred boundary.

### Assumptions Made (flag these for review)
- Local continues to mean the current machine only; the desktop sidecar and same-machine browser remain separate clients of the existing loopback authority.
- Team profiles are information-architecture previews until shared membership/capability storage is implemented; selecting Team grants no authority.

### Known Issues / Deferred
- Corvus Cloud remains Preview: native pre-sidecar runtime selection, Google identity, E2B lifecycle, cross-device continuity, and billing are not implemented.
- Real multi-user Team collaboration and database migrations remain behind the approved post-Milestone-1 stop boundary.
- The blueprint static HTML auditor cannot execute the SPA to observe runtime component markers; Playwright-rendered evidence and source markers were reviewed instead.
- The mobile More sheet does not yet include a project picker; the active project is preserved when switching profiles.

### Suggested Next Steps
- Perform hands-on review of the pushed adaptive shell.
- At the next authorized boundary, implement the native Local/Cloud chooser, Google continuity, and E2B sandbox lifecycle before multi-user collaboration migrations.

## 2026-07-15 — Provider Runtime and Deep E2E Audit

### What Was Implemented
- Completed a deeper read-only web/API/runtime audit and live end-to-end pass without changing production code.
- Verified the complete workflow approval boundary: preparation succeeded, delivery stopped for approval, and the workflow completed only after explicit approval.
- Verified team creation, credential-reference-only provider setup, shadow evaluation, untrusted memory retrieval, skill/routine creation and execution, reload persistence, and mobile overflow behavior.
- Audited installed local AI tools and documented the provider/unattended-mode decision boundary in `QUESTIONS.md`.

### Files Modified
- `QUESTIONS.md` — mandatory autonomous-work stop record with verified state, assumptions, decisions, recommended UX contract, and explicit boundary.
- `PROJECT_LOG.md` — verification evidence and deferred implementation record.

### Assumptions Made (flag these for review)
- No implementation assumptions were applied; ambiguous provider routing and unattended authority were recorded for confirmation.

### Known Issues / Deferred
- A hard offline browser reload reaches the browser network error page; offline startup is not supported.
- Four visible mobile controls measured 30 px high, below the preferred 40–44 px touch target.
- The Skills route remains overloaded with collaboration, providers, memory, skills, routines, and ingress.
- Claude and Gemini are installed but have no Corvus runtime adapters; Cursor and Grok/xAI CLIs are absent.

### Suggested Next Steps
- Confirm the five decisions in `QUESTIONS.md`.
- Implement the AI connection flow and typed `AgentRuntimePort` test-first, preserving all authority and secret boundaries.
- Implement bounded unattended profiles only after their pre-authorization envelope is confirmed.

## 2026-07-15 — Agent Runtime Decision-Ready Contract

### What Was Implemented
- Converted local CLI probes, current Corvus seams, official provider documentation, and the deep E2E findings into a provider-by-provider implementation contract.
- Specified a separate typed `AgentRuntimePort`, capability model, authority-bound run request, sequenced redacted events, cancellation contract, progressive AI connection UX, and bounded unattended profiles.
- Defined seven independently verifiable delivery milestones plus unit, adapter, API/security, browser, Windows Computer Use, and certification gates.

### Files Modified
- `docs/superpowers/plans/2026-07-15-agent-runtime-implementation-plan.md` — decision-ready architecture, UX, adapter safety profiles, milestones, and verification matrix.
- `PROJECT_LOG.md` — planning checkpoint and preserved stop boundary.

### Assumptions Made (flag these for review)
- The five values labeled as recommendations remain proposals, not implementation decisions.
- Provider-runtime implementation remains paused until `QUESTIONS.md` is confirmed.

### Known Issues / Deferred
- Cursor runtime conformance cannot be tested until `cursor-agent` is installed.
- Grok is specified through the xAI Responses API because no supported local Grok CLI is present.
- Google/E2B sequencing remains an explicit product decision.

### Suggested Next Steps
- Confirm the recommended defaults in `QUESTIONS.md`.
- Begin M2A with failing contract/security tests before any live adapter wiring.

## 2026-07-15 — M2A Task 1 Agent Runtime Contracts and Simulator

### What Was Implemented
- Added strict immutable provider, capability, autonomy, request, handle, event, and cancellation contracts for the agent-runtime boundary.
- Added an infrastructure-independent application protocol and deterministic simulator with digest-chained replay, idempotent cancellation, and substitution-safe start/resume behavior.
- Hardened event payloads with deep immutability while preserving JSON serialization and deterministic digest replay.
- Added focused red-green coverage for transport identity, authority inputs, payload safety, replay idempotency, model binding, cancellation, resume, and typed stable errors.

### Files Modified
- `corvus/domain/agent_runtime.py` — typed immutable agent-runtime contracts and event digest behavior.
- `corvus/application/ports.py` — `AgentRuntimePort` protocol.
- `corvus/infrastructure/agent_runtimes/` — deterministic simulator and package exports.
- `tests/unit/domain/test_agent_runtime.py` — domain contract and deep-immutability coverage.
- `tests/unit/infrastructure/test_simulated_agent_runtime.py` — simulator replay, cancellation, resume, and substitution coverage.
- `PROJECT_LOG.md` — Task 1 implementation record.

### Assumptions Made (flag these for review)
- `agent_run_idempotency_mismatch` and `provider_binding_model_mismatch` are the stable reason codes for the reviewed simulator substitution failures.
- Serialized payloads may be returned as fresh mutable JSON containers while the validated event's stored payload remains deeply immutable.

### Known Issues / Deferred
- Authority-bound orchestration, proof verification, context-firewall integration, and live provider adapters remain deferred to M2A Task 2 and later tasks.
- This Task 1 simulator proves boundary behavior only and does not grant provider, filesystem, network, credential, budget, or autonomy authority.

### Suggested Next Steps
- Submit the Task 1 commit in a ready pull request for external review.
- Implement Task 2 authority-bound orchestration only after Task 1 review is accepted.

## 2026-07-15 — M2A Task 2 Authority-Bound Agent Runtime Coordinator

### What Was Implemented
- Added strict frozen agent-run authorization request/decision and redacted audit contracts with workspace/project, idempotency, authorization snapshot, handle, request digest, and current kill-switch proof binding.
- Added an authority-gated application coordinator for start, resume, and cancel with exact authorization receipt checks, authorization-before-runtime audit ordering, stable failures, and best-effort outcome audit.
- Exported one canonical agent-run request digest helper and reused it in both the coordinator and deterministic Task 1 simulator.
- Added deterministic application tests covering substitution rejection, stale/over-budget/kill-switch denials, stable start replay, fresh resume proofs, current cancel proofs, runtime errors, audit redaction, and structural protocols.
- Completed M2A Task 2 code, which remains unmerged pending whole-milestone review and the ready PR review gate.

### Files Modified
- `corvus/application/ports.py` — agent-run authorization and redacted audit contracts and protocols.
- `corvus/application/agent_runtime.py` — authority-bound start/resume/cancel coordinator and operation result.
- `corvus/domain/agent_runtime.py` — shared canonical agent-run request digest helper.
- `corvus/infrastructure/agent_runtimes/simulated.py` — reuse of the shared digest helper without changing simulator semantics.
- `tests/unit/application/test_agent_runtime_coordinator.py` — Task 2 RED/GREEN coordinator, contract, audit, and proof-binding coverage.
- `PROJECT_LOG.md` — Task 2 implementation and verification record.

### Assumptions Made (flag these for review)
- None. Scope semantics, reason-code vocabulary, audit shape, and replay metadata behavior were confirmed before implementation.

### Known Issues / Deferred
- No live provider adapter, API/UI wiring, database persistence, Cloud authority, or Team authority is included in Task 2.
- `identical_start_replayed` remains `None` because the Task 1 runtime port exposes stable handle equality but no durable replay metadata.
- M2A remains unmerged until the controller completes whole-milestone verification and the ready PR review gate.

### Suggested Next Steps
- Run the controller-owned milestone-wide suite and complete whole-milestone self-review.
- Submit the combined M2A branch through the ready PR review gate before merge.

## 2026-07-15 — M2A Whole-Milestone Repair, UX Verification, and Documentation

### What Was Implemented
- Repaired all seven Important and three Minor whole-milestone review findings across concrete authorization, provider-binding identity, resume immutability, runtime receipts, event lifecycle and deduplication, secret-field rejection, audit acknowledgements, typed discovery/health, replay metadata, and fail-closed capabilities.
- Reused the canonical capability-intersection and authorization-snapshot verification core through a repository-injectable verified agent-run adapter without adding a second policy engine or a database migration.
- Exercised the real Windows desktop shell through onboarding, Everyday/Developer and Personal/Team profiles, the Cloud Preview boundary, Local connection, and graceful shutdown.
- Replaced the stale README with verified product modes, runtime truth, quick-start commands, security boundaries, review workflow, and honest OpenAI Codex AI-assistance attribution.

### Files Modified
- `README.md` — current product, runtime, setup, verification, scope, PR workflow, and attribution.
- `HACKATHON_STATUS.md` — M2A scope, current automated and Windows UI verification, and explicit durable/runtime limitations.
- `PROJECT_LOG.md` — final repair and verification record.
- M2A runtime, authorization, security, simulator, and tests — review-driven integrity repairs recorded in the preceding M2A entries and commits.

### Assumptions Made (flag these for review)
- OpenAI Codex is credited as an AI-assisted engineering tool only; no GitHub identity or account linkage is fabricated.
- The current feature branch remains unmerged until both the independent internal re-review and the user's external review agents approve the ready PR.

### Known Issues / Deferred
- Live vendor adapters, durable current-state repositories for agent runtime authority families, E2B lifecycle, Google continuity, billing, and production signing remain outside M2A.
- Post-effect audit reconciliation is fail-visible and retryable but does not claim a durable database outbox in this milestone.

### Suggested Next Steps
- Complete the exact-commit whole-M2A re-review and address every finding.
- Push only the feature branch, open a ready PR targeting `main`, and wait for review-agent feedback before merge.

## 2026-07-15 — M2A Whole-Milestone Runtime Integrity Repairs

### What Was Implemented
- Added executable/credential-aware provider binding receipts, immutable resume-request digests, typed scoped discovery/health/start receipts, and fail-closed pre-runtime provider verification.
- Enforced sequenced event lifecycle, provider-event deduplication, tool-call transitions, cursor bounds, and one shared recursive sensitive-field predicate for validation and redaction.
- Added acknowledged tamper-evident audit receipts; authorization audit acknowledgment is mandatory, while a post-effect audit failure returns explicit `agent_run_audit_pending` state with no provider output.
- Added a concrete repository-injectable verified agent-run authorization adapter that reuses the canonical capability evaluator and cryptographic snapshot verifier, then binds current autonomy, provider, credential, budget, and kill-switch receipts.
- Validated runtime-returned start, resume, and cancellation identities and exposed deterministic in-memory simulator replay metadata.

### Files Modified
- `corvus/security.py` — shared public sensitive-field predicate used by redaction and runtime-event validation.
- `corvus/domain/agent_runtime.py` — provider/autonomy digests, immutable request identity, typed discovery/health/start models, and event lifecycle fields.
- `corvus/application/ports.py` — authorization, audit-receipt, and runtime port receipt contracts.
- `corvus/application/agent_runtime.py` — audit acknowledgment, provider preflight, runtime receipt validation, and audit-pending behavior.
- `corvus/infrastructure/agent_runtimes/simulated.py` — scoped typed discovery, provider binding verification, replay metadata, immutable resume checks, and lifecycle enforcement.
- `corvus/infrastructure/agent_run_authorization.py` — verified agent-run authorization adapter over the existing canonical authorization stack.
- `tests/unit/` — focused RED/GREEN coverage for all repaired boundaries.
- `.superpowers/sdd/task-2-report.md` — refreshed repair and verification evidence.
- `PROJECT_LOG.md` — this completion record.

### Assumptions Made (flag these for review)
- None. The provider receipt, proof refresh, event lifecycle, audit acknowledgment, adapter reuse, and stop boundaries were explicitly confirmed before repair work.

### Known Issues / Deferred
- Durable repositories for autonomy grants, credential/budget/kill-switch receipts, provider bindings, and audit-pending reconciliation remain later infrastructure work; this task provides repository-injectable contracts and pure verification behavior.
- No live provider/API/UI wiring, database migration, new dependency, Cloud/Team scope, README change, push, merge, or history rewrite was performed.

### Suggested Next Steps
- Have the controller perform the final whole-milestone review against commits `7cf85ca`, `80d2490`, and `493142f` plus the final verification-record commit.
- Keep M2A unmerged until the ready PR review gate is complete.

## 2026-07-15 — M2A Exact-Commit Re-Review Repairs

### What Was Implemented
- Bound audit acknowledgement into the tamper-evident receipt digest and made every post-authorization exit explicitly audit-pending when its outcome audit is missing or unacknowledged, while retaining the primary reason and opaque handle/cancellation result.
- Expanded autonomy and run contracts with explicit sandbox, tool, effect, provider-spend, Corvus-budget, approval, retry, and turn limits; verified canonical filesystem roots and every approved ceiling before evaluation.
- Replaced arbitrary credential/budget wrapper assertions with optional paired receipts derived deterministically from canonical authorization claims and full authoritative verification evidence; absent claims require absent wrappers.
- Added distinct per-effect authorization decision receipts to tool/approval events and included them in event digests and simulator chain materialization.
- Made empty simulator templates synthesize a deterministic `STARTED` event so cancellation preserves `STARTED → CANCELLED` lifecycle ordering.

### Files Modified
- `corvus/application/ports.py` — acknowledgement-bound audit receipts and optional canonical proof receipts.
- `corvus/application/agent_runtime.py` — primary failure retention and audit-pending behavior for every post-authorization exit.
- `corvus/domain/agent_runtime.py` — explicit autonomy/run limits, optional proof pairs, and per-effect authorization references.
- `corvus/infrastructure/agent_run_authorization.py` — canonical evidence receipt derivation and complete autonomy-envelope enforcement.
- `corvus/infrastructure/agent_runtimes/simulated.py` — effect receipt propagation and deterministic empty-template start lifecycle.
- `tests/unit/` — RED/GREEN regressions for receipt tampering, pending outcomes, autonomy/evidence binding, effect receipts, and empty-template cancellation.
- `.superpowers/sdd/task-2-report.md` — exact-commit repair evidence.
- `PROJECT_LOG.md` — corrected simulator durability wording and this completion record.

### Assumptions Made (flag these for review)
- None. Result fields, autonomy/request shapes, canonical evidence behavior, effect receipt fields, empty-template behavior, and stop boundaries were explicitly confirmed.

### Known Issues / Deferred
- Replay metadata remains deterministic and in-memory in the simulator; durable replay persistence remains later infrastructure work.
- Durable authority/evidence repositories and audit-pending reconciliation remain deferred infrastructure work.
- No push, merge, README, dependency, migration, live provider/API/UI/database, Cloud/Team, or unrelated refactor work was performed.

### Suggested Next Steps
- Re-review exact commits `9f7c57d`, `3759837`, and `f2eaf5a` plus the final verification/log commit.
- Keep M2A unmerged until the controller-owned ready PR review gate succeeds.

## 2026-07-15 — M2A Receipt and Tool-Chain Re-Review Repairs

### What Was Implemented
- Added one coordinator receipt verifier that independently recomputes every returned audit receipt digest and uses constant-time comparisons for both event and receipt digests before accepting authorization or outcome acknowledgement.
- Added adversarial start, resume, and cancel coverage for forged authorization and forged outcome receipts created by bypassing Pydantic validation with `model_copy`.
- Added a public, typed, side-effect-free `validate_agent_run_event_chain` domain validator for stream identity, sequencing, digest linkage, terminal state, provider-event deduplication, tool prerequisites, and effect-authorization consistency.
- Enforced one effect authorization decision reference across each tool call lifecycle; standalone approvals remain valid, while tool-bound approvals must follow a request and match its decision reference.
- Made the simulator consume the shared chain validator and preserve the stable `tool_effect_authorization_mismatch` failure reason.

### Files Modified
- `corvus/application/agent_runtime.py` — constant-time independent verification of authorization and outcome audit receipts.
- `corvus/domain/agent_runtime.py` — public event-chain validator and typed chain error.
- `corvus/infrastructure/agent_runtimes/simulated.py` — shared validator integration.
- `tests/unit/application/test_agent_runtime_coordinator.py` — six forged-receipt operation/phase regressions.
- `tests/unit/domain/test_agent_runtime.py` — tool lifecycle decision-substitution and approval relationship coverage.
- `tests/unit/infrastructure/test_simulated_agent_runtime.py` — shared-validator integration regression.
- `.superpowers/sdd/task-2-report.md` — third bounded repair evidence.
- `PROJECT_LOG.md` — this completion record.

### Assumptions Made (flag these for review)
- None. Constant-time receipt verification, all six adversarial cases, standalone versus tool-bound approval behavior, shared domain validator placement, reason code, and stop boundaries were explicitly confirmed.

### Known Issues / Deferred
- Durable audit persistence/reconciliation and live-adapter consumption of the public chain validator remain later infrastructure work.
- No push, merge, README, dependency, migration, live provider/API/UI/database, Cloud/Team, or unrelated refactor work was performed.

### Suggested Next Steps
- Re-review exact commits `f340447` and `1479d59` plus the final verification/log commit.
- Keep M2A unmerged until the controller-owned ready PR review gate succeeds.

## 2026-07-15 — M2A Final Quality Review Repairs

### What Was Implemented
- Bound verified HTTP runs to the exact canonical credential reference and singleton credential grant, while preserving credentialless local CLI runs.
- Added required budget unit/requested amount fields, a public runtime-limit digest over both spend ceilings and the complete runtime envelope, mandatory canonical budget evidence for every verified run, and a required autonomy output-byte ceiling.
- Required outcome audit receipts to continue the authorization receipt exactly, made malformed receipts fail closed, and mapped unsafe runtime cancellation reasons to `agent_run_cancellation_reason_invalid` without losing the opaque cancellation result.
- Rejected terminal event chains with unresolved tool calls and reuse of one effect decision across different tool calls; expanded nested sensitive-field detection and made only text capability default to supported.

### Files Modified
- `corvus/domain/agent_runtime.py` — budget/runtime digest contracts, output-byte grant ceiling, capability default, and event-chain invariants.
- `corvus/infrastructure/agent_run_authorization.py` — exact credential, mandatory budget, runtime-digest, and byte-ceiling enforcement.
- `corvus/application/agent_runtime.py` — audit receipt continuity, malformed-receipt handling, and safe cancellation-reason mapping.
- `corvus/security.py` — additional credential/private-key/signing-key/passphrase field variants.
- `tests/unit/` — RED/GREEN regressions for every repaired boundary.
- `HACKATHON_STATUS.md` — exact rerun count/result correction only.
- `.superpowers/sdd/task-2-report.md` — fourth bounded repair evidence.
- `PROJECT_LOG.md` — this completion record.

### Assumptions Made (flag these for review)
- None. Credential topology, budget semantics, receipt continuity, cancellation behavior, event-chain rules, sensitive variants, capability default, documentation limits, and stop boundaries were explicitly confirmed.

### Known Issues / Deferred
- Durable authority/evidence repositories and audit-pending reconciliation remain later infrastructure work.
- No push, merge, README, dependency, migration, live provider/API/UI/database, Cloud/Team, history rewrite, or unrelated refactor was performed.

### Suggested Next Steps
- Re-review exact commits `415920a`, `224f65a`, and `5c81932` plus the final verification/log commit.
- Keep M2A unmerged until the controller-owned ready PR review gate succeeds.

## 2026-07-15 — M2A Credentialless Local Placement Repair

### What Was Implemented
- Corrected canonical credential evidence presence detection so a valid execution placement alone does not create a credential claim for a credentialless local CLI run.
- Preserved exact placement binding whenever real provider/credential/grant claims exist, including fail-closed partial claim handling and mandatory HTTP credential evidence.
- Added a verified-adapter regression covering canonical budget evidence, a valid execution placement, no credential reference/grant/proof, and an allowed local CLI result.

### Files Modified
- `corvus/infrastructure/agent_run_authorization.py` — distinguish actual credential claims from the placement that binds them.
- `tests/unit/application/test_authorization.py` — local CLI placement regression while retaining HTTP and partial-claim coverage.
- `.superpowers/sdd/task-2-report.md` — final bounded repair RED/GREEN and verification evidence.
- `PROJECT_LOG.md` — this completion record.

### Assumptions Made (flag these for review)
- None. Credential-presence semantics, retained HTTP/partial-claim behavior, verification scope, and stop boundaries were explicitly confirmed.

### Known Issues / Deferred
- Durable authority/evidence repositories and audit-pending reconciliation remain later infrastructure work.
- No push, merge, README, HACKATHON status, dependency, migration, live provider/API/UI/database, Cloud/Team, history rewrite, or unrelated refactor was performed.

### Suggested Next Steps
- Re-review the final credential-presence repair commit together with `415920a`, `224f65a`, `5c81932`, and `cd19279`.
- Keep M2A unmerged until the controller-owned final repository/web/desktop gates and ready PR review complete.

## 2026-07-15 — M2A Review-Gated Pull Request Handoff

### What Was Implemented
- Re-ran the complete local release matrix after the final credentialless-placement repair: 604 Python tests, 23 web tests plus production build, and Windows desktop `cargo check` all passed.
- Obtained an independent final READY review with no Critical, Important, or Minor findings.
- Published `codex/main-integration` and opened ready, non-draft pull request #1 against `main` for the user's code-review agents.
- Preserved the explicit review gate: the pull request was not merged and `main` remained at `f95a814`.

### Files Modified
- `PROJECT_LOG.md` — record the verified, review-gated GitHub handoff.

### Assumptions Made (flag these for review)
- None. The user explicitly requested a ready pull request targeting `main`, no automatic merge, and follow-up repairs after review-agent findings.

### Known Issues / Deferred
- GitHub certification checks were still running when the pull request was opened.
- Live provider adapters, Google identity, E2B Cloud lifecycle, payments, database migrations, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Allow the user's review agents and GitHub certification to complete on pull request #1.
- Address confirmed review findings on `codex/main-integration`, reverify, and update the pull request before any merge decision.

## 2026-07-15 — PR #1 Cross-Platform and Deterministic-Digest Repairs

### What Was Implemented
- Replaced the Windows-only root in the canonical-current-state authorization test with pytest's resolved cross-platform temporary root, fixing the shared Ubuntu and macOS certification failure without weakening production absolute-root validation.
- After the first remote rerun exposed two later Windows-only adversarial path values in the same test, derived both the outside-root substitution and local executable identity from the resolved pytest root; no `Path("C:/...")` literals remain in that file.
- Added JSON-only sorted serialization for every digest-bearing `AutonomyGrant` frozenset and `AgentRunRequest.requested_effect_classes`, eliminating cross-process hash-seed digest drift while preserving Python-mode frozensets.
- Replaced exception-driven missing-provider lookup with explicit `None` handling that returns the existing fail-closed `agent_run_provider_unavailable` reason.
- Added RED/GREEN regressions for deterministic serialization, Python-mode preservation, and missing-provider audit behavior.

### Files Modified
- `corvus/domain/agent_runtime.py` — deterministic JSON serializers for digest-bearing frozensets.
- `corvus/application/agent_runtime.py` — explicit missing-provider preflight handling.
- `tests/unit/domain/test_agent_runtime.py` — deterministic serialization and Python-mode preservation coverage.
- `tests/unit/application/test_agent_runtime_coordinator.py` — missing-provider preflight and audit regression.
- `tests/unit/application/test_authorization.py` — cross-platform canonical-root fixture.
- `HACKATHON_STATUS.md` — current full and expanded verification counts.
- `PROJECT_LOG.md` — this review-repair record.

### Assumptions Made (flag these for review)
- None. The user explicitly approved all four repairs and the Linux/macOS CI fix; the production absolute-root rule, failure reason, PR-only push, and no-merge boundary remain unchanged.

### Known Issues / Deferred
- GitHub certification must rerun on the pushed repair commit before the cross-platform failures are considered remotely closed.
- CodeRabbit and Copilot reviews remain quota-limited; live providers, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push the verified repair to `codex/main-integration`, reply to and resolve the three Gemini review threads, and recheck every GitHub certification job.
- Keep pull request #1 open and unmerged until the user's review gate is satisfied.

## 2026-07-15 — PR #1 Full Review Repair Pass

### What Was Implemented
- Closed all 12 unique Codex review findings, including the 10 duplicated follow-up comments: usage token counters no longer trigger secret-key rejection, while nested secret-shaped values remain fail-closed.
- Preserved event-chain integrity by recomputing every event digest and deterministically closing open tool calls before cancellation.
- Made cancellation independent of volatile provider health, rejected non-terminal provider refusals as failures, and returned a canonical cancelled handle after accepted terminal cancellation.
- Enforced logical run identity across changed idempotency keys, required verified provider capabilities for requested execution envelopes and resume, and rejected unsupported nested scopes until an ancestry resolver exists.
- Removed volatile provider health observations from the binding authorization digest and rechecked queued deadlines plus autonomy issue times at authorization time.
- Added RED/GREEN regressions for every repaired boundary and independently reproduced every review finding before implementation.

### Files Modified
- `corvus/security.py` — safe usage-counter classification without weakening secret-name detection.
- `corvus/domain/agent_runtime.py` — stable binding digests, secret-value rejection, and event-chain digest verification.
- `corvus/infrastructure/agent_runtimes/simulated.py` — logical run uniqueness and cancellation-safe tool lifecycle closure.
- `corvus/application/agent_runtime.py` — capability-honest preflight and correct cancellation semantics.
- `corvus/application/ports.py` — fail-closed unsupported nested agent-run scopes.
- `corvus/infrastructure/agent_run_authorization.py` — authorization-time deadline and grant-issuance checks.
- `tests/unit/` — focused contract, simulator, coordinator, and authorization regressions.
- `HACKATHON_STATUS.md` — exact current verification counts.
- `PROJECT_LOG.md` — this repair record.

### Assumptions Made (flag these for review)
- None. The user approved the complete unresolved review pass; capability downgrade, scope, cancellation, digest, time-window, redaction, idempotency, PR-only push, and no-merge behavior were validated against the existing plan and contracts.

### Known Issues / Deferred
- The provider-binding digest intentionally changed to exclude only `status` and `health_checked_at`; in-flight pre-repair binding proofs must be regenerated rather than silently accepted.
- GitHub certification must rerun on the repair commit before the remote macOS, Linux, Windows, and Docker gates are considered current.
- Live provider adapters, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push this verified repair to `codex/main-integration`, respond to every duplicated review thread with evidence, and resolve only the findings demonstrably closed by the pushed commit.
- Keep pull request #1 open and unmerged until the user's review agents approve it.

## 2026-07-15 — PR #1 Post-Review Quality Sweep

### What Was Implemented
- Rechecked the live pull request after the prior repair commit and confirmed there were no new GitHub comments or unresolved threads, then completed two independent read-only security and portability reviews.
- Closed seven additional reproduced defects: Digest and bare Bearer/Basic credentials are rejected from event payloads; authorization decisions fail closed when evaluated in the future or at/after the run deadline; operation-specific authorization fields cannot be smuggled into START, RESUME, or CANCEL.
- Canonicalized semantically equal Decimal and timezone-offset values before hashing without mutable Decimal-context rounding, kept extreme exponents compact, rejected blank or oversized message inputs, and prevented `TOOL_BLOCKED` from closing an already-started tool call in both shared and simulator lifecycle validation.
- Added RED/GREEN regressions for every repaired boundary and reran Python, web, dependency, lint, type, patch, and desktop compilation checks.

### Files Modified
- `corvus/security.py` — conservative Authorization plus bare Bearer/Basic credential redaction.
- `corvus/application/agent_runtime.py` — coordinator-clock and run-deadline validation for authorization decisions.
- `corvus/application/ports.py` — operation-specific authorization request field hygiene.
- `corvus/domain/agent_runtime.py` — canonical proof digests, bounded message input, and valid tool lifecycle transitions.
- `corvus/infrastructure/agent_runtimes/simulated.py` — simulator template parity for started-tool closure.
- `tests/unit/application/test_agent_runtime_coordinator.py` — decision-time, clock-failure, and field-smuggling regressions.
- `tests/unit/domain/test_agent_runtime.py` — credential, digest, message-bound, and shared lifecycle regressions.
- `tests/unit/infrastructure/test_simulated_agent_runtime.py` — simulator lifecycle regression.
- `HACKATHON_STATUS.md` — current verification counts.
- `PROJECT_LOG.md` — this post-review repair record.

### Assumptions Made (flag these for review)
- None. The user explicitly authorized all remaining evidence-backed repairs while preserving the PR-only push and no-merge review boundary.

### Known Issues / Deferred
- Canonical agent-runtime proof digests intentionally changed for semantically equal Decimal scales and timezone offsets; any in-flight pre-repair proofs must be regenerated instead of silently accepted.
- GitHub certification must rerun on the pushed commit before the remote macOS, Linux, Windows, and Docker gates are current.
- Live provider adapters, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push the verified sweep to `codex/main-integration`, leave evidence on pull request #1, and monitor every remote certification job.
- Keep pull request #1 open and unmerged until the user's review agents approve it.

## 2026-07-15 — Asif Security-Owner Review Follow-Up

### What Was Implemented
- Validated Asif's three mandatory PR follow-ups against the current head instead of applying a stale change mechanically.
- Confirmed the differing-idempotency-key scenario is already fail-closed: the simulator indexes logical `(run_id, binding_id)`, raises `agent_run_idempotency_mismatch`, creates no second handle, and the exact existing regression passes.
- Added a dedicated `tests/unit/test_security.py` module covering registered, keyed, and bare secret redaction; token-usage safe-list classification; and absolute/parent path-traversal rejection.
- Added `.github/CODEOWNERS` routing security-critical authority, runtime, redaction, sandbox, and certification-test surfaces to `@asifdotpy`.
- Enabled `main` branch protection with strict required certification checks, admin enforcement, one approving review, code-owner review, stale-review dismissal, conversation resolution, and force-push/deletion denial.

### Files Modified
- `.github/CODEOWNERS` — security-owner routing for critical implementation and test paths.
- `tests/unit/test_security.py` — direct security-core unit coverage requested by the reviewer.
- `HACKATHON_STATUS.md` — current full and dedicated-security verification counts.
- `PROJECT_LOG.md` — this security-owner review follow-up record.

### Assumptions Made (flag these for review)
- None. The user explicitly requested that Asif's review be inspected and fixed; the idempotency behavior was preserved because live code and an exact regression disproved that stale finding.

### Known Issues / Deferred
- The CODEOWNERS file is part of pull request #1 and becomes base-branch ownership policy only after this reviewed PR is merged; branch protection is already active and requires an approval now.
- Asif must re-review the latest pushed commit before the existing `CHANGES_REQUESTED` state is cleared.
- Live provider adapters, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push the verified follow-up to `codex/main-integration`, reply to Asif with evidence for all three items, and monitor the newly required certification checks.
- Keep pull request #1 open and unmerged until Asif approves the latest head.

## 2026-07-15 — Final Automated Review Repairs

### What Was Implemented
- Closed Gemini's multi-word credential leak by redacting unquoted sensitive assignments through the line boundary while preserving following lines.
- Migrated agent-runtime discovery and health checks to asynchronous port operations so future database, local-process, and network adapters cannot block the coordinator event loop.
- Removed the redundant payload thaw/copy from secret-value inspection and retained fail-closed scalar validation plus distinct secret-key and secret-value reason codes.
- Added test-first regressions for all three review findings and observed each fail before the production repair.
- Reproduced the post-push Ubuntu/macOS failure as a Ruff formatting-only mismatch in the new security test and normalized that file; all remote Python tests had already passed.
- Closed the follow-up naive-clock defect by rejecting timezone-naive coordinator clocks inside the fail-closed authorization boundary before audit or runtime execution.
- Made timezone-aware historical agent-run requests deserializable while retaining deadline enforcement at authorization time, preserving both archival fidelity and time-of-use safety.
- Added exact safe classifications for provider token-usage counters/details while deliberately retaining generic `tokens` as sensitive credential-bearing data.
- Replaced full provider-binding equality in simulator lookup with the established canonical digest, accepting health-only refreshes while retaining every stable identity, scope, capability, executable/credential, model, version, and disclosure boundary.
- Enforced the request deadline against current coordinator time so an earlier valid authorization decision cannot start or resume an already expired run.
- Canonicalized credential and budget evidence receipts from Python-native values, making equivalent timezone offsets digest-identical while preserving semantic changes.
- Converted protocol-violating null start/resume/cancel adapter results into the existing operation-specific fail-closed outcomes and audit records.
- Required exact typed start, resume, and cancel results from runtime adapters, mapping arbitrary protocol-violating objects to the same audited operation-specific failures.
- Rejected non-canonical executable identities instead of silently normalizing them, preserving exact provider-binding evidence and preventing alternate path spellings from crossing the runtime boundary.
- Preserved kill-switch cancellation after ordinary autonomy deadlines and budget/runtime consumption limits expire, while retaining authority, credential, binding-digest, current-proof, capability, and audit checks.
- Rejected approval events for tool calls that have already reached a blocked or result terminal state, preserving causal effect authorization in replay and audit streams.
- Redacted quoted JSON-style secret assignments without corrupting valid provider JSON or missing credential assignments embedded inside already-parsed log strings.
- Required verified provider-side cancellation capability before authorizing emergency cancellation, while continuing to tolerate unavailable health status for the stop path.
- Rejected secret-shaped mapping keys as well as sensitive field names before freezing agent-run event payloads.
- Revalidated every declared authorization-decision field at the coordinator port boundary before trusting an allow result.
- Bound nested cancellation-result handles to the exact cancelled handle identity and withheld malformed adapter results from failure responses.

### Files Modified
- `corvus/security.py` — fail-closed multi-word and quoted-key secret assignment redaction with valid JSON-string preservation.
- `corvus/domain/agent_runtime.py` — allocation-free recursive secret inspection across keys and values, shared canonical evidence-value normalization, canonical executable identity enforcement, and causal tool-approval ordering.
- `corvus/application/authorization.py` — exact agent-run cancellation exemption from budget/runtime consumption denial.
- `corvus/application/ports.py` — asynchronous discovery and health contracts.
- `corvus/application/agent_runtime.py` — awaited provider preflight, cancellation-safe deadline binding, revalidated authorization decisions, exact typed-result enforcement, and exact cancellation handle identity.
- `corvus/infrastructure/agent_run_authorization.py` — canonical credential and budget evidence receipts plus narrowly scoped emergency-cancellation liveness and capability handling.
- `corvus/infrastructure/agent_runtimes/simulated.py` — asynchronous simulator parity and stable-digest binding lookup.
- `tests/unit/test_security.py` — multi-word and quoted JSON-style credential regressions.
- `tests/unit/domain/test_agent_runtime.py` — no-thaw payload scan, secret-shaped key, historical deserialization, structured usage-metadata, non-canonical executable-path, and late tool-approval regressions.
- `tests/unit/infrastructure/test_simulated_agent_runtime.py` — asynchronous runtime contract and volatile health-refresh regressions.
- `tests/unit/application/test_agent_runtime_coordinator.py` — async tracing adapter plus clock, expired-request, emergency-cancellation, malformed authorization, exact cancellation identity, null-result, and malformed typed-result fail-closed regressions.
- `tests/unit/application/test_authorization.py` — authorization-time deadline revalidation, cancellation capability/consumption boundaries, and equivalent-timezone evidence receipt regressions.
- `HACKATHON_STATUS.md` — current verification evidence.
- `PROJECT_LOG.md` — this review-repair record.

### Assumptions Made (flag these for review)
- Unquoted sensitive assignments are intentionally redacted through end-of-line; safe over-redaction is preferred to leaking a multi-word credential.
- `capabilities()` remains synchronous because the reviewed blocking-I/O concern was limited to discovery and health, and current capability reports are immutable binding metadata.
- Provider status and health timestamps remain runtime observations outside the stable binding digest and are validated separately before execution.
- Runtime adapters are typed as returning non-null contracts; defensive null handling maps violations to the existing operation-specific failure codes rather than inventing new public reasons.
- No unsigned five-minute clock-skew allowance was introduced. The established security regression rejects authorization decisions even one microsecond in the future, so tolerance remains deferred until a signed and explicitly configured skew policy exists.
- Cancellation bypasses only run-liveness, provider-health status, and budget/runtime consumption gates; revoked autonomy, future-issued grants, scope, identity, credential, provider binding, current kill-switch proof, capability, snapshot, and audit requirements remain fail-closed.

### Known Issues / Deferred
- CodeRabbit accepted the final review request but its hosted reviewer was rate-limited; the existing CodeRabbit status on the reviewed head remained successful.
- Live provider adapters, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push the verified repairs, reply to and resolve all three Gemini threads, and re-request the final automated reviews on the new head.
- Merge pull request #1 only after the new cross-platform certification matrix, conversation-resolution gate, and required code-owner approval are current.
