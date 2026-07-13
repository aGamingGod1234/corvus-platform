# Corvus Milestone 0 / 0.5 Execution Plan

## Authority

- Approved product plan: `PLAN.md` at commit `a2c233412241d0b21b3c85aacfd25c549e8dda26`.
- Scope: pending Milestone 0 V1 capture/bootstrap/quarantine work and Milestone 0.5 release-blocking safety hardening only.
- Baseline: Python 3.12; 14 tests pass and one Windows symlink test is expected to skip; Ruff passes; no Docker/Podman engine is available.
- Resource rule: work serially because the Mini PC had about 4.6 GB free RAM during preflight. Do not run Node, Rust, containers, or concurrent heavy workers.

## Refined specification

Preserve current V1 CLI and data readability while introducing explicit, fail-closed safety boundaries before any V2 authority or client code:

1. Freeze deterministic public-command, JSON, configuration and SQLite-domain fixtures with canonical SHA-256 manifests.
2. Replace implicit SQLAlchemy `create_all()` startup with one version-aware bootstrap that classifies a database before mutation: new, unstamped legacy, current, partial, or incompatible.
3. Require explicit backup and stamp/upgrade for a complete unstamped V1 database; partial or incompatible databases remain untouched and fail with recovery guidance.
4. Capture V1 records/configuration into an immutable canonical quarantine keyed by source digest. Repeating capture is a no-op and never converts records into future V2 domains.
5. Enforce snapshot exclusions, path/link/reparse denial, file/count/byte limits, cleanup, append-only external-content provenance, instruction/data separation, recursive secret redaction and bounded model/test output.
6. Select required verification from trusted repository/server policy. Model commands are optional additions. Run smoke checks; every repair starts from the approved source snapshot in a fresh attempt directory; package exactly the passing attempt.
7. Rehash every bundle artifact immediately before apply; bind/consume actor approvals once; lock bundle and destination; persist and flush rollback intent before mutation; recover or fail closed at every injected crash boundary.
8. Reject unsafe provider URLs by deployment context, allowlist child-process environment variables, strictly validate artifact digests, narrow optional budgets with `min`, require digest-pinned production sandbox images and enforce complete resource bounds.
9. Finish with the full local gate and an independent read-only Milestone 0.5 security review. No claim of container integration without a runtime.

## Non-goals

- No Milestone 1 authority, identity, scope, project repository or audit-root implementation.
- No CLI V2, FastAPI, React, desktop, channels, connector, cloud or distribution work.
- No provider credential migration or keyring extraction.
- No host-execution fallback when Docker/Podman is absent.
- No broad refactor of retained chat/TUI/provider behavior.

## Acceptance criteria

### V1 freeze and bootstrap

- Current `--help`, `doctor --json`, safe public help/JSON envelopes and four-table V1 schema have canonical fixtures and a committed manifest.
- A missing/empty DB initializes and stamps exactly once.
- A complete unstamped V1 DB is detected without mutation; explicit backup plus stamp/upgrade is required.
- A current DB opens without DDL or stamp changes.
- Missing known tables, unexpected partial metadata, unsupported versions, or failed integrity checks do not mutate source state.
- Backup/restore paths carry verified SHA-256 sidecars.
- Quarantine capture canonicalizes domain rows/config references, excludes credentials, writes a sealed manifest atomically, and returns the same capture on a second run.

### Milestone 0.5

- Secret/cache/dependency/default-denied paths never enter model snapshots; approved includes cannot override secret/link/resource limits.
- External, repository, user and model-returned content carries immutable provenance and remains untrusted data; content cannot create tool, secret, permission or autonomy grants.
- Nested mappings/sequences and registered plaintext/base64/hex secrets redact before serialization/persistence.
- Repair context and provider/test output are redacted and bounded.
- Required checks cannot be replaced by model-declared trivial commands; smoke checks run.
- Each repair attempt uses a fresh source snapshot; stale prior-attempt files cannot affect verification or packaging.
- Delivery detects manifest/artifact/bundle tampering, approval replay/expiry/mismatch, concurrent apply and every injected crash boundary without unauthorized or unjournaled mutation.
- Provider URL, child environment, digest, optional-token and sandbox-image/resource tests fail closed.
- Adversarial suite, full suite, Ruff, mypy, Bandit, compile, CLI/doctor, SQLite integrity, secret scan and Git checks pass or limitations are documented exactly.

## Minimal file map

### Bootstrap/capture slice

