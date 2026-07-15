# Corvus V2 — Security Review Checklist (Asif, OAI)

Use this per-milestone, before signing off as one of the required independent reviews.
Source of truth: `PLAN.md`. Evidence log: `PLAN-REVIEW-LOG.md`.

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
- [ ] VERIFIED (`305cbfb`): `SecretRedactor` rejects bare `Bearer`/`Basic`/`Digest`
      in event payloads; event validation rejects secret keys AND values
      (`security.py:68-69`, `domain/agent_runtime.py:727-730`)
- [ ] DEDICATED `tests/unit/test_security.py` for `corvus/security.py` core —
      OPEN follow-up (non-blocking); currently only `tests/security/test_structured_redaction.py`
      covers it directly

## Verification & Evidence
- [ ] Completion claims backed by actual evidence (logs, hashes, test output) — not just agent assertion
- [ ] Migration fixtures are byte-exact and reproducible, not approximate
- [ ] Delivery is atomic — no partial/corrupted state possible on interruption
- [ ] VERIFIED (`305cbfb`): `validate_agent_run_event_chain` recomputes every event
      digest + enforces sequence/run/handle/`previous_event_digest` chaining; tampered or
      out-of-order events rejected (`domain/agent_runtime.py:797-818`)
- [ ] VERIFIED: `TOOL_BLOCKED` after `TOOL_STARTED` rejected; authorization fail-closed on
      operation-field smuggling (`ports.py:199-231`)

## Review Process (gate integrity — lessons from this session)
- [ ] Two independent reviews reference the EXACT same frozen commit hash
- [ ] Reviewer is not the same person who implemented the milestone
- [ ] Findings are logged (not just verbally raised) before sign-off
- [ ] BEFORE reviewing: re-pull the PR head and confirm the commit hash. A stale-commit
      review is a real failure mode (agent reviewed `7d2ec2e`; fixes already landed at `305cbfb`)
- [ ] AFTER posting a review: verify it actually landed via
      `gh api repos/.../pulls/N/reviews` — a self-`--approve` may NOT persist
      (GitHub eligibility / dismissed). If it didn't land, post the verdict as a PR
      COMMENT (guaranteed) AND have the PR author confirm the formal approve.

## Replay / Idempotency (verified, `305cbfb`)
- [ ] `SimulatedAgentRuntime.start` keys idempotency on `(run_id, provider_binding_id)`;
      a retry with a different idempotency_key returns the SAME handle (`replayed=True`),
      never a second handle; a differing request fails the digest check (`simulated.py:125`)
- [ ] Event-chain proof holds within a single runtime AND must hold across devices once the
      cross-device/node sync surface opens (see THREAT_MODEL.md §8)

## Pre-Demo / Judge-Facing
- [ ] Security layer is visible in the demo, not just backend plumbing
- [ ] One clear, judge-understandable explanation of "fail-closed" and why it matters
- [ ] No security theater — every guardrail claimed in the pitch is actually enforced in code
- [ ] If the OAuth / cross-device sync surface (4 personas, local/cloud) opens:
      confirm (1) OAuth tokens not logged, (2) sync can't replay/forge agent-run events,
      (3) local-vs-cloud hosting doesn't weaken sandbox image pinning
