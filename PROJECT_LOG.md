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

## 2026-07-15 — Final Codex Review Trust-Boundary Repairs

### What Was Implemented
- Bound emergency cancellation to the complete current kill-switch proof pair: both proof ID and proof digest now cross the runtime port, are validated for replay, and appear in cancellation and synthetic tool-close evidence.
- Revalidated nested start, resume, and cancellation handles before the coordinator trusts adapter output; malformed nested identities or states now fail closed through the established operation-specific audit paths.
- Rejected terminal cancellation results carrying a non-terminal nested handle before a success audit can be recorded.
- Added an explicit numeric safe list for provider-native camelCase usage counters while retaining fail-closed handling for generic secret-shaped token keys.
- Added test-first regressions for all four Codex findings and reran the complete repository Python certification commands against the final formatted files.
- Reused one private read-only empty `SecretRedactor` for event payload key/value scans, eliminating per-call construction without introducing a mutable default argument; the regression reproduced Gemini's performance finding before the repair.
- Made an already-active simulator event iterator observe contiguous events appended before that iterator completes, so a concurrent cancellation terminal event is not omitted from the open stream.

### Files Modified
- `corvus/application/ports.py` — cancellation port contract now carries the current proof digest.
- `corvus/application/agent_runtime.py` — nested runtime-result reconstruction, validation, and stable cancellation identity failure mapping.
- `corvus/infrastructure/agent_runtimes/simulated.py` — proof-pair validation, replay binding, cancellation evidence parity, and active-iterator continuity.
- `corvus/security.py` — explicit provider-native camelCase token-usage counters.
- `corvus/domain/agent_runtime.py` — private reusable payload redactor for key and scalar-value scans.
- `tests/unit/application/test_agent_runtime_coordinator.py` — malformed nested start and terminal cancellation-handle regressions.
- `tests/unit/domain/test_agent_runtime.py` — per-call redactor-construction regression.
- `tests/unit/infrastructure/test_simulated_agent_runtime.py` — proof digest evidence, mismatched replay, and concurrent append visibility regressions.
- `tests/unit/test_security.py` — camelCase usage-counter regression.
- `HACKATHON_STATUS.md` — exact final Python verification evidence.
- `PROJECT_LOG.md` — this repair record.

### Assumptions Made (flag these for review)
- The duplicated CodeRabbit reviewer name in the user request refers to the previously agreed fourth automated reviewer, Copilot; both CodeRabbit and Copilot are requested on the exact pushed head.
- No cancellation proof compatibility shim is added: callers must provide the complete current proof pair so evidence cannot silently weaken across the runtime boundary.
- Gemini's literal default-argument suggestion was implemented as an equivalent private module-scoped instance so the optimization does not add a mutable function default.
- Missing or misspelled capability attributes remain invalid adapter output and are already caught by the provider-preflight exception boundary; no permissive attribute default was added.

### Known Issues / Deferred
- Pull request #1 remains subject to strict protected-branch certification, conversation resolution, and a fresh code-owner approval from Asif; no administrator bypass is permitted.
- Live provider adapters, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push this verified repair, reply to the four exact Codex threads with evidence, and request Gemini, CodeRabbit, Codex, Copilot, and Asif review on the new commit.
- Merge pull request #1 only after all exact-head checks pass, no review threads remain unresolved, and GitHub reports the required approval satisfied.

## 2026-07-15 — PR #2 Security Governance Review Repairs

### What Was Implemented
- Expanded CODEOWNERS to preserve the union of PR #2's authority/sandbox coverage and PR #1's runtime plus dedicated security-test coverage.
- Protected the CODEOWNERS file itself and added the omitted audit, recovery, registry, database, domain, runtime, and authorization trust-root paths identified by Gemini and Codex.
- Replaced the misleading required-CI secret-scan claim with a truthful manual evidence requirement until a dedicated required job exists.
- Removed stale commit-specific language from the guardrail checklist and threat model while preserving the verified PR #1 review history.
- Verified the repaired governance branch with 461 Python tests, Ruff lint/format, MyPy across 88 source files, diff checks, and validation of all 62 non-redundant ownership rules.
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
- Repaired the threat model's repository-root and guardrail-checklist links; retained the intentionally plural authorization-inputs repository filename after verifying it stores multiple record types.
- Replaced fragile per-file MVP source/test routes with complete directory ownership and made the remaining threat-model/certification references directly navigable.
- Repaired the guardrail checklist's repository-root plan and evidence-log links.

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

## 2026-07-15 — PR #1 Governance Integration Refresh

### What Was Implemented
- Merged protected `main` after PR #2 into the PR #1 integration branch without discarding either milestone history.
- Resolved CODEOWNERS to PR #2's complete 62-rule policy, which includes every PR #1 runtime and dedicated-security-test path.
- Preserved the full PR #1 runtime/security implementation and both project-log histories.
- Verified the merged tree with 680 Python tests, Ruff lint/format, MyPy across 93 source files, complete ownership-target validation, and conflict-marker checks.

### Files Modified
- `.github/CODEOWNERS` — retained the complete merged security-owner policy.
- `.github/GUARDRAIL_CHECKLIST.md` — integrated the merged security review checklist.
- `.github/THREAT_MODEL.md` — integrated the merged threat model.
- `SECURITY_REVIEW.md` — integrated the protected-branch security gate checklist.
- `PROJECT_LOG.md` — preserved both histories and recorded this integration refresh.

### Assumptions Made (flag these for review)
- PR #2's complete directory-aware ownership policy supersedes PR #1's narrower policy because it contains the full PR #1 ownership subset.

### Known Issues / Deferred
- The merge commit requires a fresh exact-head certification run and formal Asif code-owner approval because protected-branch stale-review dismissal applies after the head changes.
- Live provider adapters, E2B Cloud lifecycle, Google identity, payments, durable runtime repositories, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Commit and push the verified integration merge, request exact-head reviewers, and merge PR #1 only after protected-branch requirements are satisfied.

## 2026-07-15 — Alpha Installers and Vercel Release Path

### What Was Implemented
- Added a release-only Tauri packaging config that bundles the compiled React client and a standalone PyInstaller `corvus-mvp` sidecar without weakening the existing local sidecar override.
- Added a GitHub Actions desktop-release workflow for unsigned Windows NSIS, macOS x64 DMG, Linux AppImage, and Linux `.deb` artifacts, with tag-gated GitHub prerelease publishing and SHA256 checksums.
- Added the hosted-web Local handoff so Vercel never receives same-machine pairing secrets or local session cookies.
- Linked Vercel project `corvus-platform` to `aGamingGod1234/corvus-platform`, connected GitHub integration, set Git root to `apps/web`, and deployed the current web app to `https://corvus-platform-tau.vercel.app`.
- Confirmed GitHub `main` protection is already enabled with strict required checks, one code-owner approval, stale-review dismissal, admin enforcement, and force/delete disabled.

### Files Modified
- `.github/workflows/desktop-release.yml` — cross-platform unsigned installer build and tag-gated prerelease publishing.
- `.gitignore` — ignores local Vercel project metadata.
- `apps/desktop/src-tauri/src/lib.rs` — packaged sidecar lookup now checks both resource and installed executable directories.
- `apps/desktop/src-tauri/tauri.conf.json` — declares desktop icons for release bundling.
- `apps/desktop/src-tauri/tauri.release.conf.json` — release-only sidecar and resource packaging config.
- `apps/desktop/src-tauri/icons/icon.icns` — generated macOS desktop icon from the existing app SVG.
- `apps/desktop/README.md` — documents the standalone unsigned alpha installer build.
- `apps/web/src/App.tsx`, `apps/web/src/runtime/*`, `apps/web/src/styles/onboarding.css`, `apps/web/src/App.workspace.test.tsx` — hosted Local handoff and tests.
- `apps/web/vercel.json` — Vercel Vite build, SPA rewrite, and security headers.
- `scripts/corvus_mvp_entry.py` — PyInstaller entrypoint for the MVP sidecar.
- `README.md`, `HACKATHON_STATUS.md`, `PROJECT_LOG.md` — release/deployment status and limitations.

### Assumptions Made (flag these for review)
- Unsigned alpha artifacts are acceptable for this milestone; production signing, notarization, and update channels are intentionally deferred.
- GitHub Releases should be created only from reviewed `main` tags, not directly from this feature branch.
- Hosted Vercel Local mode should remain a launcher/handoff for same-machine runtime until a real cloud runtime and browser-safe local bridge are designed.

### Known Issues / Deferred
- GitHub Release assets require a reviewed tag push from `main`; the macOS alpha artifact is x64 because a locked dependency is not universal2-compatible in PyInstaller.
- The Computer Use control surface was not exposed in this resumed tool set, so current Windows installer validation used process-level smoke testing instead of GUI automation.
- Vercel direct deployment briefly required clearing `rootDirectory`; it was restored to `apps/web` after deployment for GitHub `main` auto-deploys.
- Real E2B Cloud, Google-backed continuity, payments, production signing, notarization, live provider adapters, and real multi-user authority remain later milestones.

### Suggested Next Steps
- Push this branch and open a ready PR targeting `main` for review.
- After review and merge, tag `v0.2.0-alpha.1` on `main` so the release workflow publishes installer assets and checksums.
- Verify the GitHub Actions macOS and Linux installer artifacts before treating them as downloadable alpha builds.

