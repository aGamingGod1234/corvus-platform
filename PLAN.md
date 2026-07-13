# Plan: Corvus CLI V2 and Shared Web/Desktop Platform
_Maintained by Codex/Hermes and gated by recorded independent review._

## Goal
Evolve the supplied Corvus CLI V1 into one tested, installable, configuration-driven Corvus V2 platform with a single authoritative Python core. Users may interact through CLI, browser web, Tauri desktop, or approved third-party channels; run Corvus for an individual or a team; and place authorized work locally, through a secure connector, or on Corvus Cloud. The platform must add team-safe identity, scope, authorization, outcome contracts, durable workflow graphs, artifact lineage, governed memory and skills, context isolation, secret brokering, earned autonomy, shadow mode, budgets, kill switches, offline operation, and proof-carrying completion without weakening V1's sandbox, verification, delivery, or rollback guarantees.

Milestones 0 and the security-characterization portion of 0.5 have started. The next implementation work completes the release-blocking V1 trust fixes, then proves one vertical project create/read path through the corrected deployment/workspace/client/execution contracts, authorization, migration-backed persistence, and audit. CLI V2, FastAPI expansion, React UI, channels, and desktop remain later consumers of that boundary.

## Product Configuration Matrix

Corvus is one product with one authoritative core. Configuration is separated by owner, lifetime, and cardinality rather than collapsed into product editions or one overloaded runtime profile.

### Configuration ownership

| Contract | Owner/cardinality | Lifetime | Values/responsibility |
|---|---|---|---|
| `DeploymentProfile` | one per installed/server deployment | deploy/restart | authority mode, auth, network, storage, enabled adapters |
| `WorkspaceConfig` | one per workspace | mutable through authorized migration | `individual` or `team`, memberships, reviewer rules, shared scopes, budgets |
| `ClientContext` | one per request/session | request/session | `cli`, `desktop`, `web`, or `channel`; transport identity and origin only |
| `ExecutionPlacement` | one per task/run | task/run | `local_runner`, `cloud_worker`, or `connector`; sandbox and data locality |
| `ModelRouteSet` | principal/workspace scoped | independently mutable | local/API/OAuth routes, health, cost, capabilities, failover |
| `CredentialRef` | principal/workspace scoped | independently rotatable | OS keyring, cloud vault, provider OAuth, or connector reference |

Client surface never grants authority. Individual/team behavior belongs to the workspace. Different tasks may execute in different approved locations. Credentials rotate independently from deployment, workspace, client, and execution state.

### Behaviorally distinct combinations

| Deployment authority | Workspace mode | Clients | Execution | Status and controls |
|---|---|---|---|---|
| `embedded_local` | individual | CLI | local runner | Supported first; implicit private workspace, SQLite, OS keyring, fail-closed sandbox |
| `local_daemon` | individual | CLI/web/desktop | local runner | Supported after API slice; loopback auth, strict origins, visible lifecycle |
| `self_hosted` | individual/team | CLI/web/desktop/channel | server/local runners | Deferred; TLS, explicit auth, PostgreSQL for multi-worker operation |
| `vendor_cloud` | individual/team | CLI/web/desktop/channel | cloud workers | Deferred; tenant isolation, cloud vault, managed workers, signed audit checkpoints |
| `vendor_cloud` | individual/team | any | connector | Deferred; outbound-only mutually authenticated connector and explicit user consent |
| any | any | any | host process without sandbox | Invalid for build/apply work; fail closed |

One workspace has exactly one authoritative control plane represented by a persisted `WorkspaceAuthority` epoch and fencing token. Local and cloud copies are never implicit dual-primary replicas. Authority moves only through a signed, atomic export/import handoff that closes the old epoch before activating the next one. Connectors are execution placements and never acquire control-plane authority. A remote-authority client that is offline may only queue signed intents; reconnect performs fresh authentication, authorization, revocation, budget, and kill-switch checks before any intent becomes executable work.

### Effective capabilities

The authoritative backend resolves deployment, workspace, client, execution, model, credential, policy, budget, and kill-switch state into `EffectiveCapabilities`. Clients render returned capabilities and reason codes; feature flags may hide features but cannot create authority or disable authorization, audit, verification, evidence, limits, or rollback controls.

### Bring-your-own models and credentials

- Corvus does not silently bundle model entitlement. Users select local models, API providers, or provider-owned OAuth such as Codex/ChatGPT.
- `ProviderConnection` binds a route, credential reference, execution placement, ownership, and lifecycle without exposing the secret.
- Local credentials use the OS credential store or provider-owned local session. Cloud credentials use an encrypted workspace vault plus the scoped secret broker.
- Provider OAuth uses persisted authorization transactions with state/nonce, PKCE or device-flow binding, callback ownership, expiry, token-version references, refresh rotation, revocation, and recovery; OAuth tokens remain opaque to prompts, workers, traces, and clients.
- Codex CLI OAuth remains local unless the provider offers a supported server OAuth flow.
- Corvus Cloud cannot reach a laptop-only model without an explicit outbound connector. The connector uses short-lived mutual authentication, model-only RPC, consent, health registration, revocation, egress limits, and complete audit attribution.
- Offline execution is permitted only while the local deployment owns the current workspace authority epoch. Remote-authority offline clients can inspect an authorized cache and queue signed intents only; they cannot execute work, use stale grants, or cause external effects. Cloud-only actions remain unavailable with explicit reason codes.

## Context

### Source and baseline
- Repository: `C:/Users/lucas/Projects/corvus-platform`
- Imported V1 baseline commit: `1410d7f`
- Original source manifest: `V1_SOURCE_MANIFEST.json`
- Prior architecture memo: `C:/Users/lucas/AppData/Local/hermes/.ai/HERMES_HANDOFFS/2026-07-13-corvus-web-team-agent-integration.md`
- V1 contains 27 Python files and approximately 9,322 lines.
- V1 version is `0.1.0`; it has no package metadata, lockfile, tests, migrations, README, API, web client, or desktop client.

### Current implementation status
- Branch: `feat/corvus-v2-foundation`.
- Corvus V2 package baseline is `0.2.0a1` with `pyproject.toml`, `uv.lock`, README, Python 3.12 selection, and retained CLI behavior.
- Security characterization and the empty-trace verification fix are committed.
- Latest full gate: 14 tests passed; one Windows symlink test skipped because this host cannot create symlinks; Ruff lint/format and Git diff validation passed.
- No Task 1.1 schema/domain, FastAPI, React, channel, connector, or desktop code exists yet.

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
3. Every command/run carries an immutable request context: deployment, workspace authority epoch, discriminated scope, immutable audience-policy snapshot, requester, client/transport identity, acting agent and agent grant, requester access bundle, execution placement when applicable, policy digest, correlation ID, and idempotency key.
4. Missing or mismatched identity/scope/capability information fails closed.
5. Cross-scope memory reads and promotions require explicit policy and provenance; private memory never silently becomes team memory.
6. Workers acquire monotonically fenced durable leases with expiry and heartbeat. All external effects flow through one effect gateway backed by semantic idempotency keys and a transactional outbox, so stale workers cannot duplicate effects after recovery.
7. Implementers cannot approve their own unsupported completion claims.
8. Automated routines use the same authorization, budget, sandbox, verification, and audit path as interactive runs.
9. Progress comes only from persisted backend events; clients never synthesize progress timers.
10. Sandboxes receive approved snapshots and scoped broker responses only; they never receive host credentials or direct host filesystem access.
11. Web previews use a distinct hostile-content origin and never receive Corvus auth tokens.
12. Completion is proof-carrying: every required acceptance criterion must pass or the run uses an honest partial/failed/blocked status.
13. Corvus earns autonomy through verified performance and provides proof for every completed action.

### Locked capability brief

| Capability | Authoritative owner | Required proof before enforcement/promotion |
|---|---|---|
| Outcome contracts | domain + verification service | acceptance criteria, evidence schema, permissions, budget and runtime-limit tests |
| Versioned skills | workspace skill registry | evaluation suite, independent approval, canary metrics, regression detection and rollback |
| Context firewall | ingestion/context service | untrusted-source labels, instruction/data separation, provenance and prompt-injection fixtures |
| Secret broker | credential service | short-lived scoped grant, host/method/path limits, revocation and zero-secret trace tests |
| Autonomy levels | workspace policy | `advise`, `observe`, `sandbox`, `propose`, `apply`, `bounded_delegation` transition tests |
| Shadow mode | evaluation service | proposed-versus-approved comparison, reliability threshold, holdout canaries and rollback |
| Durable workflow graphs | work service | dependencies, specialists, checkpoints, stuck detection and retry -> replan -> decompose recovery |
| Artifact lineage | artifact/audit service | request, source, model, tool, test, approval and receipt linkage with digest verification |
| Memory governance | memory service | scope, source, confidence, expiry, encryption, export, deletion and promotion authorization |
| Kill switches and limits | policy/budget service | atomic workspace/agent/workflow/run stop plus cost/runtime reservation tests |
| Offline mode | deployment + execution services | local model/cache/memory/queue behavior with explicit unavailable cloud capability reasons |

Autonomy starts in shadow/proposal mode. Promotion to a more powerful level requires versioned evaluation evidence, independent approval where risk requires it, canary operation, reliability thresholds, and reversible rollback. A client or feature flag cannot self-promote an agent, skill, workflow, or credential grant.

### Capability implementation ledger

