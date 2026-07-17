# Task 2.1 Report: Conversation Persistence

Date: 2026-07-17

## Outcome

Task 2.1 adds workspace-scoped durable persistence for threads, thread versions, attachment metadata, messages and attachment links, immutable agent-run records, hash-chained agent-run events, run artifacts, and artifact lineage. The implementation preserves the certified V1 `corvus/conversations.py`, `TraceStore`, and legacy `run_events`; the new stream is `agent_run_events`.

No provider discovery, provider execution, provider adapter, conversation API, SSE, web UI, binary blob store, retention worker, deployment, push, PR, or Task 2.2 work is included.

## Implemented Contracts

- Frozen, extra-forbid domain models with aware timestamps, bounded text and metadata, exact principal/agent/system author discrimination, SHA-256 bindings, recursive sensitive/noncanonical rejection, and stable validation reason codes.
- Manifest schema version 9 with deterministic ID `00000000-0000-4000-8000-000000000012` and nine in-root families: `threads`, `thread_versions`, `attachments`, `messages`, `message_attachments`, `agent_runs`, `agent_run_events`, `run_artifacts`, and `run_artifact_lineage`.
- Composite workspace foreign keys and exact version bindings for workspaces, memberships, projects, and agent identities; immutable triggers and required tenant/index/check coverage are classifier-enforced.
- Infrastructure-only repository mutations with current active-membership revalidation, SQLite `BEGIN IMMEDIATE`, PostgreSQL static row locks, `MAX(sequence)+1` allocation, exact replay, mismatch denial, bounded numeric pages, hash-chain validation, and deterministic artifact DAG locking.
- Application mutations that fail with `conversation_authority_lifecycle_unavailable` before writes unless an injected lifecycle binds request context, client surface, authorization snapshot, canonical request digest, prior/proposed authority roots, signed audit receipt, and finalized result digest.
- Whole-path downgrade preflight at the current head. Conversation, sync, OAuth/account-idempotency, identity history, and incompatible identity-workspace metadata are checked for every crossed protected revision before Alembic can remove a newer layer.

## TDD Evidence

The slice was developed red-first:

- Domain RED: collection failed with `ModuleNotFoundError: corvus.domain.conversations`; GREEN reached 27 domain tests.
- Repository RED: collection failed with `ModuleNotFoundError` for the conversation repository; GREEN covered transactionality, membership, replay, sequence allocation, pages, events, and artifacts.
- Migration RED: the expected `M2_CONVERSATIONS_REVISION` was absent; GREEN covered current classification, root coverage, tamper-to-PARTIAL, populated refusal, empty cycling, and PostgreSQL offline DDL.
- Service/security RED: the conversation application module was absent; GREEN covered fail-closed lifecycle behavior and non-enumerating tenant isolation.
- Additional genuine RED cases exposed duplicate terminal-start transitions, nested locator rejection, recreated wrong tenant indexes, and persisted event payload/previous-digest tampering. Each case was fixed and retained as a regression.
- Whole-path downgrade review restored strict pre-mutation atomicity. The four OAuth cases now prove identical before/after tables, triggers, protected row count, and exact head revision.

## Verification

Final functional evidence:

- `uv run --python 3.13 pytest -q`: **949 passed, 5 skipped** in 261.99 seconds.
- `uv run --python 3.13 pytest tests/integration/test_account_repository.py tests/integration/test_conversation_migration.py -q`: **43 passed**.
- OAuth whole-path downgrade focus: **4 passed** with exact schema/trigger/head preservation.
- The five skips are guarded PostgreSQL destructive tests requiring `postgres_reset_opt_in_required`: one conversation repository test, one database test, and three sync repository tests.

Final quality evidence:

- `uv run --python 3.13 ruff check .`: clean.
- `uv run --python 3.13 ruff format --check .`: 200 files formatted.
- `uv run --python 3.13 bandit -r corvus -q -ll`: clean.
- `uv lock --check`: clean.
- `git diff --check`: clean.
- Targeted mypy over every changed/new Task 2.1 source module: clean.

Full `uv run --python 3.13 mypy corvus` reports five baseline errors in files unchanged from base commit `72c860c1dd2d6e1281fe710b456957be9229145e`:

- `corvus/infrastructure/migrations/env.py:15`: optional URL `startswith` union error.
- `corvus/infrastructure/migrations/versions/m1_006_handoff_restore.py:138`: SQLAlchemy row-sequence assignment type.
- `corvus/infrastructure/migrations/versions/m1_007_identity_scope.py:131`: SQLAlchemy row-sequence assignment type.
- `corvus/infrastructure/migrations/versions/m1_008_non_circular_root_manifest.py:47`: SQLAlchemy row-sequence assignment type.
- `corvus/infrastructure/migrations/versions/m1_009_audit_external_proofs.py:47`: SQLAlchemy row-sequence assignment type.

Those five paths have no Task 2.1 diff and were not modified because they are certified prior migrations outside this task.

## Stop Boundary

Task 2.1 stops at domain, application lifecycle seams, repository persistence, migration/classifier/root integration, tests, and documentation. No push, pull request, deployment, Task 2.2, provider runtime, API/SSE, or UI work is performed in this task. Progression to Task 2.2 follows independent Task 2.1 approval.

## Independent Review Repair

The first independent Task 2.1 review returned two High findings. Both were reproduced red-first and repaired in a separate local commit:

- Authority transplant: five workspace-transplanted mutation cases, three thread-scope transplants, attachment/artifact unrelated-scope cases, owner/author/requester/snapshot mismatches, and an agent-author transplant all returned success before the repair. The security RED was **13 failed, 6 passed**.
- Event chain: paging after sequence 1 accepted a sequence-2 record whose predecessor and event digest were both recomputed, because only the returned slice was decoded. The repair validates every persisted record from genesis through the frozen high watermark before slicing.

The application boundary now returns the single non-enumerating `conversation_authority_binding_mismatch` before lifecycle or repository access when:

- any affected payload workspace differs from `RequestContext.workspace_id`;
- attachment owner differs from the requester or the request is not exactly workspace-scoped;
- a message is not exactly thread/conversation-scoped, a principal author/requester membership binding differs, or an agent author differs from `context.agent_id`;
- a run is not exactly thread/conversation-scoped, its requester differs, or its authorization snapshot ID/digest differs;
- an event is not exactly bound to the context workspace and thread/conversation scope; or
- an artifact is not exactly workspace-scoped. Producing run/event and parent lineage remain transactionally bound because `RequestContext` has no run scope and `RunArtifact` has no thread field.

Repository page reads now validate the complete frozen chain for contiguous sequence from 1, canonical genesis predecessor, event digest, predecessor linkage, stable handle/run identity, workspace/thread/run envelope, provider uniqueness, terminal transitions, and tool/effect state before returning the requested bounded slice.

Focused GREEN evidence after the repair:

- `tests/security/test_conversation_isolation.py`: **19 passed**.
- Complete conversation domain/repository/migration/security slice: **63 passed, 1 guarded PostgreSQL skip**.
- Final exact-tree `uv run --python 3.13 pytest -q`: **962 passed, 5 guarded PostgreSQL skips** in 332.34 seconds.