## 2026-07-15 — Alpha Release Review Hardening

### What Was Implemented
- Made packaged sidecar discovery skip directory lookalikes and continue to the next trusted candidate.
- Made loopback host classification reject missing or non-string runtime values without throwing.
- Required every release tag commit to be an ancestor of `origin/main` before GitHub prerelease publication.
- Removed redundant native-sidecar bundling because the desktop runtime uses the explicit packaged-resource lookup.

### Files Modified
- `apps/desktop/src-tauri/src/lib.rs` — file-only packaged sidecar selection plus regression coverage.
- `apps/web/src/runtime/localRuntime.ts` and `localRuntime.test.ts` — defensive runtime-host validation and regression coverage.
- `.github/workflows/desktop-release.yml` — reviewed-main ancestry gate for release tags.
- `apps/desktop/src-tauri/tauri.release.conf.json` — avoids packaging the sidecar twice.
- `PROJECT_LOG.md` — this hardening record.

### Assumptions Made (flag these for review)
- Tags may point at any reviewed commit reachable from `main`; they do not need to point only at the current `main` tip.

### Known Issues / Deferred
- Broader CODEOWNERS coverage for release, desktop, and scripts paths remains a separate governance change so this release fix stays narrowly reviewable.

### Suggested Next Steps
- Re-run focused and full verification, obtain exact-head approval, merge PR #3, and tag `v0.2.0-alpha.1` from updated `main`.

## 2026-07-16 — Complete PR #3 code-owner coverage

### What Was Implemented
- Extended required security review ownership to the desktop application and all release-support scripts.

### Files Modified
- `.github/CODEOWNERS` — enforces `@asifdotpy` review for `apps/desktop/` and `scripts/`.
- `PROJECT_LOG.md` — records the governance follow-up.

### Assumptions Made (flag these for review)
- `@asifdotpy` remains the security owner for the alpha release surface.

### Known Issues / Deferred
- A fresh formal approval is still required because branch protection dismisses stale reviews after new commits.

### Suggested Next Steps
- Push the PR-head update, request Asif's review, and merge only after the protected-branch gate is satisfied.

## 2026-07-16 — Close PR #3 release security blockers

### What Was Implemented
- Removed pull-request-triggered multi-OS installer packaging while preserving manual and release-tag builds.
- Pinned the alpha Vercel network contract to same-origin API and streaming connections.
- Disclosed that the alpha loopback handoff cannot authenticate the process owning port 8080.
- Added regression coverage for the packaging trigger, CSP contract, and visible trust disclosure.

### Files Modified
- `.github/workflows/desktop-release.yml` — limits packaging to manual dispatch and release tags.
- `apps/web/HOSTED_RUNTIME_SECURITY.md` — documents CSP and loopback trust decisions.
- `apps/web/src/runtime/LocalRuntimeLauncher.tsx` — shows the unverified loopback limitation.
- `apps/web/src/App.workspace.test.tsx` — checks the visible trust disclosure.
- `tests/security/test_release_surface.py` — enforces the release-trigger and hosted-network policies.
- `PROJECT_LOG.md` — records the security follow-up.

### Assumptions Made (flag these for review)
- The alpha hosted surface has no external API, SSE, or WebSocket dependency; future cloud origins require an explicit CSP review.

### Known Issues / Deferred
- Cryptographic local-app identity requires a native bootstrap channel and remains in the runtime-selector milestone.

### Suggested Next Steps
- Run the focused and full verification suites, push the reviewed delta, and request exact-head security approval.

## 2026-07-16 — Complete PR #4 security-scan review repair

### What Was Implemented
- Made Semgrep scan the repository root while writing a real JSON artifact through its dedicated JSON-output option.
- Added regression coverage for the scan target and artifact-output contract.

### Files Modified
- `.github/workflows/security-scan.yml` — uses `--json-output` instead of treating the artifact path as a scan target or writing default text output.
- `tests/security/test_release_surface.py` — guards the Semgrep invocation against both failure modes.
- `PROJECT_LOG.md` — records the review repair.

### Assumptions Made (flag these for review)
- The alpha security workflow should remain inform-only as documented in the PR rather than becoming a merge-blocking Semgrep gate in this repair.

### Known Issues / Deferred
- Action SHA pinning, SARIF upload, dependency auditing, and blocking Semgrep remain the explicitly documented post-alpha hardening work.

### Suggested Next Steps
- Push a verified-account commit, confirm the Vercel author check and GitHub Actions pass, and request final review without merging the PR.

## 2026-07-16 — Harden PR #4 Semgrep regression parsing

### What Was Implemented
- Replaced the order-sensitive Semgrep workflow assertion with shell-token parsing.
- Preserved independent checks for the repository target, JSON-output option, and absence of the prior positional-output failure.

### Files Modified
- `tests/security/test_release_surface.py` — validates Semgrep arguments independently of spacing, quoting, or option order.
- `PROJECT_LOG.md` — records the final review repair.

### Assumptions Made (flag these for review)
- The Semgrep invocation remains a single shell command line in the alpha workflow.

### Known Issues / Deferred
- PR #4 still requires an approving code-owner review under the protected-main policy after this commit.

### Suggested Next Steps
- Push the final repair, resolve the Gemini thread, wait for exact-head checks, and obtain the required code-owner approval before merge.

## 2026-07-16 — Close PR #5 security workflow review findings

### What Was Implemented
- Upgraded the security workflow to the Node 24 releases of checkout and Gitleaks Action.
- Removed Semgrep's shell-level error suppression while retaining the documented inform-only `continue-on-error` policy.
- Made Semgrep command parsing accept block and inline YAML `run:` forms without matching comments or step names.

### Files Modified
- `.github/workflows/security-scan.yml` — upgrades Node runtimes and preserves Semgrep failure visibility.
- `tests/security/test_release_surface.py` — covers action versions, failure propagation, and YAML command forms.
- `PROJECT_LOG.md` — records the final bot-review repair.

### Assumptions Made (flag these for review)
- The repository remains a personal-account repository, so Gitleaks Action v3 does not require an organization license secret.

### Known Issues / Deferred
- Action SHA pinning, SARIF upload, dependency auditing, and blocking Semgrep remain the documented post-alpha hardening work.

### Suggested Next Steps
- Run full verification, push the repair, resolve all bot threads, and obtain fresh code-owner approval before merge.

## 2026-07-16 — Specify the complete Corvus product platform

### What Was Implemented
- Consolidated the seven user-approved design sections into one decision-complete architecture specification.
- Fixed the delivery boundary at seven milestone commits on one branch followed by one unmerged review pull request.
- Documented authoritative state ownership, security invariants, data flow, UX adaptation, error handling, and integrated verification.

### Files Modified
- `docs/superpowers/specs/2026-07-16-corvus-full-product-platform-design.md` — records the approved modular Railway/PostgreSQL control-plane design.
- `PROJECT_LOG.md` — records the design milestone and review gate.

### Assumptions Made (flag these for review)
- None beyond the decisions explicitly approved in the design conversation and recorded in the specification.

### Known Issues / Deferred
- Implementation has not started; the mandatory written-spec review and detailed `PLAN.md` remain the next gates.
- Production database migration, paid billing activation, and automatic PR merge remain outside the authorized boundary.

### Suggested Next Steps
- Complete the specification self-review, commit it, obtain user approval of the written file, and then generate the seven-milestone implementation plan.

## 2026-07-16 — Create the seven-milestone full-product implementation plan

### What Was Implemented
- Added a 735-line executable product plan with 39 red/green tasks across identity, agents, scheduling, settings, teams, runtimes, and final product verification.
- Preserved the previous foundation plan unchanged beneath the new current plan.
- Incorporated backend/frontend planning review corrections so existing workspace, membership, credential, runtime, authorization, and audit types remain authoritative.

### Files Modified
- <code>PLAN.md</code> — adds the current seven-milestone implementation checklist, interfaces, dependencies, tests, commit gates, and one-PR stop boundary.
- <code>PROJECT_LOG.md</code> — records completion and self-review of the plan.

### Assumptions Made (flag these for review)
- The user's prior blanket dependency approval covers the explicitly listed Authlib, psycopg, E2B, recurrence, React product, Playwright, and axe packages.

### Known Issues / Deferred
- No product implementation task has been marked complete yet.
- Live Google, Railway, and E2B credential checks remain environment-gated, while deterministic adapters and local contract tests are required in every case.

### Suggested Next Steps
- Commit the plan, invoke the subagent-driven-development skill, and execute Milestone 1 from its first unchecked task.

## 2026-07-16 — Produce and approve the frontend design packet

### What Was Implemented
- Regenerated the required Antigravity packet from the approved seven-surface Corvus product design.
- Replaced stale unrelated Sitesbuilder content with source-cited identity, conversation, run-flightpath, scheduling, settings/integrations, team-collaboration, and runtime-continuity contracts.
- Recorded fetched and hashed Corvus, T3Code, ChatGPT, shadcn Button, and Lucide Send evidence with explicit adoption and copy boundaries.
- Captured desktop, tablet, and mobile baselines, verified no horizontal overflow or console errors, verified reduced-motion behavior, and locked Lucas's approval hash.

