# Corvus M2-M11 Hackathon MVP Status

This is a hackathon MVP implementation record, not formal M2-M11 certification.

## Baseline and branch

- Verified baseline: `repair/m1-certification` at `8c18f53`.
- Original implementation branch: `hackathon/m2-m11-mvp`; current fast-forward integration branch: `codex/main-integration`.
- GitHub `main` contains the verified M2-M11 hackathon implementation through `424aeb6`; the final acceptance evidence follows as a documentation-only release commit.
- M0.5/M1 history and frozen `corvus` CLI behavior remain intact. Additive MVP code lives under `corvus.mvp`, uses `mvp_*` SQLite tables, and exposes a separate `corvus-mvp` command.

## Architecture

- `CorvusService` is the authoritative workflow, effect, approval, budget, artifact, conversation, and event core.
- `GovernanceService`, `OfflineConnectorService`, and `ChannelIngressService` share the same transactional SQLite store.
- CLI, FastAPI, generated TypeScript client, and React UI are thin adapters. They do not duplicate authority rules.
- Credentials persist only as `env://` or `keyring://` references and are resolved only by the broker at an effect boundary.
- Signed connector/channel envelopes remain proposals or untrusted input; server-side identity and authorization decide what is accepted.

## Adaptive application shell (Milestone 1)

- The shared React client now starts with a versioned three-step chooser for Everyday/Developer, Personal/Team, and Local/Corvus Cloud.
- Local is operational on the existing authoritative same-machine API and supervised Tauri sidecar. Corvus Cloud is explicitly labeled Preview and exposes no fake identity, purchase, or payment success.
- One shell composes four distinct navigation/copy profiles without duplicating workflow, authority, approval, budget, audit, or credential logic.
- Team selection is capability-honest and grants no membership or permissions; real shared collaboration remains deferred to its authorized database milestone.
- Responsive behavior includes desktop rail/inspector, mobile bottom navigation and profile sheet, full-screen mobile inspector, focus restoration, skip navigation, and reduced-motion handling.

## Agent runtime foundation (M2A candidate)

- Strict agent-run contracts bind the complete request, provider binding version/digest, executable or credential identity, model, scope, authorization snapshot, autonomy, credential, budget, kill-switch, sandbox, network, filesystem, tool, and idempotency inputs.
- A verified agent-run authorization adapter reuses the canonical capability-intersection and authorization-snapshot verification core; it does not introduce a second policy engine.
- Start, resume, cancel, event streaming, and audit receipts reject substituted runtime identities, non-proof resume changes, invalid event ordering, duplicate provider events, secret-bearing payload keys, and unacknowledged or tampered audit outcomes.
- Capability discovery is fail-closed and typed. The only executable runtime remains deterministic/local; live Codex, Claude, Gemini, Cursor, and xAI/Grok adapters are not yet connected.
- Durable provider binding, autonomy, credential, budget, kill-switch, and post-effect audit-reconciliation repositories remain an explicit later milestone. M2A does not claim those production integrations.

## Install and run

```powershell
uv sync --all-groups --locked
cd apps/web
pnpm install --frozen-lockfile
pnpm build
cd ../..
```

Migrations run transactionally when the SQLite-backed service opens.

```powershell
$env:CORVUS_BOOTSTRAP_TOKEN = '<one-time-pairing-value>'
$env:CORVUS_SESSION_SECRET = '<at-least-32-byte-signing-value>'
uv run corvus-mvp server --database corvus-mvp.sqlite3
```

In a second terminal:

```powershell
cd apps/web
pnpm dev
```

Open `http://127.0.0.1:5173`, pair once, then use Execution and Operations. For a CLI-only durable demo:

```powershell
uv run corvus-mvp demo --database corvus-mvp.sqlite3 --json
uv run corvus-mvp workflow inspect <WORKFLOW_ID> --database corvus-mvp.sqlite3 --json
uv run corvus-mvp capabilities-demo --database corvus-mvp.sqlite3 --json
```

For the production-style, single-origin local path, build once and let FastAPI serve the real web client:

```powershell
cd apps/web
pnpm build
cd ../..
uv run corvus-mvp server --database corvus-mvp.sqlite3 --static-web-dir apps/web/dist
```

The reproducible self-host container path is:

```powershell
Copy-Item .env.example .env
# Replace both demo secret values in .env, then:
docker compose up --build
```

Build the wheel and bind it plus the static asset inventory into SBOM/provenance output:

```powershell
uv build --wheel
uv run python -m scripts.generate_supply_chain --artifact dist/corvus-0.2.0a1-py3-none-any.whl --static-dir apps/web/dist
```

