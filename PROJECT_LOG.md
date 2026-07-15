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

## 2026-07-15 — PR #2 Security Governance Review Repairs

### What Was Implemented
- Expanded CODEOWNERS to preserve the union of PR #2's authority/sandbox coverage and PR #1's runtime plus dedicated security-test coverage.
- Protected the CODEOWNERS file itself and added the omitted audit, recovery, registry, database, domain, runtime, and authorization trust-root paths identified by Gemini and Codex.
- Replaced the misleading required-CI secret-scan claim with a truthful manual evidence requirement until a dedicated required job exists.
- Removed stale commit-specific language from the guardrail checklist and threat model while preserving the verified PR #1 review history.
- Verified the repaired governance branch with 461 Python tests, Ruff lint/format, MyPy across 88 source files, diff checks, and validation of all 79 non-redundant ownership rules.
- Removed one redundant ownership rule and replaced hardcoded source line references with stable class, method, and helper names after Gemini's exact-head review.
- Added explicit audit-repository ownership and corrected the formal-approval wording identified in Gemini's final documentation pass.
- Added explicit ownership for the MVP ingress, update-verification, deployment/OIDC, API/session, governance, supply-chain, and matching regression-test trust boundaries identified in Gemini's exact-head review.
- Aligned the threat model with the branch's actual redaction coverage while recording the dedicated `tests/unit/test_security.py` coverage as part of PR #1.
- Protected the required workflow and the remaining provider, sandbox, snapshot, delivery, authority-persistence, MVP execution, and focused regression-test boundaries identified by the final Codex and Gemini exact-head reviews.
- Removed misleading current-branch verification claims for bare credential redaction and the not-yet-merged agent runtime, event chain, replay, and operation-binding contracts.
- Corrected the review-gate guidance so only a persisted formal approval from an eligible reviewer satisfies protected-branch and CODEOWNERS requirements.
- Ran checksum-verified Gitleaks 8.30.1 scans over the staged final repair and the seven-commit PR range; both reported no leaks.
- Added the final MVP server-adapter, V1 context/store firewall, root security-review document, and matching regression-test routes from Codex's late prior-head review; clarified that protected `main` must require Code Owner review.
- Added the executable MVP package initializer to security ownership and removed a redundant checklist conjunction identified by Gemini's exact-head pass.

### Files Modified
- `.github/CODEOWNERS` — complete security-owner routing, MVP trust-boundary coverage, and self-protection.
- `.github/GUARDRAIL_CHECKLIST.md` — commit-independent review evidence language.
- `.github/THREAT_MODEL.md` — commit-independent stale-review warning.
- `SECURITY_REVIEW.md` — explicit authorization/MVP-core coverage, truthful secret-scan gate, and branch-protection dependency.
- `PROJECT_LOG.md` — this repair record.

### Assumptions Made (flag these for review)
- Broader code-owner routing is intentionally conservative; requiring Asif review on the complete domain directory is preferable to leaving a trust-boundary model unowned.
- Secret scanning remains a documented manual review step until a separately reviewed CI implementation is added and made required.

### Known Issues / Deferred
- PR #1 still requires a fresh formal Asif approval on its current head; a Discord verdict or PR comment does not satisfy GitHub branch protection.
- A dedicated automated secret-scanning job remains deferred rather than being implied by documentation.
- The dedicated `tests/unit/test_security.py` test remains on PR #1 until that integration branch is merged.
- The seven agent-runtime and dedicated-security-test CODEOWNERS routes intentionally pre-own PR #1 paths that are absent from PR #2's base.

### Suggested Next Steps
- Verify, commit, and push the final PR #2 repairs; reply to and resolve all exact-head review threads.
- Obtain the required owner review, merge PR #2 normally, then refresh PR #1 against protected `main` and request Asif's exact-head approval.