### Files Modified
- `.antigravity/website-blueprint/` — approved design packet, research evidence, adoption map, interaction contract, responsive targets, and baseline screenshots.
- `PROJECT_LOG.md` — records the Task 1.1 design-provenance milestone.
- `.superpowers/sdd/task-1.1-report.md` — records commands, results, self-review, and concerns for the delegated task.

### Assumptions Made (flag these for review)
- None. The approved 2026-07-16 full-product specification and the task brief define the seven surfaces, sources, change boundary, and approval note.

### Known Issues / Deferred
- Product implementation and final after-build visual audit remain deferred to their named frontend milestones.
- The Antigravity research client's direct fetch was blocked by private-repository access and ChatGPT's Cloudflare challenge; authenticated GitHub and browser-readable evidence were captured locally instead.

### Suggested Next Steps
- Review and squash the local Task 1.1 commit into the Milestone 1 commit after the remaining milestone tasks pass.

## 2026-07-16 — Tighten frontend design packet review findings

### What Was Implemented
- Marked Cloud fallback and wake controls as non-rendered until the native runtime selector, real Cloud path, advertised capabilities, and authorized runtime binding exist.
- Kept the Cloud label truthfully Preview throughout the runtime interaction and section contracts.
- Replaced the orphan compatibility interaction with a real, globally mapped Workspace identity details control and mapped Mobile More to global navigation.
- Removed an unrelated duplicate backend Task 1.1 section from the ignored delegated-task brief.
- Reverified the packet, source/citation/orphan contracts, browser evidence, and Lucas approval hash.

### Files Modified
- `.antigravity/website-blueprint/INTERACTION_SPEC.json` — adds explicit Cloud render gates and real global interaction mappings.
- `.antigravity/website-blueprint/SECTION_PLAN.json` — records global shell/navigation interactions and runtime availability truth.
- `PROJECT_LOG.md` — records the review-fix milestone.
- `.superpowers/sdd/task-1.1-brief.md` and `.superpowers/sdd/task-1.1-report.md` — clean ignored task coordination artifacts.

### Assumptions Made (flag these for review)
- None. The review findings explicitly define the required runtime truth and interaction mapping.

### Known Issues / Deferred
- The blueprint verifier still requires the legacy machine ID `dish-selector`; the packet gives it the canonical product name `workspace-identity-details`, real behavior, and a global-shell mapping. No dish UI or orphan compatibility behavior remains.
- Cloud fallback and wake remain unavailable until their complete native/runtime capability gates exist.

### Suggested Next Steps
- Preserve these render gates when the native runtime selector and real Cloud lifecycle are implemented.

## 2026-07-16 — Task 1.2 Hosted configuration and PostgreSQL support

### What Was Implemented
- Added immutable, fail-closed hosted settings with required SQLite/PostgreSQL URLs, distinct minimum-length signing secrets, and redacted representations and configuration errors.
- Added URL-based SQLAlchemy engine and Alembic revision/upgrade APIs while preserving the existing SQLite `Path` APIs and classification gates.
- Added a disposable PostgreSQL 17 test service and an environment-gated fresh-database integration test.
- Made M1-002 through M1-009 migration triggers dialect-aware and preserved both partial unique constraints on PostgreSQL.

### Files Modified
- `corvus/platform/__init__.py` and `corvus/platform/config.py` — expose immutable hosted settings and validated engine creation.
- `corvus/infrastructure/db.py` and `corvus/infrastructure/migrations/env.py` — add URL-based migration access and dialect-aware Alembic configuration.
- `corvus/infrastructure/migrations/trigger_ddl.py` and M1-002 through M1-009 — emit equivalent SQLite and PostgreSQL trigger DDL and PostgreSQL partial-index predicates.
- `compose.platform-test.yaml` — provides the disposable PostgreSQL integration-test service.
- `pyproject.toml` and `uv.lock` — add the approved psycopg binary driver.
- `tests/unit/platform/test_config.py` and `tests/integration/test_postgres_database.py` — cover fail-closed settings, redaction, engine URLs, fresh SQLite migration, and the real PostgreSQL migration contract.
- `PROJECT_LOG.md` — records Task 1.2 implementation and verification status.

### Assumptions Made (flag these for review)
- None. Secret requirements, allowed database URLs, PostgreSQL test skipping, and SQLite compatibility were fixed by the approved Task 1.2 authority.

### Known Issues / Deferred
- Docker, PostgreSQL client tools, and `CORVUS_TEST_POSTGRES_URL` were unavailable on this workstation, so the real PostgreSQL integration test skipped with its explicit service-unavailable reason; it remains mandatory when the disposable service is available.
- Hosted identity/session tables and OAuth flows are deferred to their later Milestone 1 tasks.

### Suggested Next Steps
- Run the PostgreSQL integration test against `compose.platform-test.yaml` in CI or on a workstation with Docker.
- Continue with the next approved Milestone 1 task after Task 1.2 review.

## 2026-07-16 — Harden Task 1.2 review findings

### What Was Implemented
- Reduced hosted-settings representation to the validated database driver so authority credentials and every query value remain absent.
- Made direct settings construction reject all-whitespace secrets before minimum-length checks.
- Added a destructive PostgreSQL test guard requiring an exact opt-in value, a database ending in `_test`, and a loopback or Compose-service host.
- Strengthened the live PostgreSQL contract to verify all 59 triggers and functions, both partial unique indexes and behaviors, immutable update/delete rejection, downgrade cleanup, and re-upgrade restoration.
- Added PostgreSQL offline Alembic rendering without a connection and deterministic offline manifest history for data-dependent migrations.
- Added URL-based downgrade support and guaranteed disposal of internally created Alembic engines on connection or migration failure.

### Files Modified
- `corvus/platform/config.py` — uses driver-only redacted representations and rejects blank direct-constructor secrets.
- `corvus/infrastructure/db.py` — adds the tested URL-based downgrade API.
- `corvus/infrastructure/migrations/env.py` — supports offline SQL rendering and unconditional engine disposal.
- `corvus/infrastructure/migrations/manifest_history.py` and M1-005 through M1-009 — provide deterministic offline manifest inputs while retaining online database validation.
- `tests/postgres_safety.py`, `tests/unit/platform/test_postgres_safety.py`, and `compose.platform-test.yaml` — implement, prove, and document destructive-test authorization.
- `tests/unit/platform/test_config.py` and `tests/integration/test_postgres_database.py` — add redaction, blank-secret, offline, disposal, downgrade, exact PostgreSQL DDL, and runtime-constraint coverage.
- `PROJECT_LOG.md` and `.superpowers/sdd/task-1.2-report.md` — record the review repair and verification evidence.

### Assumptions Made (flag these for review)
- None. The opt-in, disposable-name, host-policy, exact PostgreSQL proof, offline migration, disposal, and redaction requirements came directly from the Task 1.2 review.

### Known Issues / Deferred
- Docker, PostgreSQL client tools, and a test-service URL remain unavailable locally. The destructive integration test therefore stops before connecting with the explicit `postgres_reset_opt_in_required` skip; it does not accept or reset an arbitrary remote database.
- The live exact-trigger/runtime/downgrade contract must still run in CI or a Docker-enabled workstation using the documented disposable service and explicit opt-in.

### Suggested Next Steps
- Start `compose.platform-test.yaml`, set `CORVUS_TEST_POSTGRES_RESET_ALLOWED=reset-disposable-database`, and run the focused PostgreSQL test for live evidence.
- Continue to the next Milestone 1 task only after the follow-up commit is reviewed.

## 2026-07-16 — Close Task 1.2 PostgreSQL query-override gap

### What Was Implemented
- Rejected every PostgreSQL test URL query parameter except one bounded `connect_timeout` value, including libpq routing, database, identity, password, service, and encoded-host overrides.
- Kept effective PostgreSQL test routing fixed to the validated URL authority and path before engine creation.
- Added a live contract assertion that two distinct quarantined commit-intent rows for one workspace both succeed, proving the documented finalized/quarantined partial-index exclusion.

### Files Modified
- `tests/postgres_safety.py` — adds the strict query allowlist and bounded timeout validation with secret-free errors.
- `tests/unit/platform/test_postgres_safety.py` — proves routing/identity overrides, arbitrary keys, encoded keys, and ambiguous timeout values fail closed.
- `tests/integration/test_postgres_database.py` — adds same-workspace quarantined-row acceptance to the service-gated live contract.
- `compose.platform-test.yaml` — documents the only allowed query key and timeout range.
- `PROJECT_LOG.md` and `.superpowers/sdd/task-1.2-report.md` — supersede the earlier host-only safety claim with the complete effective-target rule.

### Assumptions Made (flag these for review)
- None. The strict allowlist, effective-target validation, distinct quarantined-row assertion, and retained prior safety rules came directly from the final Task 1.2 review.

### Known Issues / Deferred
- The previous `fc2fe56` guard validated the URL driver, authority host, and database path but did not reject libpq query overrides; this entry records and closes that gap.
- Live PostgreSQL remains unavailable locally, so the strengthened quarantined predicate assertion remains service-gated behind the unchanged opt-in and disposable-target controls.

### Suggested Next Steps
- Run the guarded live PostgreSQL test against the disposable Compose service for server-backed evidence.
- Treat this strict query allowlist as part of the destructive-test safety boundary in future changes.

## 2026-07-16 — Task 1.3 Identity continuity persistence

