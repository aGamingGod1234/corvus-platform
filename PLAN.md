# Plan: Corvus CLI V2 and Shared Web/Desktop Platform
_Drafted by Codex/Hermes for Gemini review._

## Goal
Evolve the supplied Corvus CLI V1 into one tested, installable, configuration-driven Corvus V2 platform with a single authoritative Python core. Users may interact through CLI, browser web, Tauri desktop, or approved third-party channels; run Corvus for an individual or a team; and host it locally or on Corvus Cloud. The platform must add team-safe identity, scope, authorization, durable work, audit, memory, delegation, routines, budgets, and capability contracts without weakening V1's sandbox, verification, delivery, or rollback guarantees.

The immediate implementation slice will establish the package/test baseline and the first fail-closed team authority boundary. Later slices will expose that same boundary through CLI V2, FastAPI/SSE, a React web workspace, and a Tauri shell that reuses the web UI.

## Product Configuration Matrix

Corvus is one product whose adapters and infrastructure change from an explicit `RuntimeProfile`; it is not four separate products.

### Interaction surface
- `cli`: local in-process mode or remote API client.
- `desktop`: cross-platform Windows/macOS/Linux Tauri client; may supervise an explicit local Corvus service or connect to Corvus Cloud.
- `web`: browser client served by Corvus Cloud or a self-hosted local/team service.
- `channel`: approved Discord, Slack, webhook, or future adapters that submit attributed requests to the same API.

### Agent/infrastructure behavior
- `individual`: one owner, private default workspace, personal memory by default, optional specialist agents, simple local onboarding.
- `team`: memberships, roles, channel/project scopes, reviewer separation, shared memory promotion, hierarchical budgets, comments/approvals, and durable multi-worker infrastructure.

### Hosting location
- `local`: user-controlled machine/server, SQLite for individual development and PostgreSQL for team/self-hosted multi-worker use; local filesystem/object storage adapters; local sandbox runtime.
- `cloud`: Corvus-hosted control plane, PostgreSQL/Redis/object storage, isolated workers/previews, organization/workspace tenancy, managed observability and signed delivery.

### Bring-your-own models
- Corvus does not silently bundle a model entitlement. Users select local models, API providers, or provider-owned OAuth such as Codex/ChatGPT.
- Configuration stores provider metadata and a `CredentialRef`, never plaintext API keys or OAuth tokens.
- Local secrets use the OS credential store; Corvus Cloud secrets use an encrypted workspace vault and scoped broker.
- A cloud run cannot directly use a model reachable only on a user's laptop. That requires an explicit outbound local connector with short-lived mutually authenticated sessions, or the run stays local.
- Model routes, costs, health, capabilities, and failover are runtime configuration; safety policy and evidence requirements remain invariant.

## Context

### Source and baseline
- Repository: `C:/Users/lucas/Projects/corvus-platform`
- Imported V1 baseline commit: `1410d7f`
- Original source manifest: `V1_SOURCE_MANIFEST.json`
- Prior architecture memo: `C:/Users/lucas/AppData/Local/hermes/.ai/HERMES_HANDOFFS/2026-07-13-corvus-web-team-agent-integration.md`
- V1 contains 27 Python files and approximately 9,322 lines.
- V1 version is `0.1.0`; it has no package metadata, lockfile, tests, migrations, README, API, web client, or desktop client.

### Verified V1 evidence
- Intended runtime: Python 3.12.
- Clean `python -m compileall` passes under Python 3.12.10 with contaminated `PYTHONHOME/PYTHONPATH` removed.
- `python -m corvus --help` starts successfully under an isolated Python 3.12 dependency environment.
- `corvus doctor --json` reports:
  - SQLite integrity: pass.
  - Codex CLI discovery: pass.
  - Docker: unavailable.
  - Podman: unavailable.
  - Build sandbox route: fail closed to chat-only.
  - Providers configured in isolated audit home: zero.
- Ruff: all checks passed.
- Secret-pattern scan: no private-key or common live-token signatures found.
- Bandit: zero high-severity findings; 21 low and two medium findings. Its runtime could not parse two Python 3.12 `type` alias modules, so the scan is incomplete until Bandit runs under a 3.12-capable parser.
- Current Mini PC capacity during audit: about 24 GB RAM total, 4.65 GB available, 80.3% used, 24% CPU. Avoid simultaneous heavy Node/Rust/container builds.

### Existing V1 primitives worth retaining
- Typed run phases, acceptance criteria, budgets, policy, approvals, artifacts, checkpoints, memory, skills, and provider models in `corvus/models.py`.
- Docker and Podman sandbox backends with no bind mounts, disabled networking, dropped capabilities, resource limits, non-root users, and validated tar staging in `corvus/sandbox.py`.
- Hash-chained run events and content-addressed artifacts in `corvus/store.py`.
- Manifest-bound packaging, encrypted rollback backups, destination conflict checks, and optional git refs in `corvus/delivery.py`.
- Repair-loop workflow in `corvus/workflow.py`.
- Bounded one-level subagent runtime in `corvus/conversations.py`.
- Provider abstraction, onboarding, Typer CLI, Textual TUI, memory and versioned skill prototypes.

