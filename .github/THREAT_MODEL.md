# Corvus V2 — Security Threat Model (Asif, OAI)

Scope: threats specific to Corvus's architecture — sandboxed AI-driven code execution,
credential handling, multi-surface delivery (web / desktop / cloud), and the
proof-carrying-completion verification layer. Updated as repo access reveals more.

> Source of truth for the security spec: [PLAN.md](../PLAN.md). Existing reviewer evidence:
> [PLAN-REVIEW-LOG.md](../PLAN-REVIEW-LOG.md). Read those before re-deriving anything below.

---

## 1. Sandbox Escape / Host Contamination

**Risk:** AI-directed builds run inside isolated containers (Docker/Podman). If
isolation fails or falls back to host execution, arbitrary AI-generated code runs unsandboxed.
**Mitigation (README/PLAN):** Fail-closed — if Docker/Podman unavailable, isolated
builds do NOT fall back to host execution; only ordinary chat remains.
**Open questions:**
- What exactly triggers "ordinary chat" mode vs. full lockout?
- Is fail-closed behavior tested under failure injection (not just happy path)?
  → See `tests/security/test_sandbox_options.py` — verify it asserts the lockout,
    not merely that the happy path builds.

## 2. Supply Chain / Image Tampering

**Risk:** A compromised or mutable base image injects malicious behavior into every sandboxed build.
**Mitigation:** Production builds require digest-pinned images (`sha256:…`); tag-only
overrides rejected before container start.
**Open questions:**
- Who controls/rotates the pinned digest, and how is a new digest vetted before default?
- Is there enforcement preventing non-production/dev mode from being used in a prod deploy by mistake?

## 3. Credential Exposure

**Risk:** Corvus handles user-provided local endpoints, API credentials, and OAuth
(e.g. Codex/ChatGPT). Leaked or logged credentials = critical failure.
**Mitigation:** Credentials via OS keyring or scoped cloud vault; explicit rule against
plaintext secrets in runtime config or sandboxes.
**Current branch status:**
- `SecretRedactor` redacts registered values, sensitive mapping keys, assigned
  api_key/token/secret/password values, and recognized sk-/GitHub token forms.
- It does not generically detect bare `Bearer`/`Basic`/`Digest` strings under
  benign keys. Existing Authorization-key tests do not prove that behavior.
- Agent-run secret key/value validation is not present on this branch. These
  controls remain open until their implementation and focused tests are present
  on the reviewed commit.
- On this branch, `tests/security/test_structured_redaction.py` directly exercises
  the redaction core. PR #1 adds the dedicated `tests/unit/test_security.py`
  coverage tracked as an open follow-up in the guardrail checklist.
**Open questions:**
- Are provider outputs/logs redacted before storage?
- Sandbox boundary: can a sandboxed build process ever read keyring/vault-resolved
  secrets directly, or only via a mediated call?

## 4. Untrusted AI Output / Prompt Injection

**Risk:** Corvus delegates to coding/testing/security/UX agents based on AI-generated
plans. Manipulated input (user prompt or untrusted delegated agent) could produce
unsafe actions framed as "verified."
**Mitigation:** "Trusted verification" (Milestone 0.5); proof-carrying completion —
can't claim done without checks passing.
**Open questions:**
- Does verification check *what actually happened* (sandboxed diff, logs) or just that
  an agent *claims* it happened?
- Are verification agents themselves protected from the same untrusted input?

## 5. Migration / State Integrity

**Risk:** Byte-exact migration fixtures suggest state transitions (V1→V2, milestone→milestone)
are sensitive to corruption or tampering.
**Mitigation:** Byte-exact migration fixtures, sealed quarantine capture, atomic delivery.
**Open questions:**
- What happens on partial/interrupted delivery — atomicity at filesystem or app level?
- Is "sealed quarantine capture" reviewed by more than one person, or automated only?

## 6. Review Gate Integrity

**Risk:** Milestone 0.5+ requires two independent exact-commit reviews before proceeding.
If the review process is gameable (self-review, stale commit reference), the gate is theater.
**Verified-in-practice (this session):**
- **Stale-commit review is a real failure mode.** Lucas's agent reviewed `7d2ec2e`;
  at the later reviewed head most flagged issues were already fixed. Always re-pull
  the PR head and confirm the commit hash before reviewing.
- **Self-approve may not persist.** A `gh pr review --approve` by the security owner
  did not land on PR #1 (GitHub eligibility / dismissed). Fix: an eligible reviewer
  must successfully submit a formal approval review. A PR comment may preserve the
  verdict as evidence, but it does not satisfy branch protection. Verify the approval
  exists via `gh api .../pulls/N/reviews` before declaring done.
- Both reviews must reference the exact same frozen commit hash.
**Open questions:**
- Who are the two reviewers in practice, and is Asif one of them?
- Is there a check that both reviews reference the same frozen commit hash?

## 7. Replay / Idempotency & Event-Chain Proof

**Risk:** A client retries an agent-run start with a different idempotency key or
forges event-chain entries to replay/escalate actions.
**Current branch status:** the agent-run runtime, event-chain validator, and
operation-binding contracts are not present on this branch and are therefore not
verified here. Existing project-create and MVP idempotency/replay tests cover
separate code paths; they do not establish agent-run same-handle replay,
event-chain proof, or operation-field fail-closed behavior. Keep these mitigations
open until the runtime implementation and focused tests are present on the
reviewed commit.

## 8. OAuth / Cross-Device & Node Sync Surface (TRACKED FUTURE — not yet opened)

**Context (Lucas, milestones 1–11 done):** 4 UI personas (Everyday/Professional ×
Individual/Team), local-or-cloud hosting, cross-device + node + webapp sync via
Google OAuth, main node for sharing/syncing. This is a NEW auth boundary.
**Risks to confirm before demo freeze (when Lucas's agent opens it):**
1. OAuth tokens must not be redacted-through or logged.
2. Node sync must not replay/forge agent-run events — the event-chain proof
   (`§7`) must hold across devices, not just within one runtime.
3. "Host locally vs cloud" must not weaken the sandbox image pinning (`§2`).
**Action:** when the sync surface PR opens, run the
[GUARDRAIL_CHECKLIST.md](GUARDRAIL_CHECKLIST.md) §Credentials and §Verification
items against it specifically.

---

## Priority for Asif (near-term)
1. Read [PLAN.md](../PLAN.md) (authoritative spec) +
   [PLAN-REVIEW-LOG.md](../PLAN-REVIEW-LOG.md) (reviewer evidence).
2. Verify fail-closed sandbox behavior is *tested*, not just documented.
3. Confirm credential/log redaction scope before the web/desktop/cloud surfaces open.
4. Keep `§7`/`§8` in sync as the sync surface and any replay fixes land.
