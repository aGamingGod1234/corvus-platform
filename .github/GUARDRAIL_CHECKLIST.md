# Corvus V2 — Security Review Checklist (Asif, OAI)

Use this per-milestone, before signing off as one of the required independent reviews.
Source of truth: [PLAN.md](../PLAN.md). Evidence log:
[PLAN-REVIEW-LOG.md](../PLAN-REVIEW-LOG.md).

## Sandbox & Execution
- [ ] Build only runs inside pinned, digest-verified image — no tag-only fallback
- [ ] No host-execution fallback path exists if Docker/Podman unavailable
      (verify `tests/security/test_sandbox_options.py` asserts the LOCKOUT, not just happy path)
- [ ] Sandbox boundary confirmed: sandboxed process cannot read host secrets/env
      beyond what's explicitly passed in

## Credentials & Secrets
- [ ] No plaintext secrets in runtime config, logs, or sandbox environment
- [ ] Credentials resolved only via OS keyring / scoped cloud vault at point of use
- [ ] Provider output redaction confirmed — no leaked tokens/keys in logs, screenshots,
      or delivered evidence
- [ ] CURRENT BRANCH STATUS: `SecretRedactor` redacts registered values, sensitive
      mapping keys, assigned api_key/token/secret/password values, and recognized
      sk-/GitHub token forms. It does not generically detect bare
      `Bearer`/`Basic`/`Digest` strings under benign keys. Keep this item open until
      explicit patterns and benign-key regressions land.
- [ ] DEDICATED `tests/unit/test_security.py` for `corvus/security.py` core —
      OPEN follow-up (non-blocking); currently only `tests/security/test_structured_redaction.py`
      covers it directly

## Verification & Evidence
- [ ] Completion claims backed by actual evidence (logs, hashes, test output) — not just agent assertion
- [ ] Migration fixtures are byte-exact and reproducible, not approximate
- [ ] Delivery is atomic — no partial/corrupted state possible on interruption
- [ ] CURRENT BRANCH STATUS: the agent-run event-chain validator and operation-binding
      contracts are not present on this branch and are not verified here. Existing
      project-create and MVP replay tests cover separate paths. Keep this item open
      until the runtime implementation and focused tests are present on the reviewed commit.

## Review Process (gate integrity — lessons from this session)
- [ ] Two independent reviews reference the EXACT same frozen commit hash
- [ ] Reviewer is not the same person who implemented the milestone
- [ ] Findings are logged (not just verbally raised) before sign-off
- [ ] BEFORE reviewing: re-pull the PR head and confirm the commit hash. A stale-commit
      review is a real failure mode; never treat an earlier reviewed commit as the current head
- [ ] AFTER posting a review: verify it actually landed via
      `gh api repos/.../pulls/N/reviews` — a self-`--approve` may NOT persist
      (GitHub eligibility / dismissed). If it did not land, an eligible reviewer
      must successfully submit a formal approval review; a PR comment is evidence
      only and does not satisfy branch protection.

## Replay / Idempotency
- [ ] CURRENT BRANCH STATUS: the agent-run runtime and its same-handle replay contract
      are not present on this branch. Existing project-create and MVP idempotency tests
      do not establish agent-run replay behavior. Keep this item open until the runtime
      implementation and focused tests are present on the reviewed commit.
- [ ] Event-chain proof holds within a single runtime AND must hold across devices once the
      cross-device/node sync surface opens (see [THREAT_MODEL.md](THREAT_MODEL.md) §8)

## Pre-Demo / Judge-Facing
- [ ] Security layer is visible in the demo, not just backend plumbing
- [ ] One clear, judge-understandable explanation of "fail-closed" and why it matters
- [ ] No security theater — every guardrail claimed in the pitch is actually enforced in code
- [ ] If the OAuth / cross-device sync surface (4 personas, local/cloud) opens:
      confirm (1) OAuth tokens not logged, (2) sync can't replay/forge agent-run events,
      (3) local-vs-cloud hosting doesn't weaken sandbox image pinning