### Architectural gaps that block safe team/web/desktop use
1. `ConversationRuntime` is in-memory while `TraceStore` is durable; refresh/restart loses chats, queues, and events.
2. Run events lack mandatory workspace, project, requester, agent, policy, and access-bundle attribution.
3. Memory is keyed only by project and identity; it lacks personal/thread/channel/workspace scope and reviewed promotion.
4. Policy is path/domain/autonomy oriented, not tenant/resource/action oriented.
5. No durable work item, lease, heartbeat, dependency, retry, routine, or trigger model exists.
6. No API authentication/authorization boundary exists.
7. No migration framework exists; `create_all()` cannot safely evolve existing databases.
8. CLI/TUI modules are large adapters coupled directly to state/config construction.
9. There are no deterministic tests proving sandbox options, event integrity, approval binding, multi-user isolation, or cancellation cleanup.
10. V1 dependency versions are implicit and unreproducible.
11. `PolicyEngine` is not enforced by builds, providers, delivery, memory, or skills; advertised policy is largely disconnected.
12. Build snapshots can include `.env`, credentials, large dependency trees, and other sensitive files; command output is stored and can be sent back to the model as repair context, while plaintext staging is not reliably cleaned up.
13. The generating model chooses its own test commands, `smoke_command` is unused, and repair attempts reuse one staging tree, so trivial or stale-file tests can forge acceptance.
14. Delivery apply validates the manifest body but not each staged file against the approved artifact digest immediately before writing; journal ordering and missing cross-process locks leave crash/TOCTOU gaps.
15. Secret redaction is regex/string-oriented rather than structured-data-aware; provider URLs are not safe for a server threat model; Codex children inherit a broad host environment; artifact digest reads are not strictly validated.

## Refined Specification

### Platform invariants
1. Corvus core is authoritative for identity, scope, policy, work state, events, budgets, approvals, verification, artifacts, and audit.
2. CLI, browser, desktop, Discord, Slack, webhooks, and routines are untrusted clients of the same application services.
3. Every command/run carries an immutable request context: workspace, project when applicable, requester, channel/thread when applicable, acting agent, access-bundle ID, policy digest, correlation ID, and idempotency key.
4. Missing or mismatched identity/scope/capability information fails closed.
5. Cross-scope memory reads and promotions require explicit policy and provenance; private memory never silently becomes team memory.
6. Workers acquire durable leases with expiry and heartbeat; stale work is recoverable without duplicate side effects.
7. Implementers cannot approve their own unsupported completion claims.
8. Automated routines use the same authorization, budget, sandbox, verification, and audit path as interactive runs.
9. Progress comes only from persisted backend events; clients never synthesize progress timers.
10. Sandboxes receive approved snapshots and scoped broker responses only; they never receive host credentials or direct host filesystem access.
11. Web previews use a distinct hostile-content origin and never receive Corvus auth tokens.
12. Completion is proof-carrying: every required acceptance criterion must pass or the run uses an honest partial/failed/blocked status.

### V2 client contract
- CLI V2 calls application services in-process for an explicit local profile or over HTTP for local-server/Corvus-Cloud profiles.
- Web uses authenticated FastAPI endpoints plus replayable SSE using durable event IDs; the same build can target Corvus Cloud or a self-hosted endpoint.
- Desktop uses Tauri and the same React client package. It may connect to Corvus Cloud or explicitly supervise a least-privilege loopback local service; it never gains authority merely because it is native.
- Third-party channels authenticate as channel/service principals and preserve the human requester, workspace, project, guild/channel/thread, and access-bundle attribution.
- Shared OpenAPI-generated TypeScript contracts prevent client-defined authority or duplicated state machines.

## Explicit Non-Goals for the Immediate Slice
- No production cloud deployment.
- No live Slack/Discord bot or Claude Tag embedding.
- No billing, purchases, or automatic external communications.
- No Docker installation or sandbox weakening on this host.
- No arbitrary MCP server execution.
- No public sharing or preview proxy yet.
- No provider credential migration.
- No automatic migration of an unknown production V1 database; only a tested local schema bootstrap and an explicit migration path.
- No complete UI workspace in the first slice.
- No recursive agents, autonomous skill self-promotion, or self-modifying safety policy.

## Recommended Repository Layout

```text
corvus-platform/
  corvus/                     # Authoritative Python core and local CLI adapter
    application/              # Use cases; no Typer/FastAPI/Textual imports
      authorization.py
      audit.py
      projects.py
      work_items.py
    domain/                   # Pure typed contracts and invariants
      identity.py
      scope.py
      access.py
      work.py
      events.py
      memory.py
    infrastructure/
      db.py
      repositories/
      sandbox/                # Gradually absorbs existing sandbox.py
      providers/              # Gradually absorbs existing providers modules
    api/                      # Thin FastAPI adapter, auth dependencies, SSE
    cli/                      # Thin Typer adapter after decomposition
    ...existing V1 modules during incremental migration
  apps/
    web/                      # Vite + React + TypeScript browser client
    desktop/                  # Tauri wrapper reusing web UI/assets
  packages/
    client-ui/                # Shared React workspace UI for web/desktop
    contracts/                # Generated OpenAPI TS types/client
  migrations/                # Alembic migrations
  tests/
    unit/
    integration/
    contract/
    security/
    e2e/
  examples/
  docs/
  pyproject.toml
  uv.lock
  package.json
  pnpm-workspace.yaml
  PLAN.md
  PLAN-REVIEW-LOG.md
```

