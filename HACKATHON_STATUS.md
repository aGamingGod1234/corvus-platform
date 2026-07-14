# Corvus M2-M11 Hackathon MVP Status

This is a hackathon MVP implementation record, not formal M2-M11 certification.

## Baseline and branch

- Verified baseline: `repair/m1-certification` at `8c18f53`.
- Original implementation branch: `hackathon/m2-m11-mvp`; current fast-forward integration branch: `codex/main-integration`.
- GitHub `main` contains the verified M2-M5 and M6-M10 contract work through `a6396e4`.
- M0.5/M1 history and frozen `corvus` CLI behavior remain intact. Additive MVP code lives under `corvus.mvp`, uses `mvp_*` SQLite tables, and exposes a separate `corvus-mvp` command.

## Architecture

- `CorvusService` is the authoritative workflow, effect, approval, budget, artifact, conversation, and event core.
- `GovernanceService`, `OfflineConnectorService`, and `ChannelIngressService` share the same transactional SQLite store.
- CLI, FastAPI, generated TypeScript client, and React UI are thin adapters. They do not duplicate authority rules.
- Credentials persist only as `env://` or `keyring://` references and are resolved only by the broker at an effect boundary.
- Signed connector/channel envelopes remain proposals or untrusted input; server-side identity and authorization decide what is accepted.

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

- Python: `452 passed`; repository Ruff passed; strict mypy passed for 87 source files.
- API/OpenAPI: focused API suite passed; OpenAPI and generated TypeScript hashes were stable across two consecutive generations.
- Web: `5 passed`; Vite production build passed (35 modules, 230.86 kB JS / 70.44 kB gzip); `pnpm audit` reported no known vulnerabilities.
- M10 packaging: wheel `corvus-0.2.0a1-py3-none-any.whl` built; provenance bound that wheel and a 23-file static manifest; single-origin `/ready`, `/`, and pairing smoke passed and the listener stopped cleanly.
- M11 desktop: Python subprocess two-launch start/instance-ready/web/re-pair/persistence/shutdown passed; 5 Rust lifecycle, fixed-launch, decoy-readiness, diagnostic-redaction, and fragment tests passed; Cargo fmt and Clippy with warnings denied passed; the full Tauri release and NSIS build passed; the real second-launch WebView was visually confirmed paired; closing the real window stopped both desktop and sidecar processes; unsigned NSIS `Corvus_0.2.0-alpha.1_x64-setup.exe` built.
- Browser: real FastAPI + Vite pairing, project/workflow execution, SSE, approval, budget settlement, team/provider setup, shadow autonomy, untrusted memory retrieval, skill activation, routine run, desktop layout, and 390x844 mobile layout passed. A fresh authenticated tab logged zero console errors or warnings.
- Design blueprint: packet, provenance, source evidence, fixed viewport captures, and responsive visual inspection exist. Its automated gate still fails because the installed auditor unconditionally requires a restaurant `dish-selector`, requires packet approval after edits, and statically scans one React source file at a time; no fake restaurant artifact was added.

## Known limitations

- The deterministic local effect adapter returns digest-bound results and does not perform privileged host writes or real provider calls.
- No production cloud, PostgreSQL server, external OAuth registration, notarization, production signing, or multi-OS installer certification was attempted.
- The container definition is authored but not locally exercised because no container engine is installed.
- The NSIS installer is unsigned and does not yet bundle a standalone Python sidecar; local execution uses the validated `CORVUS_SIDECAR_EXECUTABLE` path. No production signing, notarization, or multi-OS certification is claimed.