### What Was Implemented
- Added frozen account, external-identity, device-registration, and digest-only session contracts while retaining the existing USER Principal as the authority identity.
- Added callback-ready verified Google identity completion with exact issuer/subject reuse, atomic first-time Principal/Account/ExternalIdentity creation, and fail-closed pre-provisioned email attachment.
- Added SQLAlchemy 2 repositories that preserve SQLite Path APIs, accept caller-owned SQLite/PostgreSQL engines, keep workspace and membership reads tenant-scoped, and expose membership authority only through existing AccessBundle/CapabilityGrant records.
- Added atomic append-only session rotation/revocation, predecessor replay denial, and bound-device revocation invalidation.
- Added reversible `m2_001_identity_continuity`, schema-7 authority-root coverage, classifier/revision updates, and SQLite/PostgreSQL migration contracts.

### Files Modified
- `corvus/domain/account.py`, `corvus/domain/identity.py`, and `corvus/application/identity.py` — define identity-continuity contracts and application linking rules.
- `corvus/infrastructure/repositories/accounts.py` and `corvus/infrastructure/repositories/identity_scope.py` — implement the portable repository contract without parallel workspace or membership types.
- `corvus/infrastructure/migrations/versions/m2_001_identity_continuity.py`, `manifest_history.py`, `corvus/database.py`, and `corvus/infrastructure/db.py` — add the reversible schema, current revision, exact classification, and manifest history.
- `corvus/infrastructure/authority_root.py` — scopes account, identity, device, and session families through existing workspace memberships.
- Focused and regression tests under `tests/unit/domain`, `tests/unit/platform`, `tests/integration`, and `tests/contract` — cover identity linking, isolation, rotation/revocation, migration cycles, PostgreSQL guarding, and active-manifest compatibility.

### Assumptions Made (flag these for review)
- None. The Task 1.3 brief and the callback contract clarification fixed the identity-linking, authority, persistence, and service-gating behavior.

### Known Issues / Deferred
- The guarded live PostgreSQL repository and migration contract did not run locally because the explicit disposable reset opt-in/service was unavailable; the test skipped before engine creation with `postgres_reset_opt_in_required`.

### Suggested Next Steps
- Run `tests/integration/test_postgres_database.py` against the approved disposable PostgreSQL service with the documented reset opt-in.
- Review the Task 1.3 commit before beginning OAuth transaction and cookie/session transport work in Task 1.4.

## 2026-07-16 — Harden Task 1.3 review findings

### What Was Implemented
- Made M2 identity-continuity downgrade fail closed before changing triggers, manifests, or tables whenever any account, external identity, device, or session history exists; retained the empty downgrade/re-upgrade path.
- Added `device_version` to session history and a portable composite foreign key that database-enforces an exact same-account device-version binding; repository creation also requires the current device version.
- Scoped replay-history classification to the requested account and session, added cross-tenant rotate/revoke probes, and consolidated replacement-digest collisions under the value-free `session_replacement_conflict` code.
- Added case-insensitive Owner/Admin/Manager/Member/Viewer capability ceilings over the existing AccessBundle/CapabilityGrant records, with unknown roles and out-of-ceiling allows failing closed while deny grants remain effective.
- Made newly linked OAuth accounts truthfully retain `experience_kind=None` until onboarding, while preserving explicit experience values for pre-provisioned accounts.
- Added populated SQLite preservation proof, a guarded PostgreSQL equivalent, direct schema probes, and focused/broad/security regression coverage.

### Files Modified
- `corvus/domain/account.py` — makes onboarding experience optional and records the bound device version on every session record.
- `corvus/infrastructure/migrations/versions/m2_001_identity_continuity.py` and `corvus/database.py` — add nullable onboarding state, composite device/session integrity, classifier coverage, and the fail-closed downgrade guard.
- `corvus/infrastructure/repositories/accounts.py` — enforces exact current-device binding, tenant-scoped replay classification, generic replacement conflicts, and unselected OAuth onboarding.
- `corvus/infrastructure/repositories/identity_scope.py` — projects persisted grants through deterministic role ceilings without adding capabilities to memberships.
- `tests/unit/domain/test_account.py`, `tests/unit/platform/test_config.py`, `tests/integration/test_account_repository.py`, and `tests/integration/test_postgres_database.py` — prove the reviewed behavior on models, rendered DDL, SQLite, and the guarded PostgreSQL contract.
- `PROJECT_LOG.md` and `.superpowers/sdd/task-1.3-report.md` — record the corrected Task 1.3 contract and verification evidence.

### Assumptions Made (flag these for review)
- None. The role matrix, case-insensitive labels, value-free failure behavior, downgrade boundary, session binding, replay scope, and onboarding sequence came directly from the Task 1.3 review clarification.

### Known Issues / Deferred
- The destructive PostgreSQL test remains locally skipped before connection because `CORVUS_TEST_POSTGRES_RESET_ALLOWED` is not authorized; its populated downgrade-preservation proof is retained for the approved disposable service.

### Suggested Next Steps
- Run the guarded PostgreSQL test against the approved disposable service to collect server-backed proof of the populated downgrade refusal.
- Review the Task 1.3 follow-up commit before beginning Task 1.4.

## 2026-07-16 — Close Task 1.3 stale-device and workspace-metadata gaps

### What Was Implemented
- Unified exact-device-version write denial under the value-free `session_device_version_stale` code for session creation, rotation, and revocation.
- Made stale v1-bound rotation and revocation fail before appending session history, consuming the presented token, or minting/rebinding a replacement after the active device advances to v2.
- Extended the M2 downgrade preflight to inspect workspace-kind column and payload metadata portably on SQLite and PostgreSQL before any trigger, manifest, table, or column change.
- Refused downgrade for TEAM, unknown, non-default, invalid, or column/payload-divergent workspace metadata while preserving compatible default-individual rows with matching or absent legacy payload metadata.
- Added independent SQLite rotate/revoke regressions, TEAM-only and divergence downgrade preservation proofs, a legacy-compatible default-individual cycle, a guarded PostgreSQL TEAM proof, and explicit offline fail-closed coverage.

### Files Modified
- `corvus/infrastructure/repositories/accounts.py` — blocks stale-device session creation, rotation, and revocation with one value-free denial.
- `corvus/infrastructure/migrations/versions/m2_001_identity_continuity.py` — validates workspace metadata before online downgrade and retains offline refusal without history inspection.
- `tests/integration/test_account_repository.py` — proves stale writes do not append/mint and workspace-only metadata cannot be lost or diverge.
- `tests/integration/test_postgres_database.py` and `tests/unit/platform/test_config.py` — retain guarded PostgreSQL and offline downgrade proofs.
- `PROJECT_LOG.md` and `.superpowers/sdd/task-1.3-report.md` — record the final Task 1.3 review closure and evidence.

### Assumptions Made (flag these for review)
- None. The shared denial code, stale rotate/revoke boundary, workspace compatibility rule, and offline behavior were explicitly confirmed before implementation.

### Known Issues / Deferred
- The destructive PostgreSQL proof remains locally skipped before connection because the disposable reset opt-in is not authorized; the TEAM-workspace preservation contract is ready for the approved service.

### Suggested Next Steps
- Run the guarded PostgreSQL test against the approved disposable service for server-backed TEAM-workspace downgrade evidence.
- Review this final Task 1.3 follow-up commit before starting Task 1.4.

## 2026-07-16 — Implement Task 1.4 Google OAuth and durable sessions

### What Was Implemented
- Added Google Authorization Code OAuth with S256 PKCE, HMAC-authenticated state, nonce binding, exact redirect allowlists, fixed Google endpoints, RS256/JWKS verification, verified-email policy, and late secret resolution through injectable ports.
- Added encrypted, expiring, durably single-use OAuth transactions plus opaque browser-device/session credentials, digest-only persistence, HMAC-bound CSRF values, atomic login/session rotation, replay rejection, revocation, and secure host-only cookies.
- Added the modular `/api/v2` identity, session, onboarding, workspace, and device routes with tenant scoping, optimistic versions, durable create idempotency, stable redacted errors, and truthful unconfigured `503` responses while preserving legacy pairing/static behavior.
- Added the additive `m2_001a_oauth_sessions` migration and classifier/revision support for OAuth transactions, web-session bindings, onboarding versions, and identity idempotency records on SQLite and PostgreSQL-compatible SQLAlchemy paths.
- Added a Vercel same-origin `/api/v2/**` proxy with a validated Railway origin, strict method/path/header forwarding, manual redirect handling, safe response-header filtering, and traversal/authority/header-injection tests without enabling credentialed cross-origin CORS.

### Files Modified
- `corvus/application/oauth.py`, `corvus/infrastructure/oauth/`, and `corvus/platform/api/` — define OAuth ports, Google verification, transaction persistence, hosted dependency composition, and v2 routes.
- `corvus/infrastructure/repositories/accounts.py` and `corvus/infrastructure/repositories/platform_identity.py` — implement atomic browser login/session behavior and scoped onboarding/workspace/device persistence.
- `corvus/infrastructure/migrations/versions/m2_001a_oauth_sessions.py`, `corvus/database.py`, and `corvus/infrastructure/db.py` — add and classify the Task 1.4 schema revision.
- `corvus/platform/config.py`, `corvus/platform/__init__.py`, `.env.example`, `pyproject.toml`, and `uv.lock` — add fail-closed hosted OAuth configuration, documented deployment variables, and the approved Authlib dependency.
- `corvus/mvp/api.py` — composes the v2 router exactly once before the catch-all static mount while retaining existing callers and legacy auth.
- `apps/web/api/v2/[...path].ts`, `apps/web/vercel.json`, `apps/web/tsconfig.app.json`, and `apps/web/src/v2Proxy.test.ts` — add and verify the same-origin Vercel proxy boundary.
- `tests/security/test_google_oauth.py`, `tests/integration/test_identity_api.py`, and `tests/unit/platform/test_config.py` — prove OAuth, session, route, cookie, persistence, redaction, and hosted-configuration behavior.
- `PLAN.md` — records the completed Task 1.4 checklist.