### Incremental-layout rule
Do not move the 9k-line V1 package wholesale. Add clean seams and migrate one adapter/use case at a time. Existing `corvus.cli`, `corvus.tui`, `corvus.workflow`, `corvus.delivery`, and provider behavior remain callable while tests are introduced.

## V1 Reuse / Refactor / Replace Map

| V1 path | Decision | V2 treatment |
|---|---|---|
| `corvus/models.py` | Refactor gradually | Keep existing public models; move new team contracts into focused domain modules to avoid one larger model file. Export compatibility aliases where useful. |
| `corvus/security.py` | Reuse and harden | Retain path/link protections, atomic writes, hashing, and redaction; add bounded/typed redaction tests and broker-safe structures. |
| `corvus/store.py` | Refactor | Keep event hashing and artifact addressing; split DB bootstrap/repositories; add migrations and mandatory scoped audit records. |
| `corvus/conversations.py` | Replace runtime state, reuse bounds | Preserve limit/delegation semantics, but back chats/messages/queues/events with durable work and event repositories. |
| `corvus/policy.py` | Extend | Keep path/domain/autonomy checks; add resource/action/scope access evaluation and deny precedence. |
| `corvus/sandbox.py` | Reuse behind protocol | Keep fail-closed Docker/Podman implementations; test options and lifecycle through fakes. No host-process fallback for builds. |
| `corvus/workflow.py` | Refactor into use case | Preserve snapshot/generate/verify/package loop; require authenticated request context, durable work state, test evidence, and policy receipts. |
| `corvus/delivery.py` | Reuse and harden | Keep manifest binding/conflict detection/rollback. Add scanner inputs, replay-resistant approvals, archive export, and ownership checks later. |
| `corvus/verification.py` | Extend | Generalize sandbox protocol, persist evidence metadata, and enforce required/optional criteria honestly. |
| `corvus/memory.py` | Replace schema/API | Add scope kind, owner, visibility, provenance, promotion workflow, and authorization on every read/write. |
| `corvus/skills.py` | Extend | Bind versions to workspace, capability manifest, signer/digest, evaluator identity, and promotion audit. |
| `corvus/providers.py`, `provider_control.py`, `model_catalog.py`, `codex_cli.py` | Reuse behind routing service | Preserve transports; add provider health, capability declarations, budget-aware routing, and failover receipts later. |
| `corvus/cli.py` | Decompose | Keep command compatibility; introduce `v2` project/access/work/run commands backed by application services. |
| `corvus/tui.py` | Retain as CLI client | Stop it constructing authority directly; make it consume application services/events. |
| `corvus/onboarding*.py` | Retain, adapt later | Add local/remote mode and workspace selection after application boundary exists. |

## Core Data Model

All identifiers are opaque UUIDs. Every persistent row includes `created_at`, and mutable rows include `updated_at` plus optimistic `version`.

### Runtime configuration
- `RuntimeProfile(id, owner_principal_id, interaction_surface[cli|desktop|web|channel], collaboration_mode[individual|team], hosting_mode[local|cloud], api_endpoint?, storage_profile, queue_profile, sandbox_profile, model_route_set_id, feature_flags, version)`
- `ModelRouteSet(id, workspace_id?, routes, budget_policy_id, failover_policy)`
- `CredentialRef(id, workspace_id?, owner_principal_id, provider, kind[os_keyring|cloud_vault|provider_oauth|local_connector], locator, scopes, status, expires_at?)`
- Runtime profiles choose adapters and defaults; they cannot disable immutable safety, audit, authorization, verification, or evidence requirements.

### Tenancy and identity
- `Workspace(id, name, status)`
- `WorkspaceMembership(workspace_id, principal_id, role, status)`
- `Project(id, workspace_id, name, root_locator, privacy, status)`
- `Principal(id, kind[user|service|channel], external_provider, external_subject, display_name)`
- `AgentIdentity(id, workspace_id, name, role, model_route, skill_set_digest, status)`
- `ScopeRef(workspace_id, project_id?, channel_id?, thread_id?, conversation_id?)`

### Access
- `AccessBundle(id, workspace_id, principal_id, scope, issued_by, policy_digest, expires_at, revoked_at?)`
- `CapabilityGrant(bundle_id, resource, action, effect[allow|deny], constraints_json)`
- Deny wins. No grant means deny. Scope matching must never broaden a grant.
- Short-lived signed transport tokens may reference an access bundle but cannot replace the server-side bundle/revocation check.

### Requests, audit, and approvals
- `RequestContext(id, runtime_profile_id, workspace_id, project_id?, requester_id, channel_id?, thread_id?, agent_id, access_bundle_id, policy_digest, idempotency_key, correlation_id)`
- `AuditReceipt(id, request_context_id, action, resource, decision, reason_code, policy_digest, sanitized_input_digest, output_digest?, external_effects_json, cost_json, evidence_ids, previous_hash, receipt_hash)`
- `AuditCheckpoint(id, workspace_id, through_sequence, receipt_hash, signer_key_id, signature, anchored_at)`; the signing key lives in OS keyring/cloud KMS, not the ledger database.
- `ApprovalRequest(id, request_context_id, action, manifest_digest, required_reviewer_role, status, expires_at, nonce_digest)`
- `ApprovalDecision(id, approval_request_id, reviewer_id, decision, rationale, decided_at)`
- Implementer/reviewer separation is validated server-side.

