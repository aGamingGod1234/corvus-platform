# Milestone 0.5 Review-Blocker Repair Plan

## Scope and safety boundary

Repair only the five blockers reported against commit `153d94dc300c4282a5de86620aa5238d30aff844`:

1. Persist and use the Milestone 0.5 context firewall on every current model-call path.
2. Freeze executable V1 CLI behavior, not only Typer/Pydantic metadata.
3. Replace candidate-generated quarantine data with a committed immutable V1 fixture corpus.
4. Bind quarantine deduplication and receipts to the exact source database bytes.
5. Restore default isolated-build usability with a supported digest-pinned production image.

Do not add Milestone 1 authority/domain schemas, FastAPI, React, Tauri, channels, connectors, live-provider calls, host execution fallback, or unrelated refactors. Milestone 1 remains blocked until two independent read-only reviewers return `VERDICT: PASS` for the same frozen commit.

## Acceptance criteria

### A. M005-001 context provenance

- The current schema advances from version 1 to version 2 through named migration `M005-001`.
- New databases contain append-only `external_contents` and `context_envelopes` tables plus update/delete rejection triggers.
- A stamped schema-v1 database is migrated transactionally to schema v2 only after an integrity-checked, SHA-256-sealed backup is durable; an unstamped V1 database still requires the existing explicit backup/stamp path.
- `ContextEnvelope` owns typed `legacy_run` provenance for current V1 calls; Milestone 1 `request_context` ownership is not introduced early.
- `InteractiveAgent` and `AgentOrchestrator`, including delegation planning and direct bounded-subagent calls, construct requests from `ContextEnvelope`; untrusted history, user, model, tool, and subagent content is emitted only as user-role data.
- No subagent/model output is promoted to a system message.
- Input provenance is committed before each provider call. Model-returned content is persisted as untrusted external content after collection. Restart preserves readable provenance.
- External content cannot create tools, permissions, secret access, or autonomy fields in the trusted channel.

### B. Executable V1 command golden

- `tests/contract/test_v1_public_golden.py` invokes every public command path at least via `--help` and executes deterministic behavior scenarios for root/version, `chat --json`, `trace --json`, `doctor --json`, `review --json`, approved apply plus `undo`, `eval --json`, model configuration/status/failure paths, memory add/list/edit/pin/export/delete, and skill draft/promote/list/rollback.
- Tests use isolated `CORVUS_HOME`, controlled fakes only for external OS/network/keyring/TUI boundaries, and the real command handlers/stores/managers for command semantics.
- Dynamic UUID/time/path/hash fields are normalized by type without deleting envelope keys, exit codes, event order, or output structure.
- The executable result map is stored in the immutable hashed V1 public-contract fixture. A changed exit code, JSON envelope, event sequence, or retained command output fails the golden test.

### C. Immutable V1 domain fixture and quarantine

- `tests/fixtures/v1/legacy/` contains committed source bytes for:
  - an unstamped four-table V1 SQLite database populated with memory, skill, run-event/conversation, and delivery rows;
  - user config, onboarding, provider metadata/keyring reference, and policy;
  - project `.corvus/policy.yaml` with autonomy;
  - bundle, artifact, and backup files.
- `tests/fixtures/v1/manifest.json` hashes every committed fixture file. Tests verify this manifest before use and copy source bytes to temporary paths; they never call current `Base.metadata.create_all()` to synthesize legacy evidence.
- Quarantine capture remains redacted, bounded, source-readable, sealed, and idempotent for identical bytes.
- `capture_id` is derived from both the canonical redacted-record digest and a complete raw-source snapshot digest. The raw-source digest covers the SQLite backup plus path/size/byte hashes for every file under the config, artifact, bundle, and backup roots, including files such as `.env` that are intentionally excluded from persisted redacted records.
- Verification recomputes the aggregate source digest from sealed per-domain component digests, recomputes capture identity, and validates the manifest source hash without persisting raw secrets.
- Any two byte-distinct source snapshots whose sanitized records are identical produce different capture IDs. A returned receipt seal always equals the on-disk manifest seal.

