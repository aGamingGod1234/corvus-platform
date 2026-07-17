# Corvus

Corvus is a local-first AI workspace for turning outcomes into governed, auditable work. One authoritative Python core powers the CLI, API, web client, and Windows desktop shell so approvals, budgets, credentials, audit, and kill switches behave the same everywhere.

## Hackathon pitch

Most AI agent products force everyone into the same developer-shaped interface and hide where work actually runs. Corvus gives everyday users, developers, individuals, and teams a familiar workspace while preserving one governed execution core underneath.

The reliable end-to-end demo path is deliberately short:

1. Open the desktop app and choose a work style, workspace scope, and **On this computer**.
2. Start a thread, select a detected local Codex or Claude provider, model, and thinking level, then watch safe reasoning summaries and the answer stream live.
3. Switch Codex from **Chat** to **Build** to execute a coding task in a fresh scratch sandbox.
4. Download the completed project as a bounded ZIP with a SHA-256 manifest.
5. Open Settings to show theme, response style, custom rules, MCP consent, and integration controls.

Cloud, billing, and providers without real adapters remain visibly labeled Preview or unavailable. The demo never implies those paths are complete.

## A workspace that fits the user

Corvus adapts its language and navigation without creating separate products or separate security rules.

| Work style | Personal workspace | Team workspace preview |
| --- | --- | --- |
| Everyday | Home, My Work, Automations, Files | Team Home, Assigned Work, Approvals, Knowledge, People |
| Developer | Repositories, Threads, Changes, Runs, Skills | Repositories, Work Queue, Reviews, Environments, Policies |

The Team profile currently previews the shared-work information architecture. It does not manufacture members, permissions, or authority before the real collaboration capability is connected.

## Choose where Corvus runs

- **On this computer:** operational today. The desktop app supervises the same-machine sidecar, and the browser client can connect to the same local service.
- **Corvus Cloud (E2B):** clearly labeled **Preview**. The current build does not create a cloud sandbox, perform Google sign-in, collect payment, or imply that those paths are available.

Local and future Cloud runtimes share contracts; clients never grant themselves workspace authority.

## What works today

- Durable outcomes, dependency-linked workflows, attempts, leases, checkpoints, artifacts, lineage, conversations, and resumable event streams.
- One-time approvals, deterministic effect idempotency, budget reservation and settlement, kill switches, and restart recovery.
- Connected CLI, FastAPI, generated TypeScript client, React web app, and Tauri Windows shell over the same application services.
- Local/demo collaboration, governed memory, versioned skills and routines, signed offline intents, and signed channel ingress.
- Adaptive Everyday/Developer and Personal/Team workspace profiles with responsive desktop and mobile navigation.
- A security-focused agent-runtime foundation with immutable requests, provider-binding digests, verified authority receipts, bounded autonomy proofs, fail-closed capability discovery, redacted hash-chained events, replay resistance, and explicit audit-pending results.
- A chat-first local agent workspace with on-demand history, provider/model/thinking controls, safe streamed reasoning summaries and work status, explicit MCP opt-in, and downloadable project artifacts.

Local Codex and Claude run through native CLIs detected on the device; the provider verifies its own sign-in when a run starts. Chat is read-only. Codex Build mode uses a fresh workspace-write sandbox, always disables user plugins/apps/hooks, enables MCP only after explicit consent, streams only safe summaries/status, and returns a bounded ZIP with a SHA-256 manifest. Gemini and xAI/Grok are labeled Preview and Cursor is labeled unavailable until real adapters exist. Credentials remain references resolved only at the effect boundary and are never stored in prompts, events, synchronized state, artifacts, or audit output.

## Codex Usage

OpenAI Codex was used as the primary engineering agent for planning, implementation, code review remediation, security hardening, cross-platform CI repair, and end-to-end verification. Corvus also integrates the user's installed Codex CLI as a local runtime: the user can select recommended GPT-5.6 models and thinking levels, stream safe progress, opt into MCP tools, and run a coding task inside the bounded Build workspace before downloading the result.

The final Devpost recording should capture the Codex `/feedback` session ID alongside the sub-three-minute demo. That ID is intentionally not fabricated or committed in advance.