### Durable work
- `WorkItem(id, workspace_id, project_id?, parent_id?, kind, state, priority, payload_json, required_capabilities, budget_json, max_attempts, attempt_count, available_at, version)`
- `WorkDependency(work_item_id, dependency_id, condition)`
- `WorkLease(work_item_id, worker_id, lease_token_digest, acquired_at, heartbeat_at, expires_at)`
- `WorkAttempt(id, work_item_id, agent_id, started_at, finished_at?, outcome?, error_code?, cost_json, evidence_ids)`
- State machine: `queued -> leased -> running -> waiting_approval|waiting_dependency|paused -> verifying -> packaging -> completed|failed|cancelled|expired`.
- Compare-and-swap version and lease token prevent duplicate completion.

### Routines and triggers
- `Routine(id, workspace_id, project_id?, name, trigger_type, trigger_config, command_template, access_bundle_id, budget_json, enabled)`
- `TriggerReceipt(id, routine_id, external_event_id, payload_digest, received_at)` with unique dedupe key.
- Every trigger creates a normal `RequestContext` and `WorkItem`.

### Memory
- `MemoryRecord(id, workspace_id, scope_kind[personal|thread|project|channel|workspace], scope_id, owner_principal_id?, visibility, kind, content, provenance_json, confidence, status, expires_at?)`
- `MemoryPromotion(id, source_memory_id, target_scope_kind, target_scope_id, requested_by, reviewed_by?, status, rationale)`
- Reads require both scope membership and explicit capability.

### Skills and capabilities
- `Skill(id, workspace_id, name)`
- `SkillVersion(id, skill_id, version, content_digest, source, permissions, capability_manifest_id, evaluation, status, created_by, reviewed_by?)`
- `CapabilityManifest(id, provider, name, version, operations, risk_class, input_schema_digest, network_constraints, secret_requirements)`
- Promotion requires passing evaluation and reviewer separation for privileged capabilities.

### Budgets
- Budget layers: workspace -> project -> routine/channel -> run -> agent/subagent.
- Effective budget is the minimum remaining allowance at every layer.
- Reservations and actual usage are persisted; cancellation releases only unused reservations.

## Authoritative Events and State Machine

### Event envelope V2
Every durable event includes:
- `schema_version`
- `event_id`
- `sequence`
- `workspace_id`
- `project_id` when applicable
- `run_id`
- `work_item_id` when applicable
- `request_context_id`
- `requester_id`
- `agent_id`
- `event_type`
- `phase/state`
- timestamp
- redaction status
- visibility level
- structured payload
- previous hash
- event hash

### Rules
1. Event append and state transition occur in one database transaction.
2. Invalid state transitions are rejected before event creation.
3. SSE replay uses durable event IDs/sequence and workspace authorization on every connection and replay query.
4. Redaction happens before hashing/persistence.
5. Clients derive display state from snapshots plus events but never write state directly.
6. `run.completed` can only follow passed required criteria and a valid package/evidence record.

## API and Client Architecture

### Runtime topology resolution
- Startup loads and validates one `RuntimeProfile`, resolves only the adapters required by that profile, and records the profile digest on every request/run.
- `individual + local` can use an implicit private workspace and SQLite while still passing through the same authorization and audit services.
- `team + local` is a self-hosted server profile and must use explicit authentication, TLS when network-exposed, PostgreSQL before multi-worker operation, and the same tenant-isolation tests as cloud.
- `individual + cloud` is a private Corvus Cloud workspace with user-provided model credentials stored in the cloud vault.
- `team + cloud` adds memberships, organization policy, shared budgets, reviewer separation, queues, and isolated workers.
- Client surface does not determine authority: CLI, desktop, web, and channel adapters all construct the same server-validated request context.

### FastAPI
- Authentication adapter maps a session/API token to a `Principal`.
- Authorization dependency resolves the exact `RequestContext` and server-side `AccessBundle`.
- Initial endpoints:
  - `GET /api/v2/meta`
  - `POST /api/v2/workspaces`
  - `POST /api/v2/projects`
  - `GET /api/v2/projects/{id}`
  - `POST /api/v2/work-items`
  - `GET /api/v2/work-items/{id}`
  - `GET /api/v2/events?after=<sequence>` (SSE)
  - `POST /api/v2/access/explain` (safe decision explanation, no secret policy dump)
- OpenAPI is the source for TypeScript contracts.

### Web
- Vite + React + TypeScript, TanStack Router and Query.
- `packages/client-ui` owns accessible layout/components and consumes generated contracts.
- The first web slice authenticates, lists/creates a project, submits a work item, reconnects to SSE, and renders only persisted events.

### Desktop
- Tauri wraps the same React client/UI package.
- Desktop can switch between an explicit local profile and a Corvus Cloud profile. It stores only credential references/session material in the OS credential store.
- Native commands are allowlisted; no generic shell command bridge.
- Local mode may supervise a loopback FastAPI process with an ephemeral token, strict origin checks, bounded lifecycle, and visible status; this is configuration-driven rather than a hidden privileged daemon.

