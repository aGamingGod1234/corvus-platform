# Task 2.2 Report: Provider Registry and Bounded Process Sessions

Date: 2026-07-17

## Outcome

Task 2.2 adds one immutable, provider-neutral registry over the existing
`AgentRuntimePort` and one bounded, interruptible process-session primitive for
future local adapters. It does not add provider-specific commands, persistence,
API/SSE surfaces, UI, or durable process resurrection.

## What Was Implemented

- Frozen/orderable `(ProviderFamily, ProviderTransport)` adapter keys, frozen
  factories, duplicate-key rejection before construction, one-time adapter
  creation, and read-only adapter mappings.
- All-or-nothing deterministic discovery with strict candidate reconstruction,
  exact workspace/project/key binding, duplicate binding-ID refusal, stable
  non-reflective failures, and exact owner routing for every runtime operation.
- Fail-closed capability intersection: only two `SUPPORTED` declarations produce
  support; either `UNSUPPORTED` wins; every other combination is `UNVERIFIED`.
- Coordinator preflight reconstruction of candidate/capability/health models,
  exact query-scope validation, and exactly-one matching-binding enforcement.
- Frozen invocation, limit, and event contracts; immediate executable SHA-256
  revalidation; canonical cwd/root containment; link/reparse and shell rejection;
  direct argv spawning; and a rebuilt minimal child environment with derived
  `PATH` and only trusted OS variables plus explicit approved keys.
- Concurrent bounded stdout/stderr readers, strict UTF-8 and NDJSON parsing,
  duplicate-key/nonfinite/nonobject rejection, recursive pre-buffer redaction,
  terminal-only redacted stderr, bounded replay, stable cursor errors, and one
  reserved terminal-event slot.
- Confirmed whole-tree termination using POSIX process groups or canonical
  System32 `taskkill.exe /T /F`; taskkill failure is never reported as confirmed.
  Consumer cancellation shields and completes cleanup before propagating.
- Reusable safe-process environment, grouped-spawn, containment, and tree-kill
  helpers while preserving `run_trusted_argv` behavior.

## TDD Evidence

- Registry RED: missing `corvus.infrastructure.agent_runtimes.registry` during
  collection. GREEN: 9 focused tests passed.
- Process-session RED: missing
  `corvus.infrastructure.agent_runtimes.process_session` during collection.
  GREEN: 29 focused Windows tests passed in 13.50 seconds.
- Coordinator RED: ambiguous duplicate candidates were accepted and start
  returned `ok=True`. GREEN: the regression passed and all 109 coordinator tests
  passed.
- Shell-composition RED: a pinned `cmd.exe` invocation was accepted. GREEN:
  known shell executables are refused before spawn.
- Combined runtime/coordinator/safe-process suite: 177 tests passed.

## Verification

- Direct isolated process-session suite: **29 passed** in 13.50 seconds.
- Direct full suite excluding the process-session file: **972 passed, 5 skipped**
  in 312.66 seconds.
- Fresh direct bounded full suite: **1001 passed, 5 guarded PostgreSQL skips** in
  327.23 seconds, exit 0 under a 420-second hard timeout.
- The earlier context-mode-wrapped full run exceeded that wrapper's 300-second
  transport limit and left its subprocess detached. Process inspection showed no
  provider/session child, and direct bounded isolation reproduced no test or task
  leak. The detached process chain was terminated before the fresh direct run.
- Full Ruff check and format check: clean across 204 files before documentation.
- Targeted mypy: no issues in six Task 2.2 source files.
- Bandit `-r corvus -q -ll`: clean.
- `uv lock --check`: clean; no dependency changes.
- `git diff --check`: clean.

## Security Boundaries Preserved

- No PID, argv, environment, cwd, stdin, raw frame, raw exception, or unredacted
  stderr is exposed through process-session events.
- No parent environment merge, PATH lookup, shell invocation, or silent provider
  drop is permitted.
- Cwd containment is documented as containment only, not filesystem isolation.
- Executable digest verification is pinning immediately before spawn, not an
  atomic OS sandbox guarantee.
- Windows direct-kill fallback is cleanup only; it cannot establish confirmed
  tree termination.
- Existing authority, audit, approval, budget, idempotency, credential, sandbox,
  redaction, Task 2.1 persistence, and V1 event invariants remain unchanged.

## Deferred by Explicit Stop Boundary

- Provider-specific local CLI commands, parsers, and continuation semantics are
  Task 2.3.
- HTTP/API adapters, persistent runs, conversation APIs, resumable SSE, UI,
  durable process resurrection, push, PR, deployment, and production changes are
  not part of Task 2.2.