- New: `corvus/database.py` — schema version, state classifier, explicit initialize/backup/stamp/restore operations.
- New: `corvus/quarantine.py` — canonical content-addressed V1 capture and manifest verification.
- Modify: `corvus/store.py` — call version-aware bootstrap; strict artifact digest validation; no unconditional `create_all()`.
- Modify only if required: `corvus/cli.py` — additive read-only DB status and explicit backup/stamp/capture commands; preserve all existing commands.
- New: `tests/contract/test_v1_public_golden.py` and canonical fixtures under `tests/fixtures/v1/`.
- New: `tests/integration/test_database_bootstrap.py`.
- New: `tests/integration/test_v1_quarantine_capture.py`.

### Snapshot/context/verification slice

- New: `corvus/context.py` — `ExternalContent`, `ContextEnvelope`, trust/provenance validation.
- New: `corvus/snapshot.py` — immutable `SnapshotPolicy`, bounded copy and cleanup.
- Modify: `corvus/security.py` — recursive redaction, bounded text/serialization helpers.
- Modify: `corvus/workflow.py` — policy snapshot, envelope use, fresh attempt trees, trusted verification selection and exact passing-tree package.
- Modify: `corvus/verification.py` — trusted required commands, smoke evidence, redacted output caps.
- New tests: `test_snapshot_policy.py`, `test_context_firewall.py`, `test_secret_flow.py`, `test_workflow_repair_isolation.py`, `test_verification_trust.py`, `test_structured_redaction.py`.

### Delivery/server-boundary slice

- Modify: `corvus/delivery.py` — artifact rehash, durable actor-bound approval repository, one-time consumption, locks, fsynced rollback intent and crash recovery.
- Modify: `corvus/models.py` only for minimal approval actor/nonce state and strict digest validators.
- Modify: `corvus/providers.py` / provider validation helper — deployment-aware URL rules and redirect-safe checks.
- Modify: `corvus/codex_cli.py` — explicit environment allowlist.
- Modify: `corvus/config.py` — optional token budgets narrow with `min` semantics.
- Modify: `corvus/sandbox.py` — production digest pin requirement and source/archive/output/workflow bounds.
- Extend/add the exact Task 0.5/0.6 tests named in `PLAN.md`.

## Vertical TDD sequence

Each item is RED → expected reason → minimal GREEN → focused/full test. Never batch all tests before implementation.

1. **Bootstrap classify new/current**
   - RED: `test_new_database_initializes_and_stamps`; missing bootstrap API.
   - GREEN: classifier + atomic metadata table creation for new DB only.
   - Run focused test then full baseline.
2. **Legacy/partial/incompatible no-mutation**
   - RED one state at a time; current `create_all()` mutates silently.
   - GREEN classification and explicit exception/state result before DDL.
3. **Explicit backup/stamp and restore proof**
   - RED: unstamped open refuses; backup digest/explicit stamp absent.
   - GREEN: integrity-checked SQLite backup, sidecar, atomic stamp transaction.
4. **Idempotent quarantine capture**
   - RED: no canonical capture; second run duplicates.
   - GREEN: sorted records/config metadata, digest-addressed directory, atomic manifest, verify API.
5. **Golden fixtures**
   - RED: current CLI/schema differs from frozen manifest when intentionally perturbed.
   - GREEN: deterministic fixture capture and assertion helpers; commit static fixtures, not dynamic rewrites.
6. **Snapshot exclusions and limits**
   - RED one exclusion/link/count/byte/cleanup behavior at a time; broad `_snapshot` copies it.
   - GREEN: `SnapshotPolicy` and bounded copier; workflow delegates to it.
7. **Context provenance/firewall**
   - RED: unlabelled/model content can be inserted as ordinary instruction.
   - GREEN: typed external content/envelopes; only trusted system instructions occupy instruction channel.
8. **Recursive redaction/output bounds**
   - RED nested secret and registered encodings survive serialization; long output persists.
   - GREEN recursive redactor + cap marker/digest; wire before JSON/event/evidence/model repair context.
9. **Fresh repair attempts**
   - RED stale file survives second candidate.
   - GREEN immutable approved snapshot plus new attempt directory for each candidate; delete plaintext attempts in `finally`.
10. **Trusted required verification + smoke + exact package**
    - RED trivial model command reports success; smoke omitted; stale tree packaged.
    - GREEN repository policy selects required/smoke commands; model commands supplemental; package hash equals passing attempt.
11. **Delivery tamper and approval replay**
    - RED altered staged file applies; same approval applies twice.
    - GREEN rehash all artifact entries and manifest immediately before lock/claim; durable actor-bound single-use approval state.