Key Codex-assisted safeguards include fixed-argument process invocation, provider-bound model validation, explicit MCP consent, plugin/app/hook isolation, secret-screened artifact packaging, signed cursors, reconnect-safe event replay, and fail-closed provider discovery.

## Quick start

Requirements:

- Python 3.12
- `uv`
- Node.js and `pnpm`
- Rust/Cargo only when building the desktop shell

Install and build from PowerShell:

```powershell
uv sync --all-groups --locked
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web build
```

Start the same-machine API and compiled web client:

```powershell
$env:CORVUS_BOOTSTRAP_TOKEN = '<one-time-pairing-value>'
$env:CORVUS_SESSION_SECRET = '<at-least-32-byte-signing-value>'
uv run corvus-mvp server --database corvus-mvp.sqlite3 --static-web-dir apps/web/dist
```

Then open the loopback URL printed by the server, normally `http://127.0.0.1:8080`, and pair once. A durable CLI-only demo is also available:

```powershell
uv run corvus-mvp demo --database corvus-mvp.sqlite3 --json
uv run corvus-mvp capabilities-demo --database corvus-mvp.sqlite3 --json
```

Build and run the Windows desktop shell:

```powershell
$env:PATH = "C:\Users\lucas\.cargo\bin;$env:PATH"
$env:CORVUS_SIDECAR_EXECUTABLE = (Resolve-Path .venv\Scripts\corvus-mvp.exe).Path
pnpm --dir apps/desktop install --frozen-lockfile
pnpm --dir apps/desktop tauri build --no-bundle
& apps\desktop\src-tauri\target\release\corvus-desktop.exe
```

## Alpha installers and web deployment

Unsigned alpha desktop installers are built by `.github/workflows/desktop-release.yml` for:

- Windows x64 NSIS: `Corvus_0.2.0-alpha.1_x64-setup.exe`
- macOS x64 DMG
- Linux x64 AppImage and `.deb`

The workflow builds a standalone `corvus-mvp` sidecar with PyInstaller 6.21.0 and packages it with the Tauri shell only when manually dispatched or when a version tag is pushed. Pull requests do not execute release packaging. A GitHub prerelease with `SHA256SUMS.txt` is created only when a reviewed `v0.2.0-alpha.1` tag points to a commit already on `main`.

These installers are intentionally unsigned alpha artifacts. Windows may show SmartScreen warnings, macOS Gatekeeper will treat the DMG as unnotarized, and Linux users may need to mark the AppImage executable. Production signing, notarization, auto-update signing, and release channels remain later work.

The web app is linked to Vercel project `corvus-platform`, connected to `aGamingGod1234/corvus-platform`, with Git root `apps/web` so `main` updates produce production deployments and pull requests produce previews. Current deployment: <https://corvus-platform-tau.vercel.app>. The hosted app keeps Local mode honest: it hands off to the same-machine local runtime and does not receive local pairing secrets or session cookies.

## Development and verification

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
pnpm --dir apps/web test
pnpm --dir apps/web build
& "$HOME\.cargo\bin\cargo.exe" check --manifest-path apps/desktop/src-tauri/Cargo.toml
```

Corvus build execution is fail-closed. Production sandbox images must be digest-pinned, and unavailable container isolation never falls back to privileged host execution. The supported default image is:

```text
python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf
```

## Status and scope

This repository contains the preserved M0.5-M11 hackathon MVP foundation plus the adaptive application shell, Google-backed hosted identity/synchronization foundation, and the local Codex/Claude agent fast track. It is not formal certification. Real E2B lifecycle management, API-key providers, Gemini/Cursor/xAI adapters, durable provider/autonomy/credential/budget/kill repositories, and production signing remain explicit later milestones.

See [HACKATHON_STATUS.md](HACKATHON_STATUS.md) for verified commands and limitations, [ROADMAP.md](ROADMAP.md) for the readable delivery outline, and [PLAN.md](PLAN.md) for the authoritative security specification.

Changes target `main` through ready pull requests. Review findings are fixed on the feature branch before merge; new milestone work is not pushed directly to `main`.

## Attribution

Corvus is developed by Lucas with AI-assisted engineering from **OpenAI Codex**. This is honest tool attribution, not a fabricated GitHub account or identity.

## License

Corvus is proprietary. See [LICENSE.md](LICENSE.md).
