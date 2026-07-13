# Plan Review Log: Corvus CLI V2 and Shared Web/Desktop Platform
Started 2026-07-13 12:58:48 +0800. Initial reviewer: Gemini CLI gemini-3.1-pro-preview. The external three-round target was followed by recorded Hermes refresh rounds because external reviewers were unavailable.

## Planner availability
Claude Code planning was attempted first and returned HTTP 401 before reading or changing the repository. No Claude-generated plan content was used.

## Round 1 - Gemini (blocked)
Gemini CLI exited before reading the plan with `IneligibleTierError`: the installed Gemini Code Assist for individuals client is no longer supported and requires migration to Antigravity. No Gemini critique or verdict was produced.

### Codex/Hermes response
- No reviewer feedback was incorporated because none was produced.
- The plan remains unapproved by Gemini.
- Lucas explicitly approved a fallback consisting of read-only Codex CLI review plus two independent Hermes audits.

## Round 2 - Codex CLI fallback (blocked)
Codex CLI ran in an ephemeral read-only sandbox and inspected the plan and V1 source, including a security-plugin preflight. It did not return a final message or verdict within the bounded ten-minute review window and was terminated. The configured output file was not created. No Codex critique was incorporated and no approval is claimed.

### Remaining approved review gate
Use the two independent Hermes audits already dispatched before implementation. Record their concrete findings and the Codex/Gemini limitations without representing either external reviewer as approved.

## Round 3 - Initial independent Hermes audits
Two read-only GPT-5.6-sol reviewers inspected all 27 V1 source files. Both concluded that V1 is a strong single-user prototype but must not be wrapped directly in a web API or split into independent clients.

### Material findings
- Critical: no multi-user authorization/tenant boundary; policy is largely disconnected from execution.
- Critical: snapshots can include secrets and retained plaintext; command output can be sent back to the model.
- Critical: the generating model selects its own checks, smoke checks are unused, and repair attempts can reuse stale files.
- Critical: approved bundle files are not rehashed before apply; approval is same-command/in-memory; journal and locking leave crash/TOCTOU windows.
- High: structured secret redaction fails for ordinary nested JSON; provider URLs create server-side SSRF risk; Codex children inherit a broad host environment.
- High: empty audit chains verify successfully, the chain is recomputable by a database modifier, artifact digests are not strictly validated, resource limits are incomplete, and optional token-budget narrowing can widen limits.
- Product: preserve fail-closed sandboxing, explicit chat/build boundary, delivery/undo ergonomics, transparent model routing, bounded delegation, doctor/trace JSON, and local-first behavior.
- Product: extract one headless control plane and versioned protocol; ship CLI and web against it before wrapping the proven web client in Tauri.
- Migration: add golden tests for all public commands and JSON shapes plus an idempotent V1 importer before schema evolution.

### Codex/Hermes response
Accepted all release-blocking findings. `PLAN.md` now adds Milestone 0.5 for snapshot/redaction/verification/delivery/provider/audit hardening; signed audit checkpoints; golden command/protocol tests; an idempotent V1 importer; and a runtime-profile capability projection. Web, desktop, and channel adapters remain blocked until these gates and the refreshed post-configuration audits pass.

The reviewers began before the local baseline Git repository was initialized; their statement that the archive was not a Git repository was accurate at audit start. The current repository now has immutable baseline commit `1410d7f`.

## Round 4 - Refreshed post-configuration Hermes review
The paired security/schema reviewer timed out after 15 calls and produced no summary or verdict. This is blocked evidence, not approval.

The completed product-topology reviewer inspected committed plan `a59babe` and returned `VERDICT: REVISE`. Material findings required: split overloaded `RuntimeProfile`; event-level private scope/audience; acting-agent grants and authority intersection; implementable connector and provider/credential lifecycles; one authoritative control plane per workspace; concrete production auth and SSE semantics; transport-neutral Python ports; a smaller real project vertical slice; distribution/desktop lifecycle; team/provider/channel work before desktop; channel step-up approval; supported SQLite/cross-platform envelope; and persisted idempotency semantics.