Migration identifiers are plan-stable labels; implementation may map them to Alembic revision IDs while preserving this ownership and order.

| Capability | Milestone | Persistent records / migration | Legacy cutover or import | Downgrade / rollback boundary | Executable acceptance test |
|---|---:|---|---|---|---|
| Outcome contracts | 2 | `OutcomeContractVersion`, workflow pins / `M2-001` | V1 acceptance/budget fields imported after destination schema exists | retain prior immutable version; workflows never repoint silently | `test_outcome_contract_version_pin.py` |
| Versioned skills | 7 | `Skill`, `SkillVersion`, evaluations/promotions/regressions / `M7-002` | V1 skills imported idempotently from quarantine after `M7-002` | restore prior active version plus rollback receipt | `test_skill_canary_rollback.py` |
| Context firewall | 0.5, extended 7 | `ExternalContent`, `ContextEnvelope` / `M005-001` | legacy external/model content remains untrusted; no trust elevation on import | disable new ingestion while retaining provenance/readability | `test_context_firewall.py` |
| Secret broker | 6 | provider/OAuth/credential references and grants / `M6-001` | import references only; never import plaintext; reauthorize unsupported OAuth | revoke grants and return to direct local reference where supported | `test_secret_broker_lifecycle.py` |
| Autonomy levels | 6 | `AutonomyPolicy`, action/effect matrix / `M6-002` | V1 policy/autonomy YAML imported after schema and capped at `propose` until reviewed | lower ceiling immediately; no grandfathered authority | `test_autonomy_effect_matrix.py` |
| Shadow mode | 6 | `ShadowEvaluation`, canary policy / `M6-003` | no legacy promotion evidence is assumed | return subject to shadow and revoke canary grants | `test_shadow_no_real_effects.py` |
| Durable workflow graphs | 2 | graph/work/dependency/lease/attempt/recovery / `M2-002` | V1 runs imported as immutable history; only new work becomes schedulable | pause new claims; preserve graph/event readability | `test_workflow_recovery_fencing.py` |
| Artifact lineage | 2 | typed immutable lineage edges and effect receipts / `M2-003` | V1 artifacts receive imported-source digest edges, never fabricated evidence | reject completion if closure cannot verify | `test_lineage_digest_closure.py` |
| Memory governance | 7 | scoped memory/promotion/export/deletion / `M7-001` | V1 memories imported after schema into explicit owner/workspace scopes | stop writes; retain encrypted export and deletion receipts | `test_memory_scope_lifecycle.py` |
| Kill switches and limits | 2 | kill switches, budget reservations, effect intents / `M2-004` | V1 budgets imported as conservative ceilings after schema | fail closed and preserve stop/usage receipts | `test_effect_gateway_atomic_limits.py` |
| Offline mode | 1 authority, 8 queue/cache | authority/handoff plus offline intent/cache metadata / `M1-001`, `M8-001` | no legacy copy gains authority; cache import is non-authoritative | discard/requeue unaccepted intents; restore from last signed authority handoff | `test_offline_authority_reconciliation.py` |

### V2 client contract
- Define transport-neutral command/query/event ports, one application composition root, and matching in-process and HTTP Python clients before any UI expansion.
- CLI V2 uses the in-process client for `embedded_local` or the HTTP client for daemon/self-hosted/cloud deployments; both call the same application services.
- Web uses authenticated FastAPI endpoints plus replayable SSE with opaque workspace-scoped cursors; the same build targets Corvus Cloud or a self-hosted endpoint.
- Desktop uses Tauri and the same React client package only after CLI/web team and provider flows stabilize. It may connect to cloud or supervise a least-privilege loopback service; it never gains authority because it is native.
- Third-party channels authenticate as channel/service principals and preserve the human requester, immutable scope/audience, workspace, project, guild/channel/thread, acting agent grant, and access-bundle attribution.
- Shared OpenAPI-generated TypeScript contracts and transport-parity tests prevent client-defined authority or duplicated state machines.

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

## Locked implementation discipline
1. Inspect repository, architecture, tests, and live build status before each milestone; current evidence is recorded above.
2. Reuse the V1 map below and avoid parallel implementations of policy, sandbox, delivery, provider, memory, or runtime behavior.
3. Preserve backward compatibility where practical; expose V2 paths additively until compatibility tests pass.
4. Build the smallest secure vertical slice per capability, with TDD red -> green -> refactor and one reviewable commit per task.
5. Add explicit schema migrations, authorization checks, negative isolation tests, and rollback fixtures before changing durable state.
6. Never expose secrets in prompts, context, events, traces, snapshots, artifacts, errors, exports, or test fixtures.
7. Do not claim completion until the outcome contract's required tests and evidence pass; document partial, blocked, skipped, and unsupported states honestly.
8. Prioritize the remaining security fixes and project create/read authority path before CLI V2, FastAPI expansion, React, channels, connector, or desktop work.

## Recommended Repository Layout