Build and launch the Windows desktop shell from a Visual Studio Developer PowerShell:

```powershell
$env:PATH = "C:\Users\lucas\.cargo\bin;$env:PATH"
$env:CORVUS_SIDECAR_EXECUTABLE = (Resolve-Path .venv\Scripts\corvus-mvp.exe).Path
pnpm --dir apps/desktop install --frozen-lockfile
pnpm --dir apps/desktop tauri build --no-bundle
& apps\desktop\src-tauri\target\release\corvus-desktop.exe
```

## Concise end-to-end demo

The CLI demos use the same SQLite core as HTTP, web, and desktop and emit identifiers for inspection:

```powershell
$db = Join-Path $env:TEMP "corvus-acceptance.sqlite3"
Remove-Item $db -ErrorAction SilentlyContinue
$run = uv run corvus-mvp demo --database $db --json | ConvertFrom-Json
uv run corvus-mvp workflow inspect $run.workflow_id --database $db --json
uv run corvus-mvp capabilities-demo --database $db --json
pnpm --dir apps/web build
```

`demo` creates the project, versioned outcome, dependency graph, attempts, leases, checkpoints, artifacts/lineage, conversation/events, approval replay, and settled budget, then reopens SQLite before reporting success. `capabilities-demo` exercises team/provider references, shadow autonomy, governed memory, an active versioned skill and routine, offline queue/reconciliation, signed channel identity/step-up, and duplicate-safe replay. Start the documented single-origin server to inspect the same durable run through CLI and web/SSE; launch the desktop command above to use that same client in Tauri.

## Milestone status

### Implemented and locally verified

- **M2:** durable outcomes, dependency graphs, legal states, scheduler, attempts, fenced leases/heartbeat/recovery, checkpoints, artifacts/lineage, conversations/events, typed effects, deterministic idempotency, one-time approval decisions, budget reservation/settlement/release, kill switches, controls, and restart persistence.
- **M3:** additive project/outcome/workflow CLI, workflow inspection, configuration checking, durable demo, and governed capabilities demo over application services.
- **M4:** one-time pairing, signed cookie sessions, CSRF/origin checks, tenant-scoped API, typed OpenAPI responses/errors, workflow controls, team/provider/memory/skill/routine/offline/channel routes, signed HTTP channel ingress, and bounded resumable SSE.
- **M5:** generated OpenAPI TypeScript client; connected React pairing, project/outcome/workflow execution, dependency rail, live SSE activity, approval inbox with approve/reject, budget and kill controls, artifacts/conversation inspector, collaboration/provider/autonomy controls, governed memory, skills/routines, and offline/channel visibility. Desktop and mobile browser paths were exercised.
- **M6:** teams/memberships, owner authorization, provider references/grants, secret broker, simulated OAuth PKCE/device flow, shadow decisions, and evidence-gated autonomy promotion.
- **M7:** governed memory with untrusted retrieval, versioned active skills, routines, and authorized routine runs.
- **M8:** Ed25519-signed offline intents, disconnect/queue/reconcile, duplicate-safe application, and restore quarantine.
- **M9:** Ed25519-signed channel envelopes, expiry/digest/signature checks, identity mapping, deduplication, persisted results, step-up state, and real HTTP ingress.
- **M10:** validated local/self-host configuration, tenant isolation queries, simulated OIDC mapping, compiled React assets served by FastAPI on the API origin, non-root multi-stage container/Compose configuration, wheel build, deterministic CycloneDX SBOM, static asset inventory, and artifact-bound provenance.
- **M11:** Tauri v2 Windows shell; validated fixed-argv sidecar launch; starting/ready/reconnecting/failed/stopped supervision; launch-instance-authenticated readiness checks; restart-safe ephemeral session repair; fragment-only one-time pairing; effective HTTP CSP; bounded redacted diagnostics; real compiled web client; graceful window/stdin shutdown with kill fallback; restricted loopback navigation with no remote Tauri IPC; unsigned current-user NSIS packaging; and expiring, rollback-protected, threshold-signed update metadata using explicitly non-production test keys.

### Implemented but not externally exercised

- PostgreSQL configuration recognition, real OAuth/OIDC providers, external secret stores, production key ceremonies, and external channel/provider delivery.

### Scaffolded or partial

- No M2-M11 feature surface is placeholder-only. Production integrations listed below remain outside the hackathon local path.

### Blocked

- Docker/Podman is not installed, so the authored container image has not been built or started on this workstation. The equivalent single-origin source-tree runtime was exercised successfully.