### D. Supported pinned sandbox default

- The production default is `docker.io/library/python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf`, verified from the Docker Registry OCI index on 2026-07-13.
- A healthy fake Docker or Podman route resolves with that digest without requiring `CORVUS_SANDBOX_IMAGE`.
- `CORVUS_SANDBOX_IMAGE` remains an explicit documented override and production validation still rejects mutable references.
- Docker/Podman absence or invalid image selection remains chat-only/no-host-fallback.

## Ordered RED -> GREEN slices

### Slice 1 — migration and persisted context boundary

1. RED: extend `tests/security/test_context_firewall.py` and `tests/integration/test_database_bootstrap.py` with:
   - hostile history/subagent/model output never appearing as system-role content;
   - pre-call persisted `legacy_run` envelope and post-call untrusted model content surviving restart;
   - `M005-001` schema-v1 -> v2 migration with sealed backup;
   - update/delete attempts against provenance tables rejected;
   - crash/invalid partial migration classification remains fail closed.
2. Run:
   - `env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 pytest tests/security/test_context_firewall.py tests/integration/test_database_bootstrap.py -q`
3. GREEN: minimally modify `corvus/context.py`, `corvus/store.py`, `corvus/database.py`, `corvus/interactive.py`, `corvus/orchestration.py`, `corvus/chat_agent.py`, and `corvus/cli.py`.
4. Re-run the focused command and `tests/integration/test_trace_store.py`.
5. Rollback point: revert only Slice 1 files if the migration cannot prove atomic backup and append-only behavior.

### Slice 2 — executable V1 public goldens

1. RED: add executable scenario collection to `tests/contract/test_v1_public_golden.py`; the old fixture must fail because `command_executions` is absent.
2. Run:
   - `env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 pytest tests/contract/test_v1_public_golden.py -q`
3. GREEN: update only deterministic test harness/normalization plus `tests/fixtures/v1/public_contract.json` and its manifest hash. Production behavior changes are forbidden unless the executable golden exposes a real compatibility defect.
4. Re-run focused contract and CLI smoke tests.
5. Rollback point: preserve the previous fixture and revert this slice if normalization masks exit/envelope differences.

### Slice 3 — frozen V1 domain corpus and source-bound quarantine

1. RED: rewrite `tests/integration/test_v1_quarantine_capture.py` to verify/copy committed fixtures and add alias/seal mismatch regressions. It must fail while fixtures are absent and capture IDs use only redacted records.
2. Run:
   - `env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 pytest tests/integration/test_v1_quarantine_capture.py -q`
3. GREEN: add immutable fixture bytes/manifest and minimally change `corvus/quarantine.py` identity and verification logic.
4. Re-run quarantine plus database-bootstrap tests.
5. Rollback point: revert Slice 3 if any test writes the source fixture or a receipt differs from its stored manifest.

### Slice 4 — digest-pinned default image

1. RED: extend `tests/security/test_sandbox_options.py` so healthy default Docker/Podman resolution is usable and pinned without an environment override; preserve mutable-reference rejection and no-host-fallback cases.
2. Run:
   - `env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 pytest tests/security/test_sandbox_options.py -q`
3. GREEN: add one default-image constant in `corvus/cli.py`, return it from configuration when no override exists, and document the default/override in `README.md`.
4. Re-run focused sandbox and CLI smoke tests.
5. Rollback point: revert Slice 4 if default validation or fake-engine routing is not deterministic.

## File map

- Production: `corvus/context.py`, `corvus/database.py`, `corvus/store.py`, `corvus/interactive.py`, `corvus/orchestration.py`, `corvus/chat_agent.py`, `corvus/cli.py`, `corvus/quarantine.py`, `README.md`.
- Tests: `tests/security/test_context_firewall.py`, `tests/security/test_sandbox_options.py`, `tests/integration/test_database_bootstrap.py`, `tests/integration/test_v1_quarantine_capture.py`, `tests/contract/test_v1_public_golden.py`, and only narrowly needed helper modules under `tests/`.
- Fixtures: `tests/fixtures/v1/public_contract.json`, `tests/fixtures/v1/manifest.json`, `tests/fixtures/v1/legacy/**`.
- Evidence log: append final gate/review results to `PLAN-REVIEW-LOG.md` only after exact-byte verification.