### Assumptions Made (flag these for review)
- None. OAuth topology, algorithms, TTLs, cookie names, token formats, route contracts, migration revision, proxy boundary, and stop boundary were explicitly confirmed before implementation.

### Known Issues / Deferred
- Live Google consent/token exchange, live Vercel-to-Railway proxy behavior, deployment, and desktop browser-to-app handoff remain intentionally deferred by the Task 1.4 stop boundary.
- The guarded destructive PostgreSQL contract remains locally skipped before connection because `CORVUS_TEST_POSTGRES_RESET_ALLOWED` is not authorized.
- A broad Bandit scan still reports three pre-existing low-severity B101 assertions in `corvus/application/agent_runtime.py`; the complete Task 1.4 module scan is clean.

### Suggested Next Steps
- Review the Task 1.4 commit and configure disposable hosted OAuth/proxy credentials before any authorized live integration exercise.
- Run the guarded PostgreSQL test against the approved disposable service, then begin Task 1.5 only after explicit authorization.

## 2026-07-16 — Harden Task 1.4 review findings

### What Was Implemented
- Restricted the Vercel proxy to credential-free, default-port HTTPS Railway-generated `*.up.railway.app` origins in production/preview, with loopback HTTP available only under an explicitly injected development/test environment; custom domains and IP/private/link-local targets fail closed.
- Preserved only safe relative response redirects and the exact Google authorization endpoint, including a real proxied start-route test; external, authority-bearing, fragmented, credentialed, wrong-path, control-character, and backslash redirects are suppressed.
- Added a terminal OAuth abort/consume path so provider denial and missing/malformed callback codes return one value-free `oauth_callback_rejected` response after valid state consumption; HMAC-invalid and non-canonical state representations fail before transaction lookup.
- Converted only recognized optimistic version uniqueness and SQLite lock races for onboarding, workspace updates, and device revocation into stable `409` conflicts after rollback and authorized current-state reload; unrelated integrity failures remain unmodified.
- Added Task 1.4 immutable-trigger classification, guarded PostgreSQL control expectations, populated-family downgrade preservation proofs, and empty downgrade/re-upgrade coverage.
- Added adversarial nonce, signature, algorithm, time-claim, encrypted-transaction corruption, token/JWKS transport, recursive redaction, SSRF, and deterministic concurrent-writer coverage.

### Files Modified
- `apps/web/api/v2/[...path].ts`, `apps/web/src/v2Proxy.test.ts`, `.env.example`, and `apps/web/HOSTED_RUNTIME_SECURITY.md` — harden and document the same-origin redirect and Railway-origin boundary.
- `corvus/application/oauth.py`, `corvus/infrastructure/oauth/google.py`, and `corvus/platform/api/identity.py` — add terminal callback consumption, canonical state validation, and stable API rejection.
- `corvus/infrastructure/repositories/platform_identity.py` — normalize only recognized optimistic races after scoped state reload.
- `corvus/database.py` — require all Task 1.4 immutable controls for current-schema classification.
- `tests/security/test_google_oauth.py`, `tests/integration/test_identity_api.py`, `tests/integration/test_account_repository.py`, and `tests/integration/test_postgres_database.py` — prove the reviewed security, race, classifier, and rollback behavior.

### Assumptions Made (flag these for review)
- None. Callback error code, state-consumption boundary, redirect rules, Vercel environment policy, race translation scope, classifier controls, and stop boundary were explicitly confirmed before remediation.

### Known Issues / Deferred
- The guarded destructive PostgreSQL proof remains locally skipped before connection because `CORVUS_TEST_POSTGRES_RESET_ALLOWED` is not authorized; expected Task 1.4 controls and populated downgrade assertions are retained for the approved disposable service.
- Custom Railway domains remain unsupported pending an explicit deployment allowlist design and security review.
- Live Google, Vercel/Railway deployment, desktop handoff, and Task 1.5 remain outside this remediation boundary.

### Suggested Next Steps
- Review the Task 1.4 remediation commit and run the guarded PostgreSQL proof when disposable reset authorization is available.
- Keep the branch/worktree intact for review; begin Task 1.5 only after explicit authorization.

## 2026-07-16 — Implement Task 1.5 ordered workspace synchronization

### What Was Implemented
- Added the two-command typed sync protocol, exact-version conflicts, atomic batches of at most 100 mutations, generalized scoped idempotency, versioned device acknowledgements, bounded frozen-high-watermark pages, and explicit resync responses.
- Added serialized per-workspace sequence allocation, canonical request/change hashing, append-only workspace changes and outbox records, hash-chain validation, stable account/workspace writer locks, and tenant/version-bound foreign keys across SQLite and PostgreSQL-compatible paths.
- Added `m2_002_workspace_sync`, migrated Task 1.4 idempotency rows into the platform-wide contract, extended current-schema classification and authority-root manifest families, and made populated downgrade refuse before mutation.
- Reused the existing session, CSRF, Origin, device, membership, and redacted error boundaries while composing the sync router exactly once in the platform API.
- Added adversarial domain, repository, API/security, migration, concurrency, replay, tamper, tenant-isolation, downgrade, and guarded PostgreSQL contract coverage.

### Files Modified
- `corvus/domain/sync.py` and `corvus/application/sync.py` — define the closed mutation union, sync results/pages/errors, bounds, and service boundary.
- `corvus/infrastructure/repositories/sync.py` and `corvus/infrastructure/repositories/platform_identity.py` — implement transactional sync and the shared platform idempotency authority.
- `corvus/infrastructure/migrations/versions/m2_002_workspace_sync.py`, `corvus/database.py`, `corvus/infrastructure/db.py`, and `corvus/infrastructure/migrations/manifest_history.py` — add, classify, migrate, and safely downgrade the sync schema.
- `corvus/infrastructure/authority_root.py` — projects the five new authority families into workspace/account roots.
- `corvus/platform/api/sync.py`, `corvus/platform/api/app.py`, `corvus/platform/api/dependencies.py`, and `corvus/platform/api/identity.py` — add the authenticated sync API while reusing identity security controls.
- `corvus/security.py` — adds recursive secret rejection and stable canonical JSON normalization for persisted sync material.
- `tests/unit/domain/test_sync.py`, `tests/integration/test_sync_repository.py`, `tests/security/test_sync_replay.py`, and `tests/integration/test_sync_migration.py` — prove protocol, persistence, API, concurrency, integrity, and migration behavior.
- Existing account, PostgreSQL, authority-manifest, and real-project contract tests — update expected current-schema and manifest behavior without weakening earlier coverage.
- `PLAN.md` — records the completed Task 1.5 checklist.

### Assumptions Made (flag these for review)
- None. The mutation vocabulary, transaction boundary, lock ordering, cursor/acknowledgement semantics, idempotency scope, hash inputs, migration behavior, router composition, and stop boundary were explicitly resolved in the approved Task 1.5 brief.

### Known Issues / Deferred
- The two destructive PostgreSQL sync cases and the existing PostgreSQL migration contract remain locally skipped before engine creation because `CORVUS_TEST_POSTGRES_RESET_ALLOWED` is not authorized; their server-backed assertions and expected controls are retained.
- SSE, retention/snapshot workers, outbox delivery, arbitrary entity sync, and deployment remain intentionally outside the Task 1.5 scope guard.

### Suggested Next Steps
- Run the guarded PostgreSQL contracts against the approved disposable service for live row-lock and DDL evidence.
- Review the Task 1.5 commit before authorizing Task 1.6 onboarding and client sync work.

## 2026-07-16 — Harden Task 1.5 independent review findings

### What Was Implemented
- Validated the locked workspace head and fully recomputed its typed canonical tail before every apply-path acknowledgement, replay, entity, outbox, or idempotency write; forged, missing, and broken previous-link tails now fail atomically with `sync_change_integrity_invalid`.
- Required exact canonical payload bytes, duplicate-free finite JSON, timezone-aware canonical timestamps, closed profile schemas, kind/operation coherence, recursive sensitive-value rejection, and stable integrity-error mapping even when a page is empty at the high watermark.
- Added one value-free `RequestValidationError` boundary for malformed or rejected requests: v2 returns only a stable code and correlation ID, while legacy routes retain a stable value-free envelope.
- Bound sync changes, acknowledgements, and scoped idempotency rows to the exact account/principal pair and current workspace membership version while retaining workspace/version, device/account, and account-scope foreign keys.
- Included membership version in request/change hashes, outbox evidence, replay authority checks, and returned change provenance; generalized schema classification now also requires the Task 1.5 account/principal unique index.
- Added adversarial apply/replay/ack rollback, empty-page tail, canonical JSON, typed-profile, secret/nonfinite/naive-time, API canary, migration, direct SQLite transplant, offline PostgreSQL DDL, and guarded PostgreSQL transplant coverage.