12. **Delivery atomicity/crash recovery/concurrency**
    - RED each injected boundary leaves ambiguous mutation or second apply enters.
    - GREEN canonical bundle/destination locks, fsynced intent before writes, per-file journal before/after, deterministic recovery.
13. **Provider URL, child env, digest, narrowing**
    - RED internal/credential URL accepted for cloud, environment leak, malformed digest lookup, optional budget widening.
    - GREEN centralized validators, explicit environment allowlist, canonical SHA-256 check, min-of-present optional limits.
14. **Sandbox pin/resource bounds**
    - RED production mutable tag accepted; oversized archive/output/commands accepted.
    - GREEN production profile requires `image@sha256:<64hex>`; validate all positive caps and enforce them before allocation/dispatch.
15. **M005-001 persistence**
    - RED provenance envelope cannot survive/replay from current DB.
    - GREEN append-only rows/migration through versioned bootstrap; imported trust capped at `untrusted`.

## Serial worker assignments

1. **Bootstrap worker:** `database.py`, `quarantine.py`, `store.py`, bootstrap/quarantine/golden tests and fixtures. No security/workflow/delivery edits.
2. **Snapshot/context worker:** `snapshot.py`, `context.py`, `security.py`, `workflow.py`, `verification.py`, corresponding tests. Starts only after bootstrap is green.
3. **Boundary worker:** `delivery.py`, minimal `models.py`, `providers.py`, `codex_cli.py`, `config.py`, `sandbox.py`, corresponding tests. Starts only after snapshot/context is green.
4. **Parent Hermes integration:** inspect diffs, run every focused/full gate, resolve only test-proven defects, verify no Milestone 1/client files.
5. **Independent reviewer:** read-only security/migration checkpoint after all local gates pass. A `REVISE` blocks Milestone 1.

## Verification commands

Run serially from repository root:

```bash
rm -rf .pytest-tmp .pytest-cache
uv sync --all-groups --locked --python 3.12
env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 pytest -q
env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 ruff check .
env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 ruff format --check .
env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 mypy corvus
env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 bandit -r corvus -q
env -u PYTHONHOME -u PYTHONPATH uv run --python 3.12 python -m compileall -q corvus
```

Use an isolated `CORVUS_HOME` for:

```bash
corvus --help
corvus doctor --json
```

Then SQLite integrity/version/capture verification, project source credential-signature scan, `git diff --check`, changed-file scope review, and clean-tree check. Run `pip-audit` only after `uv sync --locked`; report ecosystem advisories separately from source defects. Docker/Podman tests stay marked/skipped if no engine exists.

## Risks and mitigations

- **Silent legacy mutation:** classify with raw SQLite inspection before SQLAlchemy metadata creation; tests compare file hash/mtime before and after refusal.
- **Partial DDL after crash:** one transaction where SQLite permits; explicit prepared/current stamp and startup refusal otherwise.
- **Capture leaks credentials:** allowlisted config fields, keyring references only, recursive redaction, secret fixture canaries.
- **Fixture brittleness:** canonicalize paths/timestamps/UUIDs; static manifest changes require explicit review.
- **Repair contamination:** new directory from immutable source each attempt; never overlay prior candidate.
- **Approval race:** unique durable consumption + OS/database lock + transaction; in-memory sets do not count.
- **Crash injection breaks user tree:** journal intent and encrypted backup fsync before mutation; recovery tests at each boundary.
- **Windows link semantics:** test reparse handling directly; keep symlink test as an honest host skip where privilege blocks creation.
- **Sandbox engine absent:** unit-test options/pinning/bounds; no production secure-execution claim.

## Rollback

- Preserve baseline commit `a2c2334` and V1 source manifest.
- Commit each verified slice separately.
- Bootstrap changes never rewrite an unstamped/partial/incompatible DB. Restore only from a digest-verified backup.
- Revert the current slice commit if full baseline regresses; do not mix later-slice fixes into an unreviewed bootstrap commit.
- Quarantine captures are append-only/content-addressed; rollback code, not captured evidence.

## Checkpoints and reporting

- Checkpoint A: bootstrap/golden/quarantine focused + full tests green; immutable fixture manifest recorded.
- Checkpoint B: snapshot/context/verification focused + full tests green; plaintext staging cleanup proven.
- Checkpoint C: delivery/server-boundary focused + full tests green; crash/race evidence recorded.
- Checkpoint D: full quality/security gate green with environment limitations listed.
- Checkpoint E: independent exact-commit reviewer returns `PASS`; only then may Milestone 1 Task 1.1 begin.
- Report at each checkpoint with counts, changed files, commit, tests and blocker—not generic progress.