## Worker and integration order

- Worker A (this agent, sequential): Slices 1 and 2.
- Worker B (this agent, sequential after A): Slices 3 and 4.
- No local heavy workers run concurrently. Independent reviewers are read-only and may run as a two-agent fan-out only after bytes are frozen.
- Integration order is fixed: Slice 1 -> Slice 2 -> Slice 3 -> Slice 4 -> full gate -> freeze -> paired review.
- One commit per tightly coupled slice is allowed, but each reviewer must inspect the final aggregate commit. Any post-freeze byte change invalidates both approvals.

## Final exact-byte gate

Run serially with `PYTHONHOME` and `PYTHONPATH` cleared:

1. `uv sync --all-groups --locked`
2. `uv run --python 3.12 pytest tests/security --junitxml=.pytest-tmp/m005-security.xml`
3. `uv run --python 3.12 pytest --junitxml=.pytest-tmp/m005-full.xml`
4. `uv run --python 3.12 ruff check .`
5. `uv run --python 3.12 ruff format --check .`
6. `uv run --python 3.12 python -m compileall -q corvus`
7. `uv run --python 3.12 corvus --help`
8. isolated-home `uv run --python 3.12 corvus doctor --json`
9. `uv run --python 3.12 mypy corvus --no-error-summary`; compare normalized signatures to baseline `73638e1829a1f59a1a5a10dc4464069f6c7f47d6`, permitting zero new signatures.
10. `uv run --python 3.12 bandit -r corvus -f json`; compare normalized issue signatures to the same baseline, permitting zero new signatures.
11. `uv run --python 3.12 pip-audit` (record environmental/index blockers honestly; do not fabricate a pass).
12. Verify fixture-manifest hashes, migration backup hashes, quarantine seals, executable golden hashes, `git diff --check`, no unstaged/staged mismatch, and added-line secret/dangerous-pattern scans.
13. Record `git rev-parse HEAD`, tree hash, final diff hash, fixture-manifest hash, exact test counts, and all static-analysis deltas.

## Risks and mitigations

- **Migration corrupts a V1 database:** integrity-check source, create/fsync/verify SHA-256 backup first, run one SQLite transaction, classify final bytes, and test injected/partial states fail closed.
- **Append-only provenance becomes mutable:** database triggers reject update/delete; application exposes append/read methods only.
- **Prompt role regression:** inspect captured `ModelRequest` objects in hostile fixtures; assert every external item is user-role data.
- **Golden tests become over-normalized:** normalize dynamic values only; preserve command path, exit code, stdout/stderr structure, JSON keys/types, and ordered events.
- **Fixture accidentally follows candidate metadata:** create once from explicit frozen SQL/bytes, hash every file, and prohibit test-time generation.
- **Quarantine leaks secrets while binding bytes:** store only SHA-256 for raw sources; retain redacted canonical records.
- **Pinned image ages:** digest remains immutable; update only through a reviewed fixture/test change. Never fall back to a mutable tag or host process.

## Freeze and re-review gate

1. Finish all final-byte checks on a clean working tree except intentional accepted commits.
2. Commit the aggregate candidate and record exact commit/tree/diff/fixture hashes.
3. Dispatch two independent read-only reviewers against that exact commit:
   - security/migration/context/quarantine/sandbox review;
   - product/topology/V1 executable compatibility review.
4. Acceptance requires two completed `VERDICT: PASS` reports naming the same commit and tree. Timeout, partial output, `REVISE`, or a byte change blocks Milestone 1 and restarts the fix -> full-gate -> freeze -> paired-review cycle.