### Third-party channels
- Channel adapters are thin authenticated ingress/egress clients.
- A channel binding maps provider/guild/channel/thread to a Corvus workspace/project and allowed agent identity.
- Channel messages never carry reusable model credentials and cannot broaden the bound access bundle.
- Replies, approvals, files, and external effects are attributed to both the channel principal and initiating human where the provider supplies that identity.

## Implementation Approach and Checkpoints

### Milestone 0 — Reproducible V1 baseline
1. Add `pyproject.toml` with Python `>=3.12,<3.14`, runtime dependencies inferred from imports, CLI entry point, Ruff/Pytest configuration, and dev dependencies.
2. Generate and commit `uv.lock`.
3. Add `README.md` with isolated Windows invocation and fail-closed sandbox statement.
4. Add golden smoke/JSON-schema tests for every public V1 command, plus focused event-chain, path-traversal, sandbox-option, and delivery-approval regression tests.
5. Define V2 identifier rules, command envelope, event envelope, error schema, protocol version, and database migration version before client work.
6. Build hashed V1 fixtures and an idempotent importer for onboarding/provider metadata and keyring references, memories, skills, run events, bundles, artifacts, and backups.
7. Add CI commands as local scripts/config only; do not publish.

Checkpoint: existing CLI help and doctor behavior pass from `uv run corvus`; the importer runs twice without duplication and leaves the source fixture readable.

### Milestone 0.5 — Release-blocking V1 safety hardening
1. Enforce a snapshot/export policy before any model call: default secret/cache/dependency exclusions, approved include overrides, file/count/byte limits, link/reparse rejection, and guaranteed cleanup.
2. Redact structured mappings/lists recursively before serialization; register brokered secrets with the redactor; bound persisted/model-returned command output.
3. Separate candidate generation from verification policy. Run server/repository-selected required checks plus any model suggestions; execute smoke checks; rebuild a fresh staging tree for each repair attempt; package exactly the tree that passed.
4. Verify every staged bundle artifact digest immediately before apply; persist/flush rollback intent before mutation; use destination/bundle locks; consume durable actor-bound approvals once.
5. Make an empty/nonexistent audit chain invalid, strictly validate artifact digests, fix optional token-budget narrowing, validate provider URLs/host classes, and use a minimal child-process environment allowlist.
6. Pin sandbox images by digest for production profiles and enforce complete snapshot/candidate/command/output/workflow resource bounds.

Checkpoint: adversarial secret-exfiltration, forged-verification, stale-staging, altered-bundle, crash-point, SSRF, environment-leak, and audit-tamper tests pass before V2 is marked installable.

### Milestone 1 — Team authority foundation (immediate feature slice)
1. Add pure domain types for runtime profiles, credential references, principals, agents, scopes, request contexts, capabilities, access bundles, decisions, effective capabilities, and audit receipts.
2. Add fail-closed `AccessEvaluator` with deny precedence, exact workspace ownership, non-broadening scope matching, expiry/revocation, and resource/action constraints.
3. Add canonical hashing for policy/access bundles and audit receipts plus a signer port for HMAC/KMS-backed periodic audit checkpoints stored outside the mutable ledger database.
4. Add new scoped audit tables/repository without mutating V1 event rows yet.
5. Add application service `authorize_and_record()` that writes an immutable allow/deny receipt.
6. Add runtime-profile resolution that returns an `EffectiveCapabilities` projection for CLI/web/desktop/channel clients without allowing feature flags to disable immutable safety.
7. Add CLI V2 commands:
   - `corvus v2 access check --context <json> --resource <name> --action <name>`
   - `corvus v2 audit verify --workspace <uuid>`
   - `corvus v2 profile explain --profile <path>`
   These are local administrative/developer commands, not a production auth interface.
8. Keep existing commands unchanged.

Checkpoint: two different workspaces cannot read or authorize each other's bundle or receipts; every decision has a verifiable hash chain and signed checkpoint; profile capability projections are deterministic across client surfaces.

### Milestone 2 — Durable work and scoped events
1. Add work item, dependency, lease, attempt, and state-transition tables.
2. Implement transactional claim/heartbeat/release/complete using optimistic versions and lease token digests.
3. Add V2 event envelope and state/event transaction service.
4. Add deterministic crash/reclaim, cancellation, retry, dependency, and idempotency tests.
5. Adapt `ConversationRuntime` to enqueue durable work instead of owning ephemeral truth.

Checkpoint: restart simulation preserves queue, event replay, and cancellation; stale leases can be recovered exactly once.

### Milestone 3 — CLI V2 project/run vertical slice
1. Add workspace/project commands and local identity bootstrap.
2. Adapt one build workflow through request context -> authorization -> work item -> sandbox protocol -> verification -> package -> approval.
3. Use a fake sandbox/provider in tests and require Docker/Podman only for marked integration tests.
4. Add pause/resume/cancel/retry and event-tail commands.

Checkpoint: a fake-provider website build executes the real state machine and produces a verifiable bundle without host writes; live build remains blocked without a sandbox.