### Files Modified
- `corvus/infrastructure/repositories/sync.py` — performs pre-write head/tail integrity checks, typed canonical read validation, stable replay authority checks, and exact membership provenance persistence.
- `corvus/infrastructure/migrations/versions/m2_002_workspace_sync.py` and `corvus/database.py` — add and classify exact membership/account-principal constraints and safely remove the supporting index on downgrade.
- `corvus/domain/sync.py` — adds closed account/workspace profile contracts and workspace, membership, and device provenance to changes.
- `corvus/mvp/api.py` and `corvus/platform/api/sync.py` — provide value-free request validation responses and use the non-deprecated 422 status alias.
- `tests/integration/test_sync_repository.py`, `tests/security/test_sync_replay.py`, and `tests/integration/test_sync_migration.py` — reproduce and prevent every confirmed review finding across repository, API, SQLite, PostgreSQL-guarded, and offline-DDL boundaries.

### Assumptions Made (flag these for review)
- None. The four repair areas, exact binding requirements, required adversarial cases, stop boundary, separate-commit requirement, and no-push boundary came directly from the confirmed independent review.

### Known Issues / Deferred
- The destructive PostgreSQL migration contract and three guarded sync PostgreSQL cases remain locally skipped before engine creation because `CORVUS_TEST_POSTGRES_RESET_ALLOWED` is not authorized; their exact FK, DDL, and row-lock assertions are retained.
- The original Task 1.5 scope guard still defers SSE, retention/snapshot workers, outbox delivery, arbitrary entity sync, and deployment.

### Suggested Next Steps
- Run the four guarded PostgreSQL cases against the approved disposable service for live constraint and lock evidence.
- Re-review the separate Task 1.5 hardening commit before authorizing Task 1.6.

## 2026-07-17 — Close Task 1.5 residual integrity findings

### What Was Implemented
- Distinguished a truly new workspace from a deleted or missing sync head by checking all workspace-scoped change, outbox, acknowledgement, and idempotency history before treating sequence zero as genesis.
- Made page, acknowledgement-only apply, idempotent replay, and new mutation paths fail before writes with the stable redacted `sync_change_integrity_invalid` error when a head is missing but scoped history remains.
- Bound account-profile entity and payload provenance to the recorded authenticated account, and workspace-profile entity/payload identity and version to the authoritative workspace/version columns already protected by foreign keys.
- Added recomputed canonical substitution attacks against account IDs, workspace IDs, and workspace versions, including empty-page high-watermark reads where only the tail validator runs.

### Files Modified
- `corvus/infrastructure/repositories/sync.py` — rejects orphan-history genesis and enforces kind-specific account/workspace entity provenance during full tail recomputation.
- `tests/integration/test_sync_repository.py` — proves four missing-head request paths roll back without writes, true genesis remains available, and recomputed account/workspace substitutions fail closed.
- `PROJECT_LOG.md` — records this consolidated residual review closure and evidence boundary.

### Assumptions Made (flag these for review)
- None. The orphan-history families, request paths, stable error, entity/version bindings, TDD order, separate-commit requirement, and no-push boundary were explicitly confirmed before implementation.

### Known Issues / Deferred
- The existing PostgreSQL migration contract and three sync PostgreSQL cases remain guarded before engine creation because disposable reset authorization is unavailable; this residual repair changes repository validation only and adds no DDL.
- The original Task 1.5 scope guard continues to defer SSE, retention/snapshot workers, outbox delivery, arbitrary entity sync, and deployment.

### Suggested Next Steps
- Run the four guarded PostgreSQL cases against the approved disposable service when reset authorization is available.
- Re-run independent review on the complete Task 1.5 commit chain before authorizing Task 1.6.

## 2026-07-17 — Implement Task 1.6 Google-first onboarding and synchronized profiles

### What Was Implemented
- Added a single hosted composition root with in-memory authentication and ordered workspace synchronization providers.
- Added Google-first, server-resumable onboarding with exact versions, stable idempotent workspace creation, explicit Team creation, unavailable Join, and disabled Cloud Preview.
- Added strict sequence/digest/provenance reduction, acknowledgement-after-reduction, conflict/resync/offline/403 behavior, and explicit authority re-selection.
- Replaced experience/scope switches with read-only identity labels and authorized workspace selection on desktop/mobile.
- Reduced V1 browser preferences to one-time post-auth migration input and preserved the authenticated hosted-to-loopback boundary.
- Added explicit V2 request/response/error schemas and regenerated deterministic OpenAPI/TypeScript contracts.

### Files Modified
- `apps/web/src/auth/`, `apps/web/src/sync/`, `apps/web/src/PlatformApp.tsx`, `apps/web/src/App.tsx`, and `apps/web/src/main.tsx` — compose session, onboarding, selection, sync, and local runtime boundaries.
- `apps/web/src/app/`, `apps/web/src/components/`, `apps/web/src/runtime/`, and web styles/tests — implement resumable onboarding, migration, read-only identity, responsive navigation, handoff, and coverage.
- `corvus/platform/api/identity.py`, `corvus/platform/api/sync.py`, `openapi/corvus-mvp.json`, and `apps/web/src/generated/api.ts` — provide explicit typed V2 contracts in configured and unavailable modes.
- `tests/mvp/test_openapi_export.py` and `.superpowers/sdd/task-1.6-report.md` — prove and record typed export and completion evidence.

### Assumptions Made (flag these for review)
- None. All state ownership, failure, migration, vocabulary, runtime, viewport, and stop-boundary decisions were explicitly confirmed.

### Known Issues / Deferred
- Full mypy still reports five pre-existing migration typing errors unrelated to Task 1.6.
- Four destructive PostgreSQL cases remain guarded before engine creation without disposable reset authorization.
- Invitations, organization roles, durable active selection, offline mutation queues, native OAuth handoff, real cloud execution, billing, deployment, profile Settings, and Task 2 are deferred.

### Suggested Next Steps
- Independently review the Task 1.6 commit and required viewport captures.
- Begin Task 2 only after explicit authorization.

## 2026-07-17 — Close Task 1.6 consolidated review findings

### What Was Implemented
- Split loopback composition from hosted identity so `localhost`, `127.0.0.1`, and IPv6 loopback open the legacy local pairing boundary without booting hosted session or synchronization APIs.
- Added generation fences for authentication discovery, workspace discovery/selection, local project/workflow/operations loads, event streams, and workspace-derived mutation results; confirmed workspace changes now reset every derived UI state.
- Centralized mutation-time 401 authority invalidation, refreshed authorized workspace lists on 403 while preserving the last-safe read-only display, and rejected stale workspace selections.
- Added explicit conflict versions with reload/retry actions, including onboarding truth refresh that preserves the selected form value and retries with the new exact account version.
- Added real Settings routes with a truthful read-only placeholder, keyboard-contained identity and mobile More dialogs, and valid legacy candidate cleanup or explicit dismissal for returning users.

### Files Modified
- `apps/web/src/auth/`, `apps/web/src/sync/`, `apps/web/src/PlatformApp.tsx`, and `apps/web/src/App.tsx` — enforce runtime authority separation, centralized invalidation, conflict recovery, and async generation fencing.
- `apps/web/src/app/` and `apps/web/src/components/` — add Settings navigation, conflict UI, legacy cleanup controls, alternate-workspace recovery, and accessible dialog focus behavior.
- Web unit and integration tests — reproduce all consolidated review races, authority failures, conflict paths, runtime boundaries, migration cleanup, Settings behavior, and keyboard interactions.
- `.superpowers/sdd/task-1.6-report.md` and `PROJECT_LOG.md` — record the review closure and final evidence.

### Assumptions Made (flag these for review)
- None. Loopback host matching, authority behavior, reset scope, conflict actions, Settings boundary, focus behavior, generation fencing, separate-commit requirement, and no-push/no-deployment stop boundary were explicitly confirmed.

### Known Issues / Deferred
- Five baseline full-mypy errors remain in pre-existing migration files; no Task 1.6 review-fix file is implicated.
- Four destructive PostgreSQL tests remain guarded before engine creation because disposable reset authorization is unavailable.
- Settings is intentionally read-only; invitations, organization roles, persisted active-workspace preference, offline mutation queues, native desktop OAuth, real cloud execution, billing, deployment, and Task 2 remain deferred.

### Suggested Next Steps
- Independently review the separate Task 1.6 consolidated-fix commit.
- Begin Task 2 only after explicit authorization.

## 2026-07-17 — Close Task 1.6 authority and stale-operation re-review

### What Was Implemented
- Removed fabricated loopback account, workspace, profile, and CSRF authority; loopback now consumes only the legacy session/pairing/project API while hosted composition remains Google-first.
- Added generation fencing to stale authentication reloads, workspace profile mutations, conflict reload/retry actions, and their 401/403 recovery paths.
- Centralized mutation and retry 403 membership refresh so the last-safe workspace remains visible but immutable until an explicit fresh selection.
- Added truthful no-access guidance for empty refreshed membership and contained nested identity Escape handling so the parent More dialog stays open with focus restored locally.
- Added direct transport tests for credentialed session/pairing requests and session-derived CSRF mutation headers.