```text
corvus-platform/
  corvus/                     # Authoritative Python core and local CLI adapter
    application/              # Use cases; no Typer/FastAPI/Textual imports
      ports.py
      authorization.py
      audit.py
      projects.py
      outcomes.py
      work_items.py
      context_firewall.py
      credentials.py
      memory.py
      skills.py
    domain/                   # Pure typed contracts and invariants
      deployment.py
      workspace.py
      client.py
      execution.py
      identity.py
      scope.py
      access.py
      outcomes.py
      work.py
      events.py
      memory.py
      skills.py
      providers.py
    infrastructure/
      db.py
      repositories/
      secret_broker/
      connector/
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
| `corvus/security.py` | Reuse and harden | Retain path/link protections, atomic writes, hashing, and redaction; add structured zero-secret redaction plus context-firewall provenance/instruction separation. |
| `corvus/store.py` | Refactor | Keep event hashing and artifact addressing; split DB bootstrap/repositories; add migrations and mandatory scoped audit records. |
| `corvus/conversations.py` | Replace runtime state, reuse bounds | Preserve limit/delegation semantics, but back chats/messages/queues/events with durable work and event repositories. |
| `corvus/policy.py` | Extend | Keep path/domain/autonomy checks; add resource/action/scope access evaluation and deny precedence. |
| `corvus/sandbox.py` | Reuse behind protocol | Keep fail-closed Docker/Podman implementations; test options and lifecycle through fakes. No host-process fallback for builds. |
| `corvus/workflow.py` | Refactor into use case | Preserve snapshot/generate/verify/package loop; require context firewall, outcome contract, authenticated authority, workflow graph, independent evidence, lineage, limits, and receipts. |
| `corvus/delivery.py` | Reuse and harden | Keep manifest binding/conflict detection/rollback. Add scanner inputs, replay-resistant approvals, archive export, and ownership checks later. |
| `corvus/verification.py` | Extend | Generalize sandbox protocol, persist evidence metadata, and enforce required/optional criteria honestly. |
| `corvus/memory.py` | Replace schema/API | Add encrypted scoped records, source/confidence/expiry, promotion review, authorization, export, deletion, retention, and receipts. |
| `corvus/skills.py` | Extend | Bind versions to workspace/capabilities and add evaluation suites, shadow/canary promotion, independent approval, regression detection, and rollback. |
| `corvus/providers.py`, `provider_control.py`, `model_catalog.py`, `codex_cli.py` | Reuse behind routing/broker ports | Preserve transports; add provider connection/credential grant ownership, placement, health, rotation/revocation, budgets, failover, and zero-secret receipts. |
| `corvus/cli.py` | Decompose | Keep command compatibility; introduce `v2` project/access/work/run commands backed by application services. |
| `corvus/tui.py` | Retain as CLI client | Stop it constructing authority directly; make it consume application services/events. |
| `corvus/onboarding*.py` | Retain, adapt later | Add local/remote mode and workspace selection after application boundary exists. |

## Core Data Model

All identifiers are opaque UUIDs. Every persistent row includes `created_at`, and mutable rows include `updated_at` plus optimistic `version`.

### Configuration and provider lifecycle
- `DeploymentProfile(id, authority_mode[embedded_local|local_daemon|self_hosted|vendor_cloud], auth_profile, network_profile, storage_profile, enabled_adapters, protocol_version, version)`
- `WorkspaceConfig(workspace_id, collaboration_mode[individual|team], autonomy_ceiling, shadow_policy_id, budget_policy_id, memory_policy_id, kill_switch_state, version)`
- `WorkspaceAuthority(workspace_id, deployment_profile_id, epoch, fencing_token_digest, state[active|handoff_pending|closed], previous_epoch_digest?, activated_at, closed_at?, version)`; `(workspace_id, epoch)` is unique and epochs increase monotonically.
- `AuthorityHandoff(id, workspace_id, from_deployment_id, to_deployment_id, from_epoch, to_epoch, export_artifact_digest, source_checkpoint_digest, signer_set, threshold_signatures, state[prepared|source_closed|target_active|aborted], prepared_at, completed_at?)`; target activation and source closure follow a recoverable atomic protocol that never leaves two active epochs.
- `OfflineIntent(id, workspace_id, observed_authority_epoch, client_context_id, requester_id, agent_id, command_digest, encrypted_payload_ref, intent_signature, queued_at, expires_at, status[queued|accepted|rejected|expired], accepted_request_context_id?, rejection_reason_code?)`; it conveys no authority and is executable only after reconnect creates a freshly authenticated/authorized request under the current epoch.
- `ClientContext(id, surface[cli|desktop|web|channel], transport_principal_id?, session_id, origin, issued_at, expires_at?)`
- `ExecutionPlacement(id, kind[local_runner|cloud_worker|connector], runner_id?, connector_id?, sandbox_profile, data_policy_digest, status)`
- `ModelRouteSet(id, workspace_id, owner_principal_id?, routes, budget_policy_id, failover_policy, version)`
- `ProviderConnection(id, workspace_id, owner_principal_id?, provider, route_id, credential_ref_id, allowed_placement_ids, status, last_health_at?, version)`
- `CredentialRef(id, workspace_id, owner_principal_id?, provider_connection_id, kind[os_keyring|cloud_vault|provider_oauth|local_connector], opaque_locator, scopes, status, expires_at?, version)`
- `CredentialVersion(id, credential_ref_id, workspace_id, version_number, opaque_version_locator, status[active|rotating|revoked|expired], valid_from, valid_until?, rotated_from_id?, revoked_at?)`
- `ProviderOAuthTransaction(id, workspace_id, provider_connection_id, requester_id, flow[authorization_code_pkce|device_code], state_digest, nonce_digest, pkce_verifier_ref?, device_code_ref?, callback_owner_principal_id, redirect_uri_digest?, expires_at, consumed_at?, status)`
- `ProviderOAuthGrant(id, workspace_id, provider_connection_id, credential_version_id, provider_subject_digest, granted_scopes, refresh_family_id?, status, issued_at, refreshed_at?, revoked_at?)`
- `CredentialGrant(id, workspace_id, provider_connection_id, credential_version_id, request_context_id, agent_grant_id, execution_placement_id, purpose, operations, host_method_path_constraints, use_limit, use_count, issued_at, expires_at, rotation_epoch, revoked_at?, nonce_digest)`
- `EffectiveCapabilities(request_context_id, workspace_authority_epoch, actions, unavailable_reason_codes, policy_digest, budget_snapshot_digest, kill_switch_snapshot_digest)`
- Configuration cannot contain plaintext credentials or disable immutable safety, authorization, audit, verification, evidence, limits, or rollback.

### Tenancy and identity
- `Workspace(id, name, status)`
- `WorkspaceMembership(workspace_id, principal_id, role, status)`
- `Project(id, workspace_id, name, root_locator, privacy, status)`
- `Principal(id, kind[user|service|channel], external_provider, external_subject, display_name)`
- `AgentIdentity(id, workspace_id, name, role, model_route, skill_set_digest, status)`
- Scope is a discriminated union with valid parentage encoded by type rather than nullable identifiers:
  - `WorkspaceScope(workspace_id)`
  - `ProjectScope(workspace_id, project_id)`
  - `ChannelScope(workspace_id, channel_id, project_id?)`
  - `ThreadScope(workspace_id, channel_id, thread_id, project_id?)`
  - `ConversationScope(workspace_id, conversation_id, parent_scope_kind, parent_scope_id)` where the parent is a valid project, channel, or thread scope in the same workspace.
- `AudiencePolicySnapshot(id, workspace_id, visibility[personal|explicit_principals|role|project|channel|thread|workspace], owner_principal_id?, principal_ids, role_ids, scope_digest, policy_version, policy_digest, created_by, created_at)` is immutable; personal visibility requires the owner and every referenced principal/role/scope belongs to the workspace.

### Access and acting-agent authority
- `AccessBundle(id, workspace_id, principal_id, scope_kind, scope_id, issued_by, policy_digest, expires_at, revoked_at?)`
- `CapabilityGrant(bundle_id, workspace_id, resource_kind, resource_id, action, effect[allow|deny], constraints_json)`
- `AgentGrant(id, workspace_id, agent_id, capability_bundle_id, autonomy_level, issued_by, expires_at?, revoked_at?)`
- `DelegationGrant(id, parent_agent_grant_id, child_agent_id, capabilities, budget_json, depth_limit, issued_at, expires_at, revoked_at?)`
- Deny wins. No grant means deny. Scope matching must never broaden a grant.
- Effective authority is the minimum intersection of current workspace authority epoch, discriminated scope/audience, requester, acting-agent/delegation, channel/routine, workspace policy, budget, autonomy ceiling, execution placement, credential grant, and kill-switch state at claim, model/tool call, approval, and external effect time.
- Short-lived signed transport tokens may reference an access bundle but cannot replace server-side bundle/revocation checks.

### Requests, audit, and approvals
- `RequestContext(id, deployment_profile_id, workspace_id, workspace_authority_epoch, scope_kind, scope_id, audience_policy_snapshot_id, audience_policy_digest, requester_id, client_context_id, transport_principal_id?, agent_id, agent_grant_id, access_bundle_id, execution_placement_id?, policy_digest, idempotency_key, correlation_id)`
- `IdempotencyEnvelope(id, workspace_id, requester_id, transport_principal_id, agent_id, agent_grant_id, operation, idempotency_key, request_context_digest, payload_digest, status[in_progress|succeeded|failed], result_digest?, result_ref?, created_at, completed_at?)`; the composite identity is unique, creation/result commit is atomic with the command, payload mismatch fails, and cached results are returned only after current read authorization.
- `AuditReceipt(id, workspace_id, workspace_sequence, schema_version, authority_epoch, request_context_id, action, resource, decision, reason_code, policy_digest, sanitized_input_digest, output_digest?, effect_attempt_ids, cost_json, evidence_ids, signer_key_id, key_epoch, previous_hash, receipt_hash)`; `(workspace_id, workspace_sequence)` is unique and monotonic.
- `AuditCheckpoint(id, workspace_id, authority_epoch, through_sequence, receipt_hash, schema_version, signer_key_id, key_epoch, signature, previous_checkpoint_digest?, anchored_at)`; receipt append, sequence allocation, and chain-head update are one transaction, while signing keys live in OS keyring/cloud KMS and support rotation/revocation metadata.
- `ApprovalRequest(id, request_context_id, action, manifest_digest, required_reviewer_role, status, expires_at, nonce_digest)`
- `ApprovalDecision(id, approval_request_id, reviewer_id, decision, rationale, decided_at)`
- Implementer/reviewer separation is validated server-side.

### Outcomes, durable workflow graphs, limits, and lineage
- `OutcomeContract(id, workspace_id, name, status, latest_version_number)`
- `OutcomeContractVersion(id, outcome_contract_id, workspace_id, version_number, canonical_digest, acceptance_criteria, evidence_schema, required_permissions, budget_json, runtime_limits_json, verifier_policy_digest, created_by, created_at)` is immutable.
- `WorkflowGraph(id, workspace_id, project_id?, outcome_contract_version_id, outcome_contract_digest, authority_epoch, state, recovery_policy, budget_json, version)`
- `WorkItem(id, workflow_graph_id, workspace_id, project_id?, parent_id?, kind, state, priority, payload_json, required_capabilities, budget_json, runtime_limit_json, max_attempts, attempt_count, available_at, version)`
- `WorkDependency(work_item_id, dependency_id, condition)`
- `WorkLease(work_item_id, worker_id, authority_epoch, lease_fence, lease_token_digest, acquired_at, heartbeat_at, expires_at)`; the fence increases on every acquisition and must accompany every state mutation/effect request.
- `WorkAttempt(id, work_item_id, agent_id, started_at, finished_at?, outcome?, error_code?, cost_json, evidence_ids)`
- `WorkflowCheckpoint(id, workflow_graph_id, work_item_id?, state_digest, artifact_ids, created_by, created_at)`
- `RecoveryDecision(id, work_item_id, trigger[retry_exhausted|stuck|verification_failed|dependency_failed], action[retry|replan|decompose|pause|fail], rationale, approved_by?, created_at)`
- `ExternalEffectIntent(id, workspace_id, workflow_graph_id, work_item_id, work_attempt_id, authority_epoch, lease_fence, semantic_idempotency_key, effect_kind, target_digest, sanitized_payload_digest, required_capabilities_digest, budget_reservation_id, kill_switch_snapshot_digest, state[pending|dispatching|succeeded|failed|cancelled|compensating|compensated], created_at)` with a unique semantic key per workspace/effect.
- `EffectPermit(id, effect_intent_id, workspace_id, authority_epoch, lease_fence, budget_reservation_version, kill_switch_version, state[available|claimed|cancelled|consumed], claimed_by?, claimed_at?, consumed_at?)`; permit claim serializes under the affected budget/kill-switch scopes.
- `ExternalEffectAttempt(id, effect_intent_id, attempt_number, gateway_id, authority_epoch, lease_fence, authorization_receipt_id, provider_idempotency_key?, started_at, finished_at?, result_digest?, error_code?, compensation_attempt_id?)`
- `EffectOutbox(id, effect_intent_id, dispatch_after, state[pending|claimed|delivered|cancelled], fence, claimed_by?, delivered_at?)`; effect-intent creation, current budget/kill-switch reservation, authorization receipt, and outbox append are one transaction.
- `LineageNode(id, workspace_id, kind[source|model_call|tool_call|test_evidence|approval|audit_receipt|artifact], immutable_record_id, canonical_digest)`
- `ArtifactLineageEdge(id, workspace_id, artifact_id, from_node_id, to_node_id, relation, edge_digest)`; completion verifies a referentially constrained digest closure over immutable nodes and parent artifacts.
- `KillSwitch(id, scope_kind[workspace|agent|workflow|run], scope_id, state[armed|stopping|stopped], reason, activated_by, activated_at, cleared_by?, cleared_at?)`
- State machine: `queued -> leased -> running -> waiting_approval|waiting_dependency|paused -> verifying -> packaging -> completed|failed|cancelled|expired`.
- Compare-and-swap version and lease fence prevent stale state mutation. Heartbeats and persisted progress trigger stuck detection. Recovery is bounded `retry -> replan -> decompose`; exhaustion pauses or fails honestly.
- Only the centralized effect gateway may dispatch external effects. It revalidates the current authority epoch, fenced lease, requester/agent grants, budget reservation, kill switches, and semantic idempotency, then atomically claims an `EffectPermit` under the affected scope locks immediately before dispatch. Kill-switch activation atomically prevents new permit claims, cancels available permits, and marks already-claimed attempts for provider cancellation or compensation; no design claims that a remote provider can undo an effect it already accepted. Provider idempotency is used when available; otherwise only effects with defined cancellation/compensation semantics are eligible for retry.
- Outcome completion requires the pinned contract version's evidence, permissions, budget, and runtime limits plus a verified immutable lineage closure. Kill switches and budget state are enforced transactionally at effect-intent creation and rechecked at dispatch, approval, and completion.

### Routines and triggers
- `Routine(id, workspace_id, project_id?, name, trigger_type, trigger_config, command_template, access_bundle_id, budget_json, enabled)`
- `TriggerReceipt(id, routine_id, external_event_id, payload_digest, received_at)` with unique dedupe key.
- Every trigger creates a normal `RequestContext` and `WorkItem`.

### Context firewall and memory governance
- `ExternalContent(id, workspace_id, source_kind, source_locator_digest, content_digest, trust_class[untrusted|reviewed|trusted], provenance_json, sanitized_at?, expires_at?)`
- `ContextEnvelope(id, workspace_id, owner_kind[request_context|legacy_run], owner_id, system_instruction_digest, trusted_context_ids, untrusted_content_ids, firewall_policy_digest, output_digest?)`; a request-owned envelope must reference a same-workspace `RequestContext`, while legacy ownership is read-only migration provenance.
- External content is data, never instruction. The firewall preserves provenance, separates instruction/context channels, labels untrusted spans, bounds content, and prevents retrieved content from granting tools, secrets, permissions, or autonomy.
- Memory scope is a workspace-bound discriminated union: `PersonalMemoryScope(workspace_id, owner_principal_id)`, `ThreadMemoryScope(workspace_id, channel_id, thread_id)`, `ProjectMemoryScope(workspace_id, project_id)`, `ChannelMemoryScope(workspace_id, channel_id)`, or `WorkspaceMemoryScope(workspace_id)`.
- `MemoryRecord(id, workspace_id, memory_scope_kind, memory_scope_id, owner_principal_id?, visibility[owner_only|explicit_principals|role|scope_members], audience_policy_snapshot_id, kind, encrypted_content_ref, encryption_key_version, content_digest, source_record_id?, source_digest, provenance_json, confidence, status, expires_at?, deleted_at?)`; personal memory requires the same-workspace owner.
- `MemoryPromotion(id, workspace_id, source_memory_id, source_digest, target_workspace_id, target_scope_kind, target_scope_id, target_audience_policy_snapshot_id, requested_by, reviewed_by?, status, rationale)`
- `MemoryExport(id, workspace_id, requested_by, scope_filter, format, artifact_id, completed_at?)`
- `MemoryDeletion(id, workspace_id, requested_by, scope_filter, reason, encryption_key_version, primary_delete_receipt_id, index_cache_receipt_ids, retention_exception_receipt_ids, completed_at?)`
- Reads require scope membership and explicit capability. Promotion preserves source and review. Export/deletion are authorized, auditable, and tested across active stores, indexes, caches, and backups according to retention policy.

### Versioned skills, autonomy, and shadow promotion
- `Skill(id, workspace_id, name)`
- `SkillVersion(id, skill_id, version, content_digest, source, permissions, capability_manifest_id, status[draft|shadow|canary|active|rolled_back|failed], created_by, reviewed_by?)`
- `SkillEvaluation(id, skill_version_id, suite_version, fixture_digest, hidden_holdout_digest?, results_json, evaluator_id, evaluated_at)`
- `SkillPromotion(id, skill_version_id, from_stage, to_stage, evidence_ids, requested_by, approved_by?, canary_policy, rollback_version_id, status)`
- `SkillRegression(id, skill_version_id, baseline_version_id, metric, threshold, observed, detected_at, rollback_receipt_id?)`
- `AutonomyPolicy(id, workspace_id, level[advise|observe|sandbox|propose|apply|bounded_delegation], allowed_actions, evidence_thresholds, reliability_thresholds, budget_limits, runtime_limits, version)`
- `ShadowEvaluation(id, subject_kind[agent|skill|workflow], subject_id, proposal_digest, approved_action_digest?, outcome, metric_json, evaluated_at)`
- `CapabilityManifest(id, provider, name, version, operations, risk_class, input_schema_digest, network_constraints, secret_requirements)`
- Normative default-deny action/effect matrix:

  | Level | Observe/read | Simulated or sandbox effects | Production effects | Delegation |
  |---|---|---|---|---|
  | `advise` | approved context only | none; return advice | forbidden | forbidden |
  | `observe` | approved read-only tools | recorded read-only calls only | forbidden | forbidden |
  | `sandbox` | approved reads | isolated fake/sandbox effects | forbidden | forbidden |
  | `propose` | approved reads | may construct plans/diffs/effect intents without dispatch | forbidden | forbidden |
  | `apply` | approved reads | allowed | only explicitly granted effects through the gateway | forbidden |
  | `bounded_delegation` | approved reads | allowed | only explicitly granted effects through the gateway | child grants are a strict capability/budget/depth subset |

- Shadow runs never receive production credential grants and use recorded/fake/read-only effects. Only separately identified, explicitly budgeted canaries may perform narrowly scoped reversible production effects through the effect gateway with independent approval and compensation. Promotion requires versioned evaluation, independent review for privileged capability, canary limits, regression monitoring, and automatic/manual rollback.

### Budgets
- Budget layers: workspace -> project -> routine/channel -> run -> agent/subagent.
- Effective budget is the minimum remaining allowance at every layer.
- Reservations and actual usage are persisted; cancellation releases only unused reservations.

## Authoritative Events and State Machine

### Event envelope V2
Every durable event includes:
- `schema_version`
- `event_id`
- workspace-global monotonic `sequence`
- `workspace_id`
- `workspace_authority_epoch`
- immutable discriminated `scope_kind` and `scope_id`
- immutable `audience_policy_snapshot_id`, `audience_policy_digest`, and visibility level
- `run_id`/`workflow_graph_id` when applicable
- `work_item_id` when applicable
- `request_context_id`
- `requester_id`
- `agent_id` and acting `agent_grant_id`
- `event_type`
- `phase/state`
- timestamp
- redaction status
- structured payload
- previous hash
- event hash

### Rules
1. Event append and state transition occur in one database transaction.
2. Invalid state transitions are rejected before event creation.
3. Every live and replayed event is authorized against its persisted immutable scope and resolvable `AudiencePolicySnapshot`; workspace membership alone cannot reveal private personal/thread/conversation events.
4. Redaction and context-firewall labeling happen before hashing/persistence.
5. Clients derive display state from snapshots plus events but never write state directly.
6. `run.completed` can only follow passed required criteria, valid lineage, and a valid package/evidence record.
7. SSE uses an opaque workspace-scoped cursor and `Last-Event-ID`; the protocol defines snapshot-plus-replay, retention-gap reset, heartbeats, backpressure/slow-client limits, terminal disconnect behavior, and version compatibility.
8. Cross-thread, cross-conversation, cross-project, cross-workspace, cursor-tampering, gap, duplicate, and reconnect tests are mandatory.

## API and Client Architecture

### Authority and placement resolution
- Startup validates one `DeploymentProfile` and opens only its approved adapters. A deployment may serve several client surfaces simultaneously.
- Every request resolves the active `WorkspaceAuthority` epoch, `WorkspaceConfig`, discriminated scope, audience snapshot, `ClientContext`, requester/access bundle, acting-agent/delegation grant, policy, budget, kill switches, model route, credential grant, and requested `ExecutionPlacement` into `EffectiveCapabilities`.
- Workspace collaboration mode changes only through an authorized migration; it does not redefine deployment identity.
- Concurrent tasks may select different permitted execution placements without changing client authority.
- `embedded_local` may bootstrap one private individual workspace with SQLite and OS keyring while still using authorization and audit.
- Self-hosted/team/cloud operation requires explicit authentication, TLS when network-exposed, PostgreSQL before multi-worker operation, and the same isolation tests.
- One composition root provides transport-neutral command/query/event ports plus in-process and HTTP Python clients; import-boundary tests prevent CLI/TUI/API/UI adapters from owning policy or persistence.

### FastAPI
- Cloud uses OIDC Authorization Code + PKCE, secure rotating session cookies, CSRF protection, and revocable API/service tokens. Self-hosting defines first-admin bootstrap, trusted OIDC configuration, recovery, TLS trust, rotation, and revocation before network exposure.
- Authentication maps each session/token/channel/connector to a `Principal`; workspace creation is authorized explicitly rather than inferred from login.
- Authorization resolves the exact `RequestContext`, `AccessBundle`, `AgentGrant`, and `EffectiveCapabilities` server-side.
- Mutating commands require a persisted `IdempotencyEnvelope` keyed by requester, transport principal, acting agent/grant, workspace, operation, and idempotency key. The request-context and payload digests, status, and result reference commit atomically with the command; payload-digest mismatches fail and concurrent duplicates commit once. A retry never receives a cached result until current authorization confirms that requester, transport principal, agent grant, scope, audience, and access bundle may still read it.
- Initial endpoints:
  - `GET /api/v2/meta`
  - `POST /api/v2/projects`
  - `GET /api/v2/projects/{id}`
  - `POST /api/v2/work-items`
  - `GET /api/v2/work-items/{id}`
  - `GET /api/v2/events?cursor=<opaque>` (SSE)
  - `POST /api/v2/access/explain` (safe decision explanation, no secret policy dump)
- OpenAPI is the source for TypeScript contracts; Python in-process/HTTP parity tests use the same command fixtures.

### Web
- Vite + React + TypeScript, TanStack Router and Query.
- `packages/client-ui` owns accessible layout/components and consumes generated contracts.
- The first web slice authenticates, lists/creates a project, submits a work item, reconnects to SSE, and renders only persisted events.

### Desktop
- Tauri wraps the stabilized React client/UI package only after CLI/web team collaboration and provider-connection contracts pass.
- Desktop connects to one explicit authoritative workspace endpoint; switching endpoints does not synchronize or create a second authority.
- Session material stays in the OS credential store. Native commands are allowlisted; there is no generic shell/filesystem bridge.
- Local mode may supervise a signed loopback sidecar with an ephemeral token, strict origins, bounded lifecycle, visible status, protocol compatibility checks, and rollback-capable updates.

### Third-party channels
- Channel adapters are thin authenticated ingress/egress clients added after team/provider contracts stabilize.
- Signed ingress/webhook verification, durable provider-event deduplication, rate limits, bounded egress, reply correlation, and explicit human identity mapping are mandatory.
- A channel binding maps provider/guild/channel/thread to immutable Corvus scope, workspace/project, allowed agent grant, budget, and access bundle.
- Messages never carry reusable model credentials and cannot broaden scope, autonomy, credential, or access grants.
- High-risk approvals require browser/desktop step-up authentication by default; channel reactions/messages alone do not authorize apply or privileged external effects.

## Implementation Approach and Checkpoints

### Milestone 0 — Reproducible V1 baseline
1. Add `pyproject.toml` with Python `>=3.12,<3.14`, runtime dependencies inferred from imports, CLI entry point, Ruff/Pytest configuration, and dev dependencies.
2. Generate and commit `uv.lock`.
3. Add `README.md` with isolated Windows invocation and fail-closed sandbox statement.
4. Add golden smoke/JSON-schema tests for every public V1 command, plus focused event-chain, path-traversal, sandbox-option, and delivery-approval regression tests.
5. Define V2 identifier rules, command envelope, event envelope, error schema, protocol version, and database migration version before client work.
6. Freeze immutable hashed V1 exports and database fixtures for config/onboarding, provider metadata and keyring references, user/project policy and autonomy YAML, memories, skills, conversations/run events, bundles, artifacts, backups, and every public command/JSON shape. Never rewrite the source fixture.
7. Replace runtime `create_all()` with one version-aware bootstrap that detects new, unstamped, current, partially created, and incompatible databases; require backup, explicit stamp/upgrade, quarantine, restore, and failure behavior.
8. Add a sealed staging/quarantine capture importer that records canonical source records and hashes without converting them to not-yet-defined V2 domains. Run it twice to prove dedupe and source readability. Each domain-specific importer is added only after that destination migration exists.
9. Add CI commands as local scripts/config only; do not publish.

Checkpoint: existing CLI help and doctor behavior pass from `uv run corvus`; all public V1 golden fixtures are hashed; version-aware bootstrap rejects unsafe partial state; sealed quarantine capture runs twice without duplication and leaves the source fixture readable.

### Milestone 0.5 — Release-blocking V1 safety hardening
1. Enforce a snapshot/export policy before any model call: default secret/cache/dependency exclusions, approved include overrides, file/count/byte limits, link/reparse rejection, and guaranteed cleanup.
2. Add the context firewall for all external/snapshot/model-returned content: immutable provenance, untrusted labels, instruction/data separation, content bounds, and denial of content-created tools, secrets, permissions, or autonomy.
3. Redact structured mappings/lists recursively before serialization; register brokered secrets with the redactor; bound persisted/model-returned command output.
4. Separate candidate generation from verification policy. Run server/repository-selected required checks plus any model suggestions; execute smoke checks; rebuild a fresh staging tree for each repair attempt; package exactly the tree that passed.
5. Verify every staged bundle artifact digest immediately before apply; persist/flush rollback intent before mutation; use destination/bundle locks; consume durable actor-bound approvals once.
6. Make an empty/nonexistent audit chain invalid, strictly validate artifact digests, fix optional token-budget narrowing, validate provider URLs/host classes, and use a minimal child-process environment allowlist.
7. Pin sandbox images by digest for production profiles and enforce complete snapshot/candidate/command/output/workflow resource bounds.
8. Add `M005-001` for append-only `ExternalContent` and `ContextEnvelope` provenance. Legacy V1 runs use a typed legacy-run owner until Milestone 1 links new envelopes to mandatory request contexts; imported trust never exceeds `untrusted` without an audited review.

Checkpoint: adversarial secret-exfiltration, forged-verification, stale-staging, altered-bundle, crash-point, SSRF, environment-leak, context-provenance, and audit-tamper tests pass; an independent read-only security review accepts this checkpoint before Task 1.1 begins.

### Milestone 1 — Project authority vertical slice
1. Add `DeploymentProfile`, `WorkspaceConfig`, fenced `WorkspaceAuthority`/handoff, `ClientContext`, `ExecutionPlacement`, identity, discriminated scope, audience snapshots, requester/agent grants, `EffectiveCapabilities`, idempotency, and audit contracts with an explicit combination table.
2. Add `M1-001` and an idempotent migration-backed local project/authority/audience/audit repository without mutating legacy V1 rows; add only the project/config portions of the per-domain importer from sealed quarantine. V1 policy/autonomy waits for `M6-002`.
3. Implement fail-closed authorization with deny precedence, exact scope containment, expiry/revocation, acting-agent intersection, budget/kill-switch checks, and immutable allow/deny receipts.
4. Implement one transport-neutral `create_project`/`get_project` application path through identity -> authorization -> repository -> audit.
5. Test in-process command/query ports, authority fencing/handoff recovery, cross-workspace/project/audience denial, receipt persistence failure, idempotency revocation/mismatch/concurrency, per-domain import repetition/rollback, and client-surface parity.

Checkpoint: equivalent authenticated requester, transport, and acting-agent authority produces the same project create/read decision across every enabled client surface. A disabled adapter, mismatched transport principal, tampered client context, stale authority epoch, different workspace/agent/audience, revoked retry, or mismatched replay is denied; every decision has a verifiable signed receipt/checkpoint.

### Milestone 2 — Outcome contracts and durable workflow graphs
1. Add immutable outcome-contract versions, pinned workflow graphs, nodes/dependencies, fenced leases, attempts, checkpoints, recovery decisions, typed lineage nodes/edges, budget reservations, runtime limits, kill switches, external-effect intents/attempts, and effect-outbox tables through `M2-001`–`M2-004`.
2. Implement transactional claim/heartbeat/release/complete with optimistic versions, authority epochs, and monotonic lease fences.
3. Add scoped V2 events plus a state/event/effect-outbox transaction service and the workspace-sequenced audit chain.
4. Implement stuck detection and bounded `retry -> replan -> decompose` recovery with honest exhaustion.
5. Adapt `ConversationRuntime` to enqueue durable work rather than own ephemeral truth.
6. Add the centralized effect gateway: semantic idempotency, current authorization/budget/kill-switch/lease validation at dispatch, provider idempotency, and explicit cancellation/compensation. Add per-domain importers for V1 outcomes, run history, artifacts, and conservative budget ceilings.

Checkpoint: restart preserves queues/events/checkpoints; dependencies and limits gate execution; stale authority/lease fences cannot mutate state or duplicate an external effect; kill-switch and budget races fail closed at intent and dispatch; completion requires the pinned outcome version and a verified immutable lineage closure.

### Milestone 3 — CLI V2 project/run vertical slice
1. Add local identity bootstrap and additive `corvus v2 project create|get` commands over the application ports.
2. Adapt one build workflow through context firewall -> outcome contract -> authorization -> work graph -> sandbox -> independent verification -> package -> approval.
3. Use fake provider/sandbox tests; Docker/Podman remain marked integration tests with no host fallback.
4. Add pause/resume/cancel/retry, kill-switch, evidence, lineage, and event-tail commands.

Checkpoint: a fake-provider build executes the real state machine and produces a verifiable lineage-bound bundle without host writes.

### Milestone 4 — FastAPI, authentication, and replayable events
1. Add the concrete cloud/self-hosted auth adapters, command/query API, OpenAPI, and scoped SSE protocol.
2. Enforce request, agent, scope, audience, credential, placement, budget, and kill-switch authorization on every route and replayed event.
3. Add idempotency, CSRF/session/token, 403/404 non-enumeration, cursor/gap/backpressure, and cross-tenant/thread tests.
4. Generate TypeScript contracts and prove Python in-process/HTTP parity.

Checkpoint: unauthorized access leaks no existence or private events; reconnect uses snapshot plus cursor replay without gaps or duplicates.

### Milestone 5 — Web workspace
1. Scaffold pnpm workspace, `apps/web`, `packages/client-ui`, and generated `packages/contracts`.
2. Implement authentication, project create/read, work submission, persisted event timeline, outcome criteria, evidence, lineage, approvals, limits, and kill-switch controls.
3. Add Vitest, API-backed Playwright, accessibility, responsive, hostile-preview-origin, and reconnect tests.

Checkpoint: browser completes the fake-provider project/work/evidence flow using only backend-reported state and capabilities.

### Milestone 6 — Team, provider, secret-broker, and earned-autonomy slice
1. Prove owner/member collaboration, reviewer separation, comments, approval, and shared budgets in one workspace.
2. Add `ProviderConnection -> CredentialRef -> CredentialVersion -> CredentialGrant` lifecycle, health, atomic rotation/revocation, exact request/agent/placement/purpose/use-limit binding, and the `M6-001` importer for provider/keyring references only.
3. Add persisted OAuth authorization-code + PKCE and device-flow transactions, callback ownership, expiry/consumption, refresh-family rotation, revocation, and recovery. Prove one local provider-owned OAuth fixture and one deterministic server OAuth lifecycle fixture; API-key-only coverage cannot pass this milestone.
4. Implement scoped short-lived secret grants with zero secret material in prompts/events/traces/snapshots/errors.
5. Add the normative autonomy action/effect matrix and shadow-mode comparison through `M6-002`/`M6-003`; import V1 policy/autonomy YAML capped at `propose`, and require evaluation, reliability threshold, approval, canary limits, compensation, and rollback for promotion.

Checkpoint: one team run uses a brokered provider connection and shadow proposal; both OAuth lifecycle fixtures pass; shadow runs have no production credential/effect path; unauthorized members/agents cannot retrieve secrets, raise autonomy, approve themselves, or exceed limits.

### Milestone 7 — Governed memory, skills, routines, and context firewall
1. Add `M7-001` scoped encrypted memory with typed owner/audience, source digest, key version, confidence, expiration, cross-workspace promotion checks, export, and deletion/retention receipts; then run the V1 memory importer twice.
2. Add `M7-002` versioned skills with evaluation suites, hidden holdouts, approval, shadow/canary stages, regression detection, and rollback; then run the V1 skill importer twice.
3. Route external/retrieved content through the context firewall before any model or memory use.
4. Add routines/webhooks through normal outcome, authority, budget, kill-switch, evidence, and audit paths.

Checkpoint: prompt-injection fixtures cannot grant authority; memory deletion/export is auditable; a regressing skill rolls back; routines cannot bypass interactive controls.

### Milestone 8 — Secure connector and offline operation
1. Define outbound-only mTLS pairing, ownership, model-only RPC, health/capability registration, consent, revocation, updates, egress bounds, and audit.
2. Connectors never acquire workspace authority. Schedule connector work only while an authorized runner/model is online under the current authority epoch; preserve waiting state without exposing localhost.
3. Add `M8-001` signed offline intent, non-authoritative cache, reconnect, dedupe, conflict, revocation, and replay metadata. A local-authority workspace may execute approved offline work; a remote-authority client may only queue intents for fresh authorization after reconnect.
4. Prove offline local models, cached resources, governed memory, and queued tasks in local-authority mode while cloud-only capabilities fail with reason codes.

Checkpoint: cloud work can use an explicitly paired local model without receiving permanent credentials; stale grants/epochs cannot execute queued work; reconnect/revoke/conflict/replay fail closed; no test can produce dual-primary authority.

### Milestone 9 — Channel gateways
1. Add signed ingress, provider-event dedupe, identity mapping, immutable bindings, rate limits, bounded replies/files, and correlation.
2. Require browser/desktop step-up for privileged approvals and apply operations.

Checkpoint: replayed/forged/cross-thread messages cannot create duplicate work, broaden authority, or approve high-risk effects.

### Milestone 10 — Operational self-hosted and vendor-cloud deployment proof
1. Define separate topology contracts for self-hosted and vendor cloud: TLS/auth bootstrap, PostgreSQL migrations, worker/effect-gateway topology, durable artifact storage, vault/KMS, tenant boundaries, observability, maintenance, capacity, and supported upgrade paths.
2. Build deployment fixtures for first install, version upgrade, database/artifact backup and restore, key rotation, worker loss, region/service degradation, migration failure, and rollout rollback.
3. Prove tenant isolation across database rows, event replay, artifacts, vault grants, workers, caches, logs, metrics, traces, backups, and support/operations access.
4. Require signed release provenance, SBOM binding, health gates, staged rollout, and a documented disaster-recovery objective before either topology is called supported.

Checkpoint: self-hosted and vendor-cloud test environments each complete install -> migrate -> execute -> backup -> restore -> rollback; adversarial tenant-isolation and failed-rollout tests pass with verifiable receipts.

### Milestone 11 — Desktop and distribution
1. Package the stabilized web client in Tauri with a signed sidecar lifecycle and narrow capabilities.
2. Add the distribution matrix: Python wheel/standalone CLI, OCI self-host image, static web assets, and signed Windows/macOS/Linux desktop installers with protocol compatibility and rollback.
3. Use a TUF-style threshold-signed update protocol: offline root keys, delegated targets/snapshot/timestamp keys, metadata expiry, monotonic version/rollback and freeze protection, key rotation/revocation recovery, reproducible provenance attestations, and SBOM-to-artifact digest binding.
4. Run OS/architecture CI for keyring, path casing, UNC/long paths, junctions/symlinks, service lifecycle, installer/update, staged rollback, expired/revoked metadata, and optional sandbox routing.

Checkpoint: desktop runs the proven team/provider flow without duplicate authority code or generic shell/filesystem access; every artifact verifies provenance/SBOM, installs, rejects rollback/freeze attacks, updates through threshold-signed metadata, survives key rotation/revocation fixtures, and rolls back through a tested path.

## Immediate TDD Task List

The baseline-capture/bootstrap portion of Task 0.7 is the first pending action despite its later planning number: freeze pre-change fixtures and establish version-aware bootstrap before Tasks 0.3–0.6 alter behavior. Apply `M005-001` only after that bootstrap exists, then rerun the complete golden/quarantine checks to finish Task 0.7 and the Milestone 0.5 gate.

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

### Task 0.3 — Secret-safe snapshots, context firewall, and repair isolation
- Create tests: `tests/security/test_snapshot_policy.py`, `tests/security/test_context_firewall.py`, `tests/security/test_secret_flow.py`, `tests/security/test_workflow_repair_isolation.py`.
- Modify: `corvus/workflow.py`, `corvus/security.py`; add a focused context/snapshot policy module only if the tests require it.
- First failing assertions: `.env`/credential/cache/dependency paths are excluded by default; limits block oversized trees; plaintext staging is removed; external/model-returned instructions remain attributed untrusted data and cannot request tools/secrets/authority; repair context is redacted/bounded; each attempt starts from a clean approved snapshot.

### Task 0.4 — Trustworthy verification
- Create tests: `tests/security/test_verification_trust.py` and extend `tests/security/test_workflow_repair_isolation.py`.
- Modify: `corvus/workflow.py`, `corvus/verification.py`.
- First failing assertions: model-declared trivial commands cannot satisfy required checks; smoke checks execute; stale files cannot influence a later attempt; the packaged tree is the exact passing tree.

### Task 0.5 — Bundle integrity and atomic delivery
- Create tests: `tests/security/test_bundle_tampering.py`, `tests/security/test_delivery_atomicity.py`, and extend `tests/security/test_delivery_approval.py`.
- Modify: `corvus/delivery.py`; add a lock/approval repository port only where the test requires it.
- First failing assertions: altered staged files, replayed/expired/mismatched approval, concurrent apply, and injected failure after each filesystem step never produce an unjournaled or unauthorized delivery.

### Task 0.6 — Server-boundary hardening
- Create tests: `tests/security/test_structured_redaction.py`, `tests/security/test_provider_url_policy.py`, `tests/security/test_codex_environment.py`, `tests/security/test_artifact_digest.py`, `tests/unit/test_config_narrowing.py`.
- Modify: `corvus/security.py`, `providers.py`, `codex_cli.py`, `store.py`, `config.py`.
- First failing assertions: nested secrets redact; internal/credential-bearing provider URLs are rejected for cloud profiles; child environment is allowlisted; invalid digests fail; optional token limits always narrow.

### Task 0.7 — V1 golden capture and version-aware migration bootstrap
- Create tests: `tests/contract/test_v1_public_golden.py`, `tests/integration/test_database_bootstrap.py`, `tests/integration/test_v1_quarantine_capture.py`.
- Freeze hashed fixtures for every public command/JSON shape plus V1 database/config/onboarding/provider-reference/policy/autonomy/memory/skill/conversation/run/bundle/artifact/backup domains.
- Replace runtime `create_all()` with one version-aware new/unstamped/current/partial/incompatible database bootstrap, explicit backup/stamp/upgrade/quarantine/restore behavior, and no silent mutation.
- Capture legacy records into a sealed canonical quarantine twice without duplication; do not convert a domain until its destination migration exists.
- Gate: Tasks 0.3–0.7 and the Milestone 0.5 checkpoint must pass, and Milestone 0.5 must receive independent read-only acceptance, before Task 1.1 starts.

### Task 1.1 — Configuration, identity, scope, and audit contracts
- Create: `corvus/domain/deployment.py`, `workspace.py`, `client.py`, `execution.py`, `identity.py`, `scope.py`, `access.py`, `audit.py`.
- Create tests: `tests/unit/domain/test_configuration_matrix.py`, `test_identity.py`, `test_scope.py`, `test_access_models.py`, `test_audit_models.py`.
- First failing assertions: overloaded profile fields are impossible; unsupported combinations fail with reason codes; client surface cannot grant authority; authority epochs cannot fork or regress; handoff cannot activate two owners; discriminated scope parentage and audience snapshots are workspace-bound; missing workspace/requester/agent grant, cross-workspace scope, plaintext credential values, naive expiry, and unstable digests are rejected.

### Task 1.2 — Fail-closed requester and acting-agent evaluation
- Create: `corvus/application/authorization.py`.
- Create test: `tests/unit/application/test_authorization.py`.
- Matrix: exact allow, no-grant deny, explicit deny wins, wrong principal/workspace/project/thread/audience, stale authority epoch, expired/revoked requester or agent grant, delegation overreach, placement/credential mismatch, budget/runtime exhaustion, kill switch, and enabled-client-surface parity.

### Task 1.3 — Migration-backed project and audit repositories
- Create: `corvus/infrastructure/db.py`, `corvus/infrastructure/repositories/projects.py`, `audit.py`, and initial Alembic migration/fixture paths.
- Create tests: `tests/integration/test_project_repository.py`, `test_scoped_audit_repository.py`, `test_v1_migration.py`.
- Persist project ownership, authority epochs/handoffs, discriminated scope, audience snapshots, access-bundle/agent-grant snapshot digests, workspace-sequenced immutable receipts, signed checkpoints/key epochs, and fully bound idempotency envelopes without changing legacy rows.
- Add the project/config importer after `M1-001`; verify migration/import twice, tampering, audit append concurrency, cross-workspace/audience reads, rollback fixture readability, stale-authority rejection, revoked cached-result denial, and concurrent duplicate commands. V1 policy/autonomy is not converted until `M6-002`.

### Task 1.4 — Transport-neutral project create/read service
- Create: `corvus/application/projects.py`, `corvus/application/ports.py`, and an in-process client adapter.
- Create tests: `tests/integration/test_project_authority_slice.py`.
- One command/query path resolves effective capabilities, records allow/deny, creates or reads the project transactionally, and fails closed if authorization/audit persistence fails.

### Task 1.5 — Vertical contract and compatibility tests
- Create tests: `tests/contract/test_inprocess_project_client.py`, `tests/cli/test_v1_compatibility.py`.
- Prove stable command/query/error envelopes, currently authorized idempotent response replay, payload mismatch/revocation rejection, equivalent decisions across enabled client surfaces, disabled-adapter and mismatched-transport denial, no secret fields, and unchanged retained V1 command availability.
- Do not add CLI V2, FastAPI, or UI adapters in this milestone.

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
- Worker A — Tasks 0.3–0.7 only: first freeze Task 0.7 fixtures/bootstrap, then complete remaining Milestone 0.5 security work and `M005-001`, then rerun/finalize the golden and sealed-quarantine checks. Must not edit new authority schemas.
- Reviewer 0.5 — independently verifies the completed Milestone 0.5 checkpoint and Task 0.7 migration-preflight evidence. A revise verdict blocks Worker B.
- Worker B — configuration/authority/identity/scope/audience/access/audit domain contracts and tests only. Starts only after the exact plan review passes, Worker A completes Tasks 0.3–0.7, and Reviewer 0.5 accepts the checkpoint.
- Worker C — project/authority/audience/audit persistence, migrations, domain importer, fixtures, and repository tests. Starts only after Worker B contracts are fixed and reviewed; it does not overlap Worker B.
- Worker D — transport-neutral project application service and contract/compatibility tests. Starts only after Worker C is fixed and reviewed; it does not overlap Workers B/C.
- Reviewer — read-only spec, security, migration, diff, test, and acceptance review. Must not be the implementing worker.
- Limit concurrent local workers to two because RAM is constrained; never combine heavy Node/Rust/container builds.

## Acceptance Criteria

### Plan-level
- The plan separates deployment, workspace collaboration, client context, execution placement, model routing, and credential ownership by lifetime/cardinality.
- Every locked capability maps to an authoritative service, persistent record, enforcement point, migration path, and test strategy.
- Web, desktop, and channels reuse contracts and clients rather than duplicate authority or run state.
- V1 compatibility, migration, checkpoints, review freshness, and rollback points are identified.

### Immediate implementation slice
1. Repository installs reproducibly with `uv sync --locked` under Python 3.12.
2. Existing CLI help and doctor JSON pass from the installed project.
3. Regression tests cover retained path, sandbox, event-chain, and delivery-approval primitives.
4. Default build snapshots exclude secret/cache/dependency material, enforce size/count limits, and clean up after success, failure, or cancellation.
5. Required verification is selected by Corvus/repository policy rather than trusted solely from generating-model commands; smoke checks execute and each repair uses a clean staging tree.
6. Delivery rehashes every staged file, rejects approval mismatch/replay/expiry, locks concurrent apply, and remains recoverable at every injected crash point.
7. Structured secrets are redacted before prompts, persistence, repair context, events, traces, snapshots, or errors; child environments and provider destinations are allowlisted.
8. Deployment/workspace/client/execution/model/credential contracts cannot express an overloaded profile or plaintext secret; a workspace has one monotonic fenced authority epoch and a signed handoff cannot activate two owners.
9. A request cannot exist without deployment, workspace authority epoch, discriminated scope, immutable audience snapshot, requester, client/transport context, acting agent grant, requester access bundle, policy digest, correlation ID, and idempotency key.
10. Effective authority is the minimum requester/agent/delegation/channel/workspace/budget/placement/credential/kill-switch intersection; deny wins and scope never broadens.
11. Equivalent authenticated requester/transport/agent authority creates and reads one project through every enabled client surface; disabled adapters, mismatched transports, tampered contexts, and cross-workspace/project/audience substitutions fail.
12. Allow and deny decisions create immutable requester/agent/authority-epoch receipts with a unique workspace sequence; append and chain-head persistence failure prevents the protected action.
13. All public V1 command/JSON and database/domain fixtures are hashed; version-aware bootstrap detects partial/unstamped state; quarantine capture runs twice without duplication; each destination migration/import runs twice and preserves rollback/legacy readability.
14. Idempotent command retries replay only after current read authorization; payload mismatch, revocation, and concurrent duplicates do not disclose data or create a second project.
15. Empty audit chains are invalid; checkpoints cover a deterministic workspace sequence/authority/key epoch; artifact lookups accept only canonical SHA-256 digests.
16. Existing V1 CLI commands remain available; no CLI V2, FastAPI, web, desktop, channel, deployment, purchase, or live provider call occurs in this slice.
17. Sandbox unavailability still produces no host-execution fallback.
18. The exact final plan revision receives a fresh independent review before any remaining implementation.
19. Task 1.1 remains blocked until Tasks 0.3–0.7 pass and an independent reviewer accepts the completed Milestone 0.5 checkpoint.

### Later client milestones
- API routes authorize every resource and each live/replayed event against immutable scope/audience.
- Web, desktop, CLI, and channels render only persisted state plus backend-returned effective capabilities.
- Team collaboration and provider/secret-broker flows stabilize through CLI/web before channel or desktop packaging.
- Connector and offline behavior have explicit scheduling, revocation, unavailable-reason, and recovery tests.
- Desktop has no generic shell/filesystem grant and contains no duplicate policy, persistence, or run-state implementation.
- Self-hosted and vendor-cloud modes are not supported until separate install/migrate/backup/restore/tenant-isolation/rollout-rollback deployment gates pass.
- Desktop updates use threshold-signed expiring metadata, rollback/freeze protection, key-rotation/revocation recovery, reproducible provenance, and SBOM binding.
- One fake-provider lineage-bound vertical slice works across in-process CLI, HTTP/web, and desktop clients before release.

## Verification Matrix

| Layer | Tests |
|---|---|
| Configuration/domain | allowed/invalid combinations, authority epoch/handoff fencing, capability projection, canonical digests, discriminated scope parentage, audience snapshots, state transitions |
| Authorization | requester/agent/delegation intersection, deny precedence, expiry/revocation, authority epoch, audience, limits, kill switches, enabled-client parity |
| Persistence/migration | V1 golden/quarantine capture, version-aware bootstrap, per-domain repeated imports, rollback fixtures, uniqueness, transactions, sequenced receipt/event chains, tamper and isolation |
| Outcomes/workflows/effects | pinned criteria/evidence, immutable lineage closure, claim races, fenced leases, semantic idempotency, transactional outbox, effect-gateway kill/budget races, compensation, stuck recovery, dependencies, cancellation |
| Context firewall | provenance, instruction/data separation, bounded ingestion, prompt-injection and retrieved-content canaries |
| Secret broker/providers | zero-secret traces, workspace/connection/version/request/agent/placement/purpose/use binding, host/method/path limits, atomic rotation/revocation, local and server OAuth lifecycle fixtures |
| Skills/autonomy | normative action/effect matrix, no-effect shadow, evaluation versions, hidden holdouts, reversible canary approval/limits/compensation, regression and rollback |
| Memory governance | typed workspace scope/owner/audience isolation, immutable source digest, key version, confidence/expiry, cross-workspace promotion, export and deletion/retention receipts |
| Sandbox | option contract unit tests; marked Docker/Podman integration tests only where available |
| Delivery | manifest/artifact rehash, approval binding, locking, crash atomicity, backup/undo, malicious paths |
| CLI | Typer tests, stable envelopes, V1 compatibility, later project/work/evidence commands |
| API/events | OIDC/session/CSRF/token tests, 403/404 behavior, idempotency, OpenAPI, scoped cursor replay/reconnect |
| Web/channels | API-backed Playwright, accessibility, hostile preview, signed ingress, dedupe, step-up approval |
| Connector/offline | mTLS pairing, no connector authority, consent, health, egress, signed intent dedupe/conflict/revocation/replay, local-authority execution, remote-authority queue-only behavior |
| Deployment operations | separate self-host/cloud install and upgrade, PostgreSQL/workers/artifacts/vault/KMS, tenant isolation, backup/restore/DR, observability, staged rollout rollback |
| Desktop/distribution | Tauri capability audit, sidecar protocol, TUF-style threshold metadata, expiry/rollback/freeze defense, key rotation/revocation, provenance/SBOM, OS/architecture CI |
| Security/quality | Pytest, Ruff, Bandit under Python 3.12, dependency audit, SBOM, secret scan, tenant/scope isolation |

## Key Decisions and Tradeoffs
- **One Python core, thin clients:** avoids three diverging agent/security implementations.
- **Fix V1 trust boundaries before exposing V2:** authorization models do not make an unsafe snapshot/verification/delivery pipeline safe; critical build and delivery defects are gated ahead of web/team enablement.
- **Separated configuration contracts, not editions or one profile:** deployment, workspace collaboration, client context, execution placement, model route, and credential ownership resolve independently into effective capabilities.
- **One fenced authoritative control plane per workspace:** a persisted monotonic authority epoch and signed atomic handoff govern local/cloud movement; connectors never become authority and remote-offline copies can queue intents only.
- **Earned autonomy:** agents and skills begin in shadow/proposal stages and advance only through versioned evidence, approval, canaries, monitoring, and rollback.
- **Bring-your-own models:** users supply local endpoints, API credentials, or provider OAuth. Corvus stores credential references and brokers access; it does not conflate a Corvus subscription with model entitlement.
- **Local model with cloud control plane requires a connector:** Corvus Cloud never assumes it can reach localhost and never asks users to expose an unauthenticated model port.
- **Vite React rather than Next.js for the workspace client:** the product is an authenticated application, not an SEO surface; static client assets are reusable by Tauri. FastAPI remains authoritative.
- **Tauri rather than Electron:** smaller native boundary and explicit capabilities, while still reusing React UI.
- **Incremental migration rather than wholesale directory move:** preserves V1 behavior and makes regressions attributable.
- **New scoped audit repository before rewriting legacy events:** provides a safe team boundary without an all-at-once event-store migration. Legacy events remain local-only until adapted.
- **Fake provider/sandbox for deterministic tests, no host fallback:** allows verification on this machine without pretending unsandboxed builds are secure.
- **Transport-neutral ports plus generated clients:** one composition root and in-process/HTTP Python parity prevent CLI drift; OpenAPI-generated TypeScript prevents web/desktop contract drift.
- **Context firewall before model or memory use:** external/retrieved content remains attributed untrusted data and cannot grant instruction, tools, secrets, permissions, or autonomy.
- **Server-side access bundle resolution:** transport tokens are references, not authority.
- **No OpenClaw shared gateway as tenant boundary:** borrow queue/session/capability patterns only; Corvus owns authorization or isolates gateways per tenant.
- **No Claude Tag embedding:** implement first-party `@Corvus`; Claude models may be providers through supported APIs.

## Risks and Mitigations
- **Unknown V1 production data:** freeze all public command/JSON/database/domain fixtures; replace `create_all()` with version-aware bootstrap; capture immutable sealed quarantine twice before evolution; add each idempotent policy/autonomy/provider/memory/skill/run/artifact importer only after its destination migration, with backup/restore/rollback tests.
- **Plaintext snapshot and model-output exfiltration:** default-deny snapshot policy, structured redaction, output bounds, clean attempt trees, and cleanup are release blockers.
- **Model-selected verification:** repository/server-required checks and independent reviewer evidence must dominate model suggestions.
- **Bundle TOCTOU/crash windows:** rehash at apply, durable one-time approvals, locks, and crash-point testing are mandatory.
- **Large CLI/TUI modules:** keep adapter registration changes minimal; extract use cases before UI rewrites.
- **Hash-chain concurrency or incomplete checkpoints:** append each schema-versioned receipt, workspace-global sequence, authority/key epoch, and chain head transactionally; test concurrent appends, signing-key rotation/revocation, and checkpoint completeness.
- **SQLite limits:** supported only for one authoritative single-process individual local workspace with file locking, integrity checks, backups, and documented recovery; PostgreSQL is required before networked or multi-worker operation.
- **Scope-comparison bugs:** centralize containment logic and use exhaustive table/property tests.
- **Approval replay:** store nonce digest and single-use status in a transaction; bind to requester/reviewer/action/manifest/expiry.
- **Credential leakage or confused ownership:** typed workspace/provider/credential-version/request/agent/placement/purpose/use bindings are mandatory; OAuth state/PKCE/callback/refresh/revocation persists; the broker issues short-lived host/method/path-scoped access and zero-secret traces.
- **Acting-agent authority drift:** recompute the requester/agent/delegation/channel/workspace/budget/placement/credential/kill-switch intersection at every effect.
- **Context injection:** all external/retrieved content remains provenance-labelled untrusted data behind instruction/context separation and adversarial fixtures.
- **Premature autonomy promotion:** shadow/canary stages, hidden holdouts, independent approval, regression thresholds, kill switches, and rollback gate every increase.
- **Memory deletion gaps:** export/deletion receipts cover primary rows, indexes, caches, artifacts, and documented backup-retention exceptions.
- **Stale worker duplicate effects:** no worker calls an external provider directly; semantic idempotency, fenced leases, transactional effect outbox, current kill/budget authorization, provider idempotency, and explicit compensation/cancellation are enforced by one effect gateway.
- **Connector compromise or offline ambiguity:** outbound-only mTLS, model-only RPC, consent, egress limits, health scheduling, revocation, fenced workspace authority, queue-only remote-offline intents, and explicit unavailable states fail closed.
- **SSE data leakage:** authorize every event against immutable scope/audience and test opaque cursor replay, retention gaps, backpressure, and cross-thread denial.
- **Desktop privilege creep:** Tauri capabilities are reviewed as code and tested against an allowlist.
- **Dependency/update supply chain:** lock Python/Node/Rust dependencies; add audits, reproducible provenance, SBOM binding, and a TUF-style threshold-signed updater with offline root, delegated rotating keys, expiry, rollback/freeze defense, revocation recovery, and staged rollback tests.
- **Declared deployment modes without operational proof:** keep self-hosted/vendor-cloud unsupported until PostgreSQL, workers, durable artifacts, vault/KMS, tenant isolation, backup/restore/DR, observability, migration, and failed-rollout rollback gates pass separately.
- **Resource pressure:** serialize Node/Rust builds and avoid local container builds while RAM is constrained.
- **Review availability:** Claude returned HTTP 401, Gemini required Antigravity migration, and Codex timed out without a verdict. Earlier Hermes audits found V1 trust/topology issues. The exact-commit paired review of `6bc2136` completed with two `VERDICT: REVISE` results and 17 accepted findings now recorded in `PLAN-REVIEW-LOG.md`. This new exact revision still requires both fresh scopes to return without a revise verdict; no timeout or partial result is approval.

## Rollback and Checkpoints
1. `1410d7f` remains the immutable imported V1 baseline.
2. Commit this revised plan and review log separately; record the exact plan digest reviewed.
3. Refresh independent reviewers against that exact revision. Do not begin Task 1.1 schemas/contracts until a completed review no longer requires revision.
4. One commit per TDD task or tightly coupled security fix; never rewrite baseline or hide incomplete gates.
5. Before authority schema work, complete Tasks 0.3–0.7: hash every V1 public/database/domain fixture, validate version-aware bootstrap, run sealed quarantine capture twice, pass the Milestone 0.5 checkpoint, and obtain independent acceptance.
6. After each destination migration, run only that domain's importer twice and verify legacy readability plus backup/restore/downgrade boundaries; never use a premature all-domain conversion.
7. CLI V2 commands are additive until replacements pass compatibility tests.
8. API, web, team/provider, connector, channel, deployment, and desktop work live on separate reversible feature commits.
9. Autonomy/skill promotions always retain the previous active version and rollback receipt.
10. No deployment, public release, live provider call, external message, credential migration, or purchase occurs in this plan.

## First Implementation Slice to Build Immediately
After this exact plan revision passes fresh review, finish Tasks 0.3–0.7 as separately reviewed TDD commits: release-blocking trust fixes, context provenance persistence, complete V1 golden capture, version-aware bootstrap, and sealed quarantine capture. Obtain independent acceptance of the completed Milestone 0.5 checkpoint. Only then may Worker B begin Milestone 1's transport-neutral project create/read authority contracts, followed sequentially by persistence and application workers. Do not add CLI V2, FastAPI, React, channel, connector, deployment, desktop, live providers, or broad workflow/autonomy features until that project slice and complete quality/security gate pass.