## Verification actually run

- Python: `678 passed` in 77.90 seconds after a clean serial rerun; cancellation proof-digest, nested runtime-result, terminal cancellation-handle, camelCase usage-counter, quoted-secret, secret-shaped-key, authorization-decision, and cancellation-identity regressions passed; full Ruff, Ruff format, and mypy passed.
- API/OpenAPI: focused API suite passed; OpenAPI and generated TypeScript hashes were stable across two consecutive generations.
- Web: `23 passed` across 7 files; Vite production build passed (48 modules, 246.53 kB JS / 74.88 kB gzip).
- M10 packaging: wheel `corvus-0.2.0a1-py3-none-any.whl` built; provenance bound that wheel and a 23-file static manifest; single-origin `/ready`, `/`, and pairing smoke passed and the listener stopped cleanly.
- M11 desktop: Python subprocess two-launch start/HMAC-ready/web/re-pair/persistence/shutdown passed; 5 Rust lifecycle, fixed-launch, fresh-challenge decoy rejection, diagnostic-redaction, and fragment tests passed; Cargo fmt and Clippy with warnings denied passed; the full Tauri release and NSIS build passed; current `cargo check` passed. Windows Computer Use verified all four workspace profiles, the truthful Cloud Preview wall, Local connection, and graceful desktop/sidecar shutdown. The unsigned NSIS `Corvus_0.2.0-alpha.1_x64-setup.exe` remains a non-production artifact.
- Browser: real FastAPI + Vite pairing, project/workflow execution, SSE, approval, budget settlement, team/provider setup, shadow autonomy, untrusted memory retrieval, skill activation, routine run, desktop layout, and 390x844 mobile layout passed. A fresh authenticated tab logged zero console errors or warnings.
- Design blueprint: packet, provenance, source evidence, fixed viewport captures, and responsive visual inspection exist. Its automated gate still fails because the installed auditor unconditionally requires a restaurant `dish-selector`, requires packet approval after edits, and statically scans one React source file at a time; no fake restaurant artifact was added.

## Final 20-point acceptance evidence

1. The install, single-origin server, CLI, web, and desktop startup sequences are documented above.
2. API, real browser, and repeat desktop launch pairing succeeded; the desktop fragment was removed before HTTP traffic.
3. The final CLI acceptance run created a persisted project.
4. It created a versioned outcome and a two-item dependency graph.
5. It started the workflow through the authoritative application service.
6. The scheduler completed both work items with the deterministic executor.
7. CLI inspection found two work items, two artifacts with lineage, 12 events, two conversation entries, and durable attempts/leases/checkpoints in the same SQLite core.
8. The second item required an approval-bearing filesystem effect.
9. The effect executed exactly once; duplicate approval/application tests safely replayed the persisted decision.
10. The 10-unit budget ended with 4 settled, 0 reserved, and 6 available.
11. SSE monotonic replay/reconnect passed in API tests and the real browser execution path.
12. The same durable run was inspected by CLI, API, and connected web controls.
13. The capabilities run connected a provider reference and returned supervised autonomy after shadow/evidence evaluation.
14. Governed memory stored and retrieved external content as untrusted.
15. A versioned active skill completed through a routine.
16. An offline intent queued while disconnected, reconciled as applied, and retained application count 1.
17. A signed channel event mapped identity, required step-up, and retained processing count 1 after retry.
18. The production web application built successfully.
19. The Tauri release executable and unsigned current-user NSIS package built; a real WebView launch rendered the connected UI.
20. The demo reopened the backend store and reported `restart_verified: true`; the desktop also re-paired across launches using the same persisted database.

## Known limitations

- The deterministic local effect adapter returns digest-bound results and does not perform privileged host writes or real provider calls.
- No production cloud, PostgreSQL server, external OAuth registration, notarization, production signing, or multi-OS installer certification was attempted.
- The container definition is authored but not locally exercised because no container engine is installed.
- The NSIS installer is unsigned and does not yet bundle a standalone Python sidecar; local execution uses the validated `CORVUS_SIDECAR_EXECUTABLE` path. No production signing, notarization, or multi-OS certification is claimed.
- Live Codex, Claude, Gemini, Cursor, and xAI/Grok runtime adapters are not connected yet. M2A provides the verified contract and deterministic adapter boundary only.
- Durable current-state repositories for agent provider bindings, autonomy grants, credential proofs, runtime budgets, kill switches, and post-effect audit reconciliation require a later explicitly authorized persistence milestone.