### Milestone 4 — FastAPI and SSE
1. Add FastAPI adapter, local test auth, production auth interface, OpenAPI, and replayable SSE.
2. Enforce workspace/project authorization on every route and SSE query.
3. Add API contract and cross-tenant security tests.
4. Generate TypeScript contracts.

Checkpoint: unauthorized workspace/project/event access returns 404/403 as designed without existence leakage; SSE reconnect replays exactly once.

### Milestone 5 — Web fork
1. Scaffold pnpm workspace, `apps/web`, `packages/client-ui`, and `packages/contracts`.
2. Implement login/session shell, project creation, work submission, event timeline, criteria, files/evidence placeholders backed only by real API data.
3. Add Vitest/component tests, Playwright API-backed e2e, accessibility checks, and responsive visual QA.

Checkpoint: browser creates project, submits fake-provider run, refreshes, reconnects, and sees persisted evidence; no timer-generated progress.

### Milestone 6 — Desktop fork
1. Scaffold Tauri in `apps/desktop` reusing web assets/client UI.
2. Add API endpoint configuration and OS credential-store session handling.
3. Lock Tauri capabilities to network/session configuration only; no shell/filesystem wildcard.
4. Add Rust tests/config validation and desktop smoke test if Rust/WebView2 are available.

Checkpoint: desktop runs the same project/work/event flow against the test API; capability audit contains no generic shell or unrestricted filesystem access.

### Milestone 7 — Team collaboration, memory, routines, skills, provider routing
Incrementally add scoped memory promotion, comments/approvals, channel bindings, routines/webhooks, budget hierarchy, skill evaluation/promotion, MCP capability manifests, model routing/failover, checkpoints/branching, and capability metrics. Every addition uses the same request context, policy, work, event, and audit services.

## Immediate TDD Task List

### Task 0.1 — Packaging baseline
- Create: `pyproject.toml`, `README.md`.
- Create tests: `tests/unit/test_version.py`, `tests/cli/test_cli_smoke.py`.
- First failing assertions:
  - package metadata exposes `corvus==0.2.0a1`.
  - `corvus --help` exits 0.
  - `corvus doctor --json` returns Python 3.12 and valid SQLite status in an isolated `CORVUS_HOME`.
- Implement minimal packaging/version change.
- Verify: `uv sync --all-groups --locked`; `uv run pytest tests/unit/test_version.py tests/cli/test_cli_smoke.py -q`.

### Task 0.2 — Security regression baseline
- Create tests:
  - `tests/security/test_paths.py`
  - `tests/security/test_sandbox_options.py`
  - `tests/security/test_delivery_approval.py`
  - `tests/integration/test_trace_store.py`
- Cover path traversal, symlink/reparse rejection where supported, network-disabled sandbox options, approval expiry/mismatch/conflict, event redaction and chain tampering.
- Do not alter behavior unless a test exposes a real defect.

### Task 0.3 — Secret-safe snapshots and repair isolation
- Create tests: `tests/security/test_snapshot_policy.py`, `tests/security/test_secret_flow.py`, `tests/security/test_workflow_repair_isolation.py`.
- Modify: `corvus/workflow.py`, `corvus/security.py`; introduce a focused snapshot policy module only if needed.
- First failing assertions: `.env`/credential/cache/dependency paths are excluded by default; limits block oversized trees; plaintext staging is removed; model repair context is redacted/bounded; each attempt starts from a clean approved snapshot.

### Task 0.4 — Trustworthy verification
- Create tests: `tests/security/test_verification_trust.py` and extend `tests/security/test_workflow_repair_isolation.py`.
- Modify: `corvus/workflow.py`, `corvus/verification.py`.
- First failing assertions: model-declared trivial commands cannot satisfy required checks; smoke checks execute; stale files cannot influence a later attempt; the packaged tree is the exact passing tree.

### Task 0.5 — Bundle integrity and atomic delivery
- Create tests: `tests/security/test_bundle_tampering.py`, `tests/security/test_delivery_atomicity.py`, and extend `tests/security/test_delivery_approval.py`.
- Modify: `corvus/delivery.py`; add a lock/approval repository port only where the test requires it.
- First failing assertions: altered staged files, replayed/expired/mismatched approval, concurrent apply, and injected failure after each filesystem step never produce an unjournaled or unauthorized delivery.

### Task 0.6 — Server-boundary hardening
- Create tests: `tests/security/test_structured_redaction.py`, `test_provider_url_policy.py`, `test_codex_environment.py`, `test_artifact_digest.py`, `tests/unit/test_config_narrowing.py`.
- Modify: `corvus/security.py`, `providers.py`, `codex_cli.py`, `store.py`, `config.py`.
- First failing assertions: nested secrets redact; internal/credential-bearing provider URLs are rejected for cloud profiles; child environment is allowlisted; invalid digests fail; optional token limits always narrow.

### Task 1.1 — Identity and scope contracts
- Create: `corvus/domain/__init__.py`, `identity.py`, `scope.py`, `access.py`, `audit.py`.
- Create tests: `tests/unit/domain/test_identity.py`, `test_scope.py`, `test_access_models.py`, `test_audit_models.py`.
- Add: `corvus/domain/runtime.py` and `tests/unit/domain/test_runtime_profile.py` for interaction/collaboration/hosting combinations and credential references.
- First failing assertions: invalid/missing workspace, cross-workspace nested scope, duplicate/empty capability, naive expiry, unstable canonical digest, plaintext credential values, and unsafe local-model/cloud combinations are rejected.