### Files Modified
- `apps/web/src/App.tsx`, `apps/web/src/PlatformApp.tsx`, and their tests — provide authority-neutral loopback composition backed by real legacy session truth.
- `apps/web/src/auth/AuthProvider.tsx` and tests — ignore stale reload failures after newer authenticated truth wins.
- `apps/web/src/sync/SyncProvider.tsx` and tests — fence mutation/conflict operations and centralize fresh-membership recovery.
- `apps/web/src/components/WorkspaceSwitcher.tsx`, responsive navigation tests, and identity tests — provide truthful empty membership and nested Escape behavior.
- `apps/web/src/api.test.ts` — prove credential and CSRF transport consumption.
- `.superpowers/sdd/task-1.6-report.md` and `PROJECT_LOG.md` — record final repair evidence and scope boundaries.

### Assumptions Made (flag these for review)
- None. Loopback authority ownership, operation generations, 403 recovery, accessibility behavior, required gates, separate commit, and no-push/no-Task-2 boundary were explicitly confirmed.

### Known Issues / Deferred
- Full mypy still reports the same five pre-existing migration typing errors in `m1_006` through `m1_009` and migration `env.py`; no changed Task 1.6 file is implicated.
- Four destructive PostgreSQL tests remain guarded before engine creation because disposable reset authorization is unavailable.
- Invitations, organization roles, durable active selection, offline mutation queues, native desktop OAuth, real cloud execution, billing, deployment, editable Settings, and Task 2 remain deferred.

### Suggested Next Steps
- Independently review the separate Task 1.6 authority/stale-operation repair commit and retained browser captures.
- Begin Task 2 only after explicit authorization.

## 2026-07-17 — Fence stale explicit-resync acknowledgements

### What Was Implemented
- Added a generation fence after explicit-resync page fetch/reduction and immediately before acknowledgement.
- Added a regression that defers workspace A's resync page, selects workspace B, then proves late A cannot send an acknowledgement or mutate B's ready snapshot.

### Files Modified
- `apps/web/src/sync/SyncProvider.tsx` — prevents superseded explicit-resync work from acknowledging a stale cursor.
- `apps/web/src/sync/SyncProvider.test.tsx` — reproduces and permanently covers the stale pre-ACK race.
- `.superpowers/sdd/task-1.6-report.md` and `PROJECT_LOG.md` — record the final review closure and verification evidence.

### Assumptions Made (flag these for review)
- None. The race shape, generation boundary, frontend-only verification scope, documentation, separate commit, and stop boundary were explicitly confirmed.

### Known Issues / Deferred
- Full mypy retains the five previously documented migration typing errors; this frontend-only repair does not touch those files.
- Four destructive PostgreSQL tests remain guarded without disposable reset authorization.
- No push, deployment, PR, or Task 2 work was authorized.

### Suggested Next Steps
- Independently review the final explicit-resync fence commit.
- Begin Task 2 only after explicit authorization.

## 2026-07-17 - Persist workspace-scoped conversations, runs, events, and artifacts

### What Was Implemented
- Added frozen, extra-forbid conversation domain contracts for threads, attachment metadata, messages, immutable run records, hash-chained run events, numeric event pages, artifacts, and canonical lineage.
- Added a fail-closed conversation application service and authority/audit lifecycle ports. Mutations bind request context, client surface, authorization snapshot, idempotency digest, live roots, audit receipt, and finalized result before repository writes are exposed.
- Added a dual-dialect `ConversationRepository` with transaction-time active-membership checks, SQLite `BEGIN IMMEDIATE`, PostgreSQL row locks, exact idempotency replay, gap-free sequence allocation, frozen event paging, artifact DAG validation, and stable tenant-safe errors.
- Added `m2_003_conversations`, manifest schema version 9, nine in-root authority families, classifier/root coverage, immutable triggers, portable composite foreign keys, partial provider-event uniqueness, and deterministic empty downgrade/re-upgrade behavior.
- Generalized head-level downgrade preflight so populated conversation, sync, OAuth, identity, or incompatible identity-workspace history refuses before any newer schema layer is mutated.
- Added domain, SQLite/PostgreSQL repository, migration/root, and security regression coverage, including tamper, tenant transplant, replay mismatch, revoked membership, cursor, event-chain, and artifact-lineage cases.

### Files Modified
- `corvus/domain/conversations.py` - defines the immutable conversation persistence contracts and canonical validation helpers.
- `corvus/application/conversations.py` and `corvus/application/ports.py` - provide the fail-closed service boundary and generalized mutation lifecycle contracts.
- `corvus/infrastructure/repositories/conversations.py` - implements tenant-safe transactional persistence and paging.
- `corvus/infrastructure/migrations/versions/m2_003_conversations.py` - creates the nine conversation authority families and manifest version 9.
- `corvus/database.py`, `corvus/infrastructure/db.py`, `corvus/infrastructure/migrations/manifest_history.py`, and `corvus/infrastructure/authority_root.py` - register the new current revision, classifier, downgrade preflight, history, and root projections.
- `tests/unit/domain/test_conversations.py`, `tests/integration/test_conversation_repository.py`, `tests/integration/test_conversation_migration.py`, and `tests/security/test_conversation_isolation.py` - cover the new domain, repository, migration, and security contracts.
- `tests/contract/test_real_project_vertical.py`, `tests/integration/test_account_repository.py`, and `tests/integration/test_non_circular_root_manifest.py` - advance active-manifest expectations and preserve whole-path downgrade atomicity.
- `.superpowers/sdd/task-2.1-report.md` and `PROJECT_LOG.md` - record Task 2.1 scope, TDD evidence, verification, and stop boundaries.

### Assumptions Made (flag these for review)
- Provider binding and authorization snapshot identifiers are immutable value bindings only; Task 2.1 does not introduce provider or authorization authority tables.
- PostgreSQL destructive runtime checks remain guarded unless an explicit disposable reset opt-in is present; portable PostgreSQL DDL is still verified offline.
- No API, SSE, provider runtime, process execution, binary blob storage, retention worker, web UI, deployment, push, or Task 2.2 work is included.

### Known Issues / Deferred
- Full `mypy corvus` retains five pre-existing errors in untouched certified migration files: migration `env.py` and revisions `m1_006`, `m1_007`, `m1_008`, and `m1_009`. All changed/new Task 2.1 source modules pass targeted mypy.
- Five PostgreSQL destructive tests are skipped by the existing `postgres_reset_opt_in_required` guard because disposable reset authorization is unavailable.
- Opaque authenticated API cursors, provider adapters, runtime execution, retention deletion, API/SSE transport, and UI remain deferred to later authorized tasks.

### Suggested Next Steps
- Independently review the separate Task 2.1 commit and the evidence in `.superpowers/sdd/task-2.1-report.md`.
- Progress to Task 2.2 after independent Task 2.1 approval.

## 2026-07-17 - Close Task 2.1 authority-binding and event-chain review findings

### What Was Implemented
- Added fail-closed application-boundary authority binding for attachment registration, message append, run creation, event append, and artifact recording before lifecycle or repository invocation.
- Bound every affected payload to the request workspace and its provable scope; denied delegated attachment ownership and principal/agent authorship, and bound run requester plus authorization snapshot ID/digest exactly to `RequestContext`.
- Required attachment and artifact mutations to use an exact workspace scope because neither payload exposes a provable thread scope; retained transactional producing-run/event/parent validation for artifacts.
- Changed event paging to validate the complete persisted chain from genesis through the frozen high watermark, including sequence, predecessor/event digests, run handle, workspace/thread/run envelope, terminal transitions, and tool-state prerequisites.
- Added adversarial coverage for all five mutation families, identity/snapshot/scope transplants, and a disconnected predecessor whose event digest was recomputed to remain locally valid.

### Files Modified
- `corvus/application/conversations.py` - rejects authority transplants with the stable non-enumerating `conversation_authority_binding_mismatch` before lifecycle/repository access.
- `corvus/infrastructure/repositories/conversations.py` - validates the full frozen persisted event chain before returning any page slice.
- `tests/security/test_conversation_isolation.py` - reproduces both High findings and covers all confirmed binding rules.
- `.superpowers/sdd/task-2.1-report.md` and `PROJECT_LOG.md` - record review repair and verification evidence.

### Assumptions Made (flag these for review)
- None. Workspace/scope, owner/author/requester, authority-version, snapshot, chain-validation, stable-error, test, commit, and no-push boundaries were explicitly confirmed.

### Known Issues / Deferred
- Full mypy retains the five documented errors in unchanged certified migration files; the review-fix source files pass targeted mypy.
- PostgreSQL destructive tests remain guarded without explicit disposable reset authorization.
- No API/SSE/UI/provider runtime, Task 2.2 implementation, push, pull request, or deployment is included in this repair.

### Suggested Next Steps
- Independently re-review the separate Task 2.1 High-finding repair commit.
- Progress to Task 2.2 after Task 2.1 approval.
## 2026-07-17 - Add provider-neutral registry and bounded process sessions