## Lucas feature brief - locked requirements
Lucas added outcome contracts; evaluated/canary/rollback skills; context firewall; scoped temporary secret broker; six autonomy levels; shadow mode; durable workflow graphs and bounded recovery; artifact lineage; governed memory; kill switches and limits; and offline local-model/cache/memory/queue operation. Security and the project create/read flow must precede CLI V2, FastAPI expansion, or React UI work. Existing modules should be reused, compatibility preserved where practical, changes remain migration-backed and TDD-driven, secrets never enter prompts/events/traces/snapshots/errors, and incomplete work must remain explicit.

### Codex/Hermes response
`PLAN.md` now separates deployment, workspace, client, execution, model-route, and credential contracts; adds an allowed-combination table and effective-capability projection; models scope/audience events, acting-agent/delegation authority, provider/credential grants, outcome/workflow/lineage/kill-switch records, context firewall, governed memory/skills, autonomy/shadow promotion, connector/offline behavior, concrete auth/SSE/idempotency, distribution, and the locked implementation sequence. The immediate authority milestone is now one migration-backed transport-neutral project create/read vertical slice, not a broad synthetic foundation or early CLI/API/UI expansion.

### Remaining gate
Commit and hash this revised plan, then run a fresh independent review against that exact revision. Do not begin Task 1.1 schema/domain implementation while that verdict is pending or requires revision.

## Round 5 - Exact-commit paired Hermes review of `6bc2136`
Two fresh read-only GPT-5.6-sol reviewers completed non-overlapping reviews of exact commit `6bc2136038c8abdea7746243cb057c004969f150`. Both returned `VERDICT: REVISE`; this is not approval and no authority/schema implementation began.

### Security/schema/authorization findings
- Critical: “one authoritative control plane” lacked persisted epochs/fencing and atomic handoff, so remote-offline work could execute under stale grants.
- Critical: leases prevented duplicate completion but not duplicate external effects or kill-switch/budget check-to-effect races.
- High: invalid-state-prone optional scope fields and digest-only audience references could not support deterministic replay authorization.
- High: credential grants were insufficiently bound to workspace, provider connection/version, request/agent grant, placement, purpose, and usage.
- High: idempotency lacked a complete persisted principal/context key and could replay data after revocation.
- High: workflows did not pin immutable outcome versions and lineage used mutable bare-ID arrays.
- High: audit checkpoints lacked a corresponding transactional workspace-global sequence, authority epoch, schema version, and signing-key lifecycle.
- High: autonomy levels had no normative effect semantics; shadow mode could still use existing credentials/effects.
- High: memory owner/scope/audience/promotion/encryption/deletion-retention contracts were ambiguous.
- High: V1 migration needed complete golden fixtures, version-aware bootstrap, quarantine, and policy/autonomy coverage before schema evolution.
- High: the Milestone 1 client-surface denial contradicted transport-neutral authority.
- High: desktop updates lacked a threshold-signed trust root, rollback/freeze protection, key lifecycle, provenance, and SBOM binding.

### Product topology/sequencing findings
- Worker B was allowed to overlap unfinished Milestone 0.5 work, contradicting the security gate.
- One all-domain importer was scheduled before most destination schemas existed and omitted V1 policy/autonomy YAML.
- The eleven locked capabilities lacked a complete persistence/migration/cutover/rollback/test ledger.
- Provider OAuth lacked a persisted authorization, PKCE/device, callback, refresh, revocation, and acceptance lifecycle.
- Self-hosted and vendor-cloud modes lacked an operational deployment milestone for PostgreSQL, workers, artifacts, vault/KMS, isolation, backup/restore, observability, and rollback.

### Codex/Hermes response
Accepted all 17 findings. `PLAN.md` now adds monotonic `WorkspaceAuthority` epochs and signed atomic handoff; queue-only remote-offline intents; a fenced centralized external-effect gateway with semantic idempotency, transactional outbox, current authorization/limits, and compensation; discriminated scopes and immutable audience snapshots; fully bound credential/OAuth records; authorization-aware idempotency; immutable outcome/lineage/audit contracts; normative autonomy/shadow effect rules; typed governed memory; complete V1 golden/quarantine/bootstrap work followed by per-domain importers; client-surface parity; TUF-style updates; an eleven-row capability implementation ledger; strict Worker A -> review -> Worker B -> review -> Worker C -> review -> Worker D sequencing; and a separate operational self-hosted/vendor-cloud deployment milestone.

### Remaining gate
Validate, commit, and hash the new plan-only revision, then rerun the same two independent read-only scopes against that exact commit. No remaining implementation begins while either verdict requires revision.