### Task 1.2 — Fail-closed access evaluation
- Create: `corvus/application/authorization.py`.
- Create test: `tests/unit/application/test_authorization.py`.
- Matrix: exact allow, no grant deny, explicit deny wins, wrong principal, wrong workspace, wrong project/channel/thread, expired/revoked bundle, constraint mismatch.

### Task 1.3 — Scoped audit persistence
- Create: `corvus/infrastructure/db.py`, `corvus/infrastructure/repositories/audit.py`.
- Create test: `tests/integration/test_scoped_audit_repository.py`.
- Persist access-bundle snapshot digest and immutable receipt chain by workspace.
- Verify tampering and cross-workspace reads fail.

### Task 1.4 — Authorization application service
- Create: `corvus/application/audit.py`.
- Create test: `tests/integration/test_authorize_and_record.py`.
- One call evaluates and persists allow or deny; repository failure causes the operation to fail closed.

### Task 1.5 — CLI V2 access/audit commands
- Create: `corvus/cli_v2.py` initially; register under existing Typer app.
- Create tests: `tests/cli/test_v2_access.py`, `tests/cli/test_v2_audit.py`.
- JSON output is stable and contains no policy secret fields.

### Task 1.6 — Quality gate
- `uv run pytest -q`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run bandit -r corvus -q`
- `uv run python -m compileall -q corvus`
- `uv run corvus --help`
- `uv run corvus doctor --json` with isolated `CORVUS_HOME`.
- `git diff --check`

## Worker Assignments
- Worker A — packaging/baseline tests only: `pyproject.toml`, lockfile, README, `tests/unit`, `tests/cli/test_cli_smoke.py`, baseline security tests. Must not edit team domain/application code.
- Worker B — domain/access/audit only: `corvus/domain`, `corvus/application/authorization.py`, domain/application tests. Must not edit packaging, CLI, or DB.
- Worker C — persistence/application integration: `corvus/infrastructure`, integration tests. Starts after Worker B contracts are fixed.
- Worker D — CLI V2 adapter: `corvus/cli_v2.py`, minimal `corvus/cli.py` registration, CLI V2 tests. Starts after Workers B/C.
- Reviewer — read-only diff, test, security, and acceptance review. Must not be the implementing worker.
- Limit concurrent local workers to two because RAM availability is constrained.

## Acceptance Criteria

### Plan-level
- The plan explicitly separates authoritative core from all clients.
- Every team feature maps to a typed model, application service, persistent record, and test strategy.
- Web and desktop reuse contracts and UI rather than duplicate the agent runtime.
- V1 compatibility and rollback points are identified.

### Immediate implementation slice
1. Repository installs reproducibly with `uv sync --locked` under Python 3.12.
2. Existing CLI help and doctor JSON pass from the installed project.
3. At least one regression test covers each retained security primitive: path, sandbox options, event chain, delivery approval.
4. Team request context cannot exist without runtime profile, workspace, requester, acting agent, access bundle, policy digest, correlation ID, and idempotency key.
5. Access evaluation is default deny; explicit deny overrides allow; scopes never broaden.
6. Cross-workspace and cross-project access fail in tests.
7. Allow and deny decisions both create immutable, verifiable, requester-attributed audit receipts.
8. Failure to persist the receipt prevents the protected action.
9. Existing V1 CLI commands remain available.
10. No live provider call, sandbox execution, external message, deployment, purchase, or credential change occurs.
11. Default build snapshots exclude secret/cache/dependency material, enforce size/count limits, and are cleaned up after success, failure, or cancellation.
12. Required verification is selected by Corvus/repository policy rather than trusted solely from generating-model commands; smoke checks execute and each repair uses a clean staging tree.
13. Delivery rejects any staged file whose current digest differs from the approved manifest and remains recoverable at every injected crash point.
14. Nested JSON/YAML-like secret values are redacted before persistence or model repair context.
15. Empty audit chains are invalid; artifact lookups accept only canonical SHA-256 digests.
16. Cloud/server profiles reject unsafe provider destinations and never inherit arbitrary host environment variables into model subprocesses.
17. V1 data migration fixtures and importers are idempotent before any existing table is changed.
18. Sandbox unavailability still produces no host-execution fallback.

### Later client milestones
- API endpoints authorize every resource and replay event.
- Web and desktop show persisted events only.
- Desktop capability configuration has no generic shell or unrestricted filesystem grant.
- A single fake-provider vertical slice works in CLI, web, and desktop against the same core and evidence.

## Verification Matrix

| Layer | Tests |
|---|---|
| Domain | Pydantic validation, canonical digest stability, scope containment, state transitions |
| Authorization | grant/deny matrix, expiry/revocation, constraints, principal/workspace/project isolation |
| Persistence | migrations, uniqueness, transactions, receipt/event hash chains, tamper detection, cross-tenant queries |
| Work queue | claim races, leases, heartbeats, stale recovery, dependency cycles, cancellation, idempotency |
| Sandbox | option contract unit tests; marked Docker/Podman integration tests only where available |
| Delivery | manifest binding, hash verification, conflict detection, backup/undo, malicious paths |
| CLI | Typer runner tests, stable JSON, V1 command presence, V2 authorization/audit commands |
| API | auth dependencies, 403/404 behavior, OpenAPI, SSE replay/reconnect/isolation |
| Web | Vitest components, API mocks only for unit tests, API-backed Playwright flow, axe/accessibility |
| Desktop | Tauri capability audit, Rust config/tests, same API-backed flow |
| Security | Ruff, Bandit under Python 3.12, dependency audit, secret scan, archive/path tests, tenant-isolation suite |

## Key Decisions and Tradeoffs
- **One Python core, thin clients:** avoids three diverging agent/security implementations.
- **Fix V1 trust boundaries before exposing V2:** authorization models do not make an unsafe snapshot/verification/delivery pipeline safe; critical build and delivery defects are gated ahead of web/team enablement.
- **One configurable product, not separate editions:** interaction surface, individual/team behavior, and local/cloud hosting are explicit runtime axes resolved to adapters; immutable safety stays common.
- **Bring-your-own models:** users supply local endpoints, API credentials, or provider OAuth. Corvus stores credential references and brokers access; it does not conflate a Corvus subscription with model entitlement.
- **Local model with cloud control plane requires a connector:** Corvus Cloud never assumes it can reach localhost and never asks users to expose an unauthenticated model port.
- **Vite React rather than Next.js for the workspace client:** the product is an authenticated application, not an SEO surface; static client assets are reusable by Tauri. FastAPI remains authoritative.
- **Tauri rather than Electron:** smaller native boundary and explicit capabilities, while still reusing React UI.
- **Incremental migration rather than wholesale directory move:** preserves V1 behavior and makes regressions attributable.
- **New scoped audit repository before rewriting legacy events:** provides a safe team boundary without an all-at-once event-store migration. Legacy events remain local-only until adapted.
- **Fake provider/sandbox for deterministic tests, no host fallback:** allows verification on this machine without pretending unsandboxed builds are secure.
- **OpenAPI-generated TS client:** prevents manual contract drift.
- **Server-side access bundle resolution:** transport tokens are references, not authority.
- **No OpenClaw shared gateway as tenant boundary:** borrow queue/session/capability patterns only; Corvus owns authorization or isolates gateways per tenant.
- **No Claude Tag embedding:** implement first-party `@Corvus`; Claude models may be providers through supported APIs.

## Risks and Mitigations
- **Unknown V1 production data:** add Alembic and migration tests before modifying existing tables; back up and verify databases before upgrade; build an idempotent V1 importer for YAML/keyring references, memories, skills, run events, bundles, and backups.
- **Plaintext snapshot and model-output exfiltration:** default-deny snapshot policy, structured redaction, output bounds, clean attempt trees, and cleanup are release blockers.
- **Model-selected verification:** repository/server-required checks and independent reviewer evidence must dominate model suggestions.
- **Bundle TOCTOU/crash windows:** rehash at apply, durable one-time approvals, locks, and crash-point testing are mandatory.
- **Large CLI/TUI modules:** keep adapter registration changes minimal; extract use cases before UI rewrites.
- **Hash-chain concurrency:** use transaction/locking plus unique workspace sequence; test concurrent appends.
- **SQLite concurrency limits:** SQLite is local-development mode. PostgreSQL is required before multi-worker production.
- **Scope-comparison bugs:** centralize containment logic and use exhaustive table/property tests.
- **Approval replay:** store nonce digest and single-use status in a transaction; bind to requester/reviewer/action/manifest/expiry.
- **Credential leakage:** credentials remain outside sandbox; add broker later with host/method/path allowlists and redacted audit.
- **SSE data leakage:** authorize connection and every replay query; never accept workspace/project solely from client token claims.
- **Desktop privilege creep:** Tauri capabilities are reviewed as code and tested against an allowlist.
- **Dependency supply chain:** lock Python/Node/Rust dependencies; add audit/SBOM gates before releases.
- **Resource pressure:** serialize Node/Rust builds and avoid local container builds while RAM is constrained.
- **Review-tool outage:** Claude returned HTTP 401, Gemini required Antigravity migration, and the approved read-only Codex fallback timed out without a verdict. Independent Hermes audits are the recorded review evidence; no external-model approval is claimed.

## Rollback and Checkpoints
1. `1410d7f` remains the immutable V1 baseline.
2. Commit reviewed planning artifacts separately before code.
3. One commit per TDD task or tightly coupled slice.
4. Never rewrite the V1 baseline after planning begins.
5. Before schema work, create and hash a V1 database fixture and test upgrade/downgrade.
6. CLI V2 commands are additive until their replacements pass compatibility tests.
7. API/web/desktop live on separate feature commits and can be reverted without changing core data.
8. No deployment or public release in this plan.

## First Implementation Slice to Build Immediately
Build Milestone 0, Milestone 0.5, and Milestone 1 only: reproducible packaging and golden tests; release-blocking snapshot/redaction/verification/delivery/provider/audit hardening; runtime-profile, credential-reference, identity/scope/access/audit contracts; fail-closed authorization; immutable scoped audit persistence; and additive CLI V2 access/audit inspection commands. Do not begin durable work, FastAPI, web, desktop, or channel-adapter code until this slice passes the complete quality gate and independent review.