### What Was Implemented
- Added an immutable provider registry over the existing `AgentRuntimePort` with deterministic one-time factory construction, all-or-nothing scoped discovery, duplicate refusal, fail-closed capability intersection, stable redacted errors, and exact binding-owner dispatch.
- Hardened `AgentRuntimeCoordinator` preflight to reconstruct provider models, validate exact workspace/project scope, require exactly one matching binding, and preserve `UNVERIFIED` as unavailable.
- Added frozen bounded process-session contracts with executable digest pinning, direct argv spawning, canonical cwd/root checks, shell/link/reparse refusal, a rebuilt minimal environment, bounded stdin/stdout/stderr/frame/event handling, strict NDJSON, recursive redaction, cursor replay, timeout handling, and single-terminal-event serialization.
- Added confirmed POSIX and Windows process-tree termination helpers while preserving `run_trusted_argv`; Windows taskkill failures remain explicitly unconfirmed.
- Added Windows-focused registry, process, process-tree, consumer-cancellation, coordinator ambiguity, security-boundary, and regression coverage.

### Files Modified
- `corvus/infrastructure/agent_runtimes/registry.py` - immutable adapter factories, deterministic discovery, capability intersection, and exact runtime routing.
- `corvus/infrastructure/agent_runtimes/process_session.py` - bounded invocation/session/event contracts and strict streaming lifecycle.
- `corvus/infrastructure/agent_runtimes/__init__.py` - exports the Task 2.2 infrastructure surfaces.
- `corvus/application/agent_runtime.py` - revalidates provider preflight models and rejects ambiguous discovery.
- `corvus/safe_process.py` - adds reusable clean-environment, grouped-spawn, path, and confirmed tree-termination helpers without changing the trusted argv API.
- `tests/unit/infrastructure/test_provider_registry.py` - provider registry construction, discovery, routing, intersection, and stable-error coverage.
- `tests/unit/infrastructure/test_process_session.py` - invocation, stream, bounds, redaction, replay, timeout, tree-kill, and cancellation coverage.
- `tests/unit/application/test_agent_runtime_coordinator.py` - ambiguous matching-provider regression.
- `.superpowers/sdd/task-2.2-report.md` - Task 2.2 TDD, verification, security, and stop-boundary evidence.

### Assumptions Made (flag these for review)
- None beyond the confirmed Task 2.2 checklist. Stable reason codes, frozen infrastructure-local process contracts, derived clean environment, conservative named limits, immediate pre-spawn digest pinning, and cross-platform termination rules were confirmed before implementation.

### Known Issues / Deferred
- Cwd containment is not a filesystem sandbox; provider tool/sandbox restrictions remain Task 2.3.
- Digest pinning immediately before spawn is not an atomic OS open/exec guarantee.
- Provider-specific CLI arguments/parsers, API providers, persistence, API/SSE/UI surfaces, and durable process resurrection remain outside Task 2.2.
- Destructive PostgreSQL tests remain intentionally skipped without explicit reset opt-in.

### Suggested Next Steps
- Independently review the Task 2.2 commit and security boundaries.
- Begin Task 2.3 only after Task 2.2 approval.

## 2026-07-17 - Close Task 2.2 process lifecycle release blockers

### What Was Implemented
- Moved bounded stdin delivery into the supervised process lifecycle so stdout/stderr readers, stdin feed/close, process wait, and timeout handling run concurrently without pipe-order deadlock.
- Shielded cancellable process creation, recovered any created handle, and confirmed whole-tree cleanup before propagating caller cancellation.
- Hardened POSIX process-tree termination to probe the process group after leader exit, escalate TERM-ignoring descendants to KILL, and require ESRCH plus leader reaping before reporting confirmation.
- Added large stdout-before-stdin, cancellable spawn with descendant, real POSIX parent-exits-first, and deterministic TERM-to-KILL escalation regressions.

### Files Modified
- `corvus/infrastructure/agent_runtimes/process_session.py` - supervises stdin concurrently and recovers cancelled spawn handles for confirmed cleanup.
- `corvus/safe_process.py` - confirms POSIX process-group absence rather than trusting leader exit.
- `tests/unit/infrastructure/test_process_session.py` - covers pipe-order progress and spawn-cancellation tree cleanup.
- `tests/unit/test_safe_process.py` - covers real and deterministic parent-exits-first descendant termination.
- `.superpowers/sdd/task-2.2-report.md` - records the two High repairs, evidence, and consolidated-gate boundary.

### Assumptions Made (flag these for review)
- None. The concurrent stdin lifecycle, shielded spawn recovery, ESRCH-only POSIX absence proof, no-full-suite deadline boundary, and exact stop boundary were explicitly confirmed.

### Known Issues / Deferred
- The real POSIX regression is skipped on Windows and will run in the existing Linux/macOS matrix; deterministic escalation logic is covered locally.
- The fresh 5.5-minute full suite is intentionally deferred to the single final consolidated vertical-MVP release gate; focused runtime/security/static gates cover this repair commit.
- Provider-specific adapters and all Task 2.3 work remain out of scope.

### Suggested Next Steps
- Independently re-review the two Task 2.2 High repairs.
- Begin Task 2.3 only after approval.

## 2026-07-17 - Ship truthful same-device Codex chat MVP

### What Was Implemented
- Added a bounded, text-only Codex CLI adapter that pins the executable, runs without a shell in a read-only sandbox, redacts diagnostics, rejects tool events, normalizes run events, and supports cancellation.
- Added paired-session local chat routes for idempotent run start, owner-scoped signed-cursor SSE replay, and cancellation.
- Kept run handles/events in daemon memory and explicitly labels responses as `this_device`; transcripts remain client-local and no Task 2.1 conversation persistence is claimed or written.
- Uses the user's configured Codex default by omitting `--model`; optional model identifiers are strictly bounded and cannot inject flags.

### Files Modified
- `corvus/infrastructure/agent_runtimes/codex.py` - bounded local Codex process adapter.
- `corvus/mvp/local_chat.py` - owner-scoped in-memory local run service and Codex backend bridge.
- `corvus/mvp/api.py` - authenticated/CSRF-protected local chat start, SSE, and cancel routes.
- `tests/contract/providers/test_codex_adapter.py` - adapter bounds, normalization, redaction, cancellation, and model validation.
- `tests/mvp/test_local_chat_api.py` - route auth, isolation, idempotency, cursor, cancellation, and redaction coverage.

### Assumptions Made (flag these for review)
- None. The hackathon scope was explicitly narrowed to a truthful same-device local Codex flow with daemon-lifetime events and client-local transcripts.

### Known Issues / Deferred
- Runs and server-side events do not survive daemon restart; cross-device sync and durable conversation storage are deferred.
- Cloud runtimes, API-key providers, tools, repository writes, scheduling, and full-auto execution are not included in this slice.
- The Codex executable must be locally installed and authenticated; unavailable installations return a stable service error.

### Suggested Next Steps
- Connect the device-local web transcript adapter to these routes and verify the desktop flow visually.
- Add durable/cloud execution only through the separately authorized runtime and identity milestones.

## 2026-07-17 - Deliver hackathon chat-first product vertical

### What Was Implemented
- Added a chat-first local workspace with versioned device-only threads, transcript, composer, Local Codex/default-model controls, durable SSE output, stop control, and Plan-to-Work-to-Result run status.
- Added real Schedule/Routines create, list, and run-now surfaces over the existing authorized routine APIs while labeling timed recurrence Coming soon.
- Added real Settings for light/dark/system theme, response tone, custom rules, synced profile changes on hosted accounts, and truthful MCP/integration placeholders.
- Reordered all four adaptive persona/workspace profiles around Conversations/Threads and Schedule while preserving distinct everyday/developer and individual/team information density.
- Kept Google-first hosted onboarding, local pairing, authority, sync, Cloud Preview, and local-runtime handoff boundaries intact.

### Files Modified
- `apps/web/src/App.tsx` - wires local chat, routines, settings, theme restoration, and chat-first local navigation.
- `apps/web/src/app/ConversationWorkspace.tsx`, `conversationApi.ts`, and `conversationStorage.ts` - paired Local Codex execution, SSE presentation, cancellation, and strict device-only transcript storage.
- `apps/web/src/app/SettingsPanel.tsx` and `devicePreferences.ts` - account profile control plus versioned workspace/device settings.
- `apps/web/src/app/RoutinesWorkspace.tsx` - authorized routine creation and run-now surface.
- `apps/web/src/app/workspaceProfiles.ts` - four coherent chat-first navigation profiles.
- `apps/web/src/styles/product-workspace.css` and `apps/web/src/main.tsx` - responsive product UI and explicit theme tokens.
- Focused and integration web tests - RED/GREEN coverage for storage, API proofs, chat/run/stop, settings, routines, profiles, and legacy navigation.

### Assumptions Made (flag these for review)
- The local-chat contract confirmed during implementation is stable: paired `corvus_session`, legacy CSRF, idempotency key, Local Codex configured default, cookie-auth SSE, and device-only storage labeling.
- Direct loopback sessions do not invent a synced persona; profile editing is disabled there and points to the signed-in web app.

### Known Issues / Deferred
- Conversation transcript synchronization, Cloud execution, E2B, additional model providers, executable MCP connections, integration OAuth, timed recurrence, advanced team administration, and billing remain deferred.
- Responsive Computer Use screenshots and real desktop acceptance are owned by the consolidated root verification pass.

### Suggested Next Steps
- Run the paired local-chat backend and complete desktop/mobile Computer Use acceptance.
- Review the combined backend/frontend vertical before the single hackathon PR.
