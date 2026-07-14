# Corvus Persona and Team Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Corvus operator console into one desktop product with genuinely tailored Everyday/Developer and Personal/Team workspaces, backed by real collaboration capabilities rather than cosmetic mode changes.

**Architecture:** Keep one authoritative Python domain/application core and one React client loaded by the existing Tauri shell. Model the product on two independent axes—experience (`everyday` or `developer`) and workspace (`personal` or `team`)—then compose shared primitives into four purpose-built information architectures. Introduce remote-team capabilities as tenant-scoped domain services and API ports; never duplicate authorization, approval, budget, effect, or workflow rules in the UI.

**Tech Stack:** Python 3.12+, FastAPI, SQLite local mode, PostgreSQL-compatible deployment path, generated OpenAPI TypeScript types, React 19, TypeScript, Vite, Vitest/Testing Library, Tauri v2/Rust, SSE, Playwright/browser verification, Antigravity Website Design Blueprint.

## Global Constraints

- Preserve all M0.5-M11 security, compatibility, authority, redaction, streaming, desktop lifecycle, and update-verification behavior.
- Do not create four applications or four copies of business logic; build four workspace compositions over shared domain capabilities.
- Call the non-technical experience **Everyday** in product copy; do not label people “normal users.”
- Treat Team as shared multi-user workspaces with membership lifecycle, ownership, assignments, discussion, notifications, policy, and audit—not multiple local profiles.
- Keep secrets as broker references; never expose credential material in UI state, logs, events, fixtures, or API responses.
- Use source repositories only for interaction-pattern research. Do not copy their branding, layouts, source code, or developer density into Everyday experiences.
- No new dependency may be installed until it is listed at the milestone preflight. The user has granted approval, but the dependency and reason must still be recorded before installation.
- Every visible feature requires an executable API/domain path or a clearly labeled unavailable state; no static mock controls.
- Respect keyboard navigation, visible focus, reduced motion, contrast, empty/loading/error/offline states, and Windows scaling.
- Verify desktop and 390x844 responsive screenshots before each UI milestone is declared complete.
- Update `PROJECT_LOG.md` after every milestone.
- After each milestone passes its gate, create one logical commit with `Co-Authored-By: Claude <noreply@anthropic.com>` and push that commit to GitHub `main`.

---

## Confirmed Product Model

| Workspace | Primary job | Default navigation | Technical detail |
|---|---|---|---|
| Everyday Personal | Turn an intent into a safe, understandable result | Home, My Work, Automations, Files | Hidden behind “Details” |
| Developer Personal | Build, inspect, and control technical work | Repositories, Threads, Changes, Runs, Skills | First-class |
| Everyday Team | Coordinate owned work, handoffs, approvals, and shared knowledge | Team Home, Assigned Work, Approvals, Knowledge, People | Translated into impact/status language |
| Developer Team | Coordinate repository work, reviews, environments, policy, and cost | Repositories, Work Queue, Reviews, Environments, Policies | First-class and auditable |

Shared data must survive switching workspace presentation. A project, run, approval, artifact, or conversation is one record with different views—not duplicated persona data.

## Decisions Required Before Product Code

The following defaults are recommended but must be confirmed at the implementation kickoff:

1. **Product packaging:** one Corvus desktop binary with onboarding and a persistent workspace switcher, not separate editions.
2. **Team deployment:** host-agnostic remote Corvus server using PostgreSQL-compatible configuration; SQLite remains single-user/local demo mode.
3. **Identity:** local simulated identity for development plus existing OIDC contracts; production IdP registration remains deployment work.
4. **Collaboration transport:** durable API records plus SSE invalidation/notifications. Presence indicators are deferred until multi-user correctness is proven.
5. **Notifications:** in-app inbox in scope; email, Slack, and Teams delivery adapters deferred.
6. **Mobile:** responsive companion/browser verification only; no separate mobile application in this plan.
7. **Billing:** workspace budget and usage policy are in scope; subscription billing is not.

## Milestone 0 — Approved UX Architecture and Blueprint Packet

**Purpose:** Lock the information architecture, interaction contracts, and visual system before changing application code.

### Tasks

- [ ] Run the required blueprint sequence from the repository root: intake, research, target, section plan, compose, change plan, snapshot, verification packet, approval, build, and audit using the exact CLI command names supported by the installed blueprint.
- [ ] Produce `.antigravity/website-blueprint/SOURCE_MANIFEST.json`, `SECTION_PLAN.json`, `FRONTEND_CRAFT_BRIEF.md`, `EXPERIENCE_STORYBOARD.json`, `INTERACTION_SPEC.json`, `COMPONENT_ADOPTION_MAP.json`, and `DESIGN_AUDIT_REPORT.md`.
- [ ] Document journeys for all four workspaces: first run, resume work, create work, observe progress, approve/reject, recover from failure, switch workspace, invite/join team, and lose/recover connectivity.
- [ ] Define shared design tokens and four density/copy/navigation profiles without changing Corvus’s core identity.
- [ ] Specify truthful progressive disclosure: Everyday uses goals, impact, owner, next step, and deliverable; Developer exposes IDs, branches, diffs, logs, policies, autonomy, budget, and environment.
- [ ] Record T3Code and Hermes patterns adopted, adapted, and rejected with source provenance.
- [ ] Review the packet for placeholders, contradictory navigation, fake controls, and inaccessible interactions.

### Gate

- The user approves the four workspace storyboards and visual direction.
- No product code changes occur before this gate.

### Commit

- `docs(ui): approve four-workspace desktop architecture`

## Milestone 1 — Shared Application Shell and Preference Foundation

**Purpose:** Create one stable shell that can compose four workspaces without branching the product into four codebases.

### Expected files

- `apps/web/src/App.tsx` — reduce to authentication/bootstrap and top-level routing.
- `apps/web/src/app/AppShell.tsx` — title bar, workspace switcher, command/search entry, connection status, account menu.
- `apps/web/src/app/WorkspaceRouter.tsx` — selects the approved workspace composition.
- `apps/web/src/app/preferences.ts` — typed experience/workspace preference model and migration-safe persistence.
- `apps/web/src/components/` — shared navigation, status, composer, approval, empty-state, and error-boundary primitives.
- `apps/web/src/styles/` — tokens, shared shell, density, motion, and responsive rules.
- `apps/web/src/App.test.tsx` plus focused component tests.

### Tasks

- [ ] Write tests first for first-run selection, persistence, switching, keyboard navigation, invalid preference recovery, pairing, reconnect, and permission-driven route hiding.
- [ ] Add a short onboarding chooser that asks how the person works and whether the workspace is personal or shared; always allow later switching.
- [ ] Preserve fragment-only desktop pairing and existing session repair.
- [ ] Implement shared query/error/loading/offline primitives and route-level error boundaries.
- [ ] Add semantic navigation landmarks, focus restoration, skip links, reduced-motion behavior, and responsive shell collapse.
- [ ] Keep all data access behind the typed `CorvusApi` adapter.

### Gate

- Existing pairing/project/workflow tests pass.
- New shell tests pass with all four route compositions.
- Production web build passes; no console errors at desktop or 390x844.

### Commit

- `feat(ui): add adaptive Corvus workspace shell`

## Milestone 2 — Personal Workspaces

**Purpose:** Deliver complete, differentiated Everyday Personal and Developer Personal workflows on the existing execution core.

### Everyday Personal

- [ ] Build Home around “What do you want to get done?”, recent results, upcoming approvals, and resumable work.
- [ ] Replace workflow jargon with guided goal creation: desired result, useful context/files, constraints, review level, and confirmation.
- [ ] Present progress as a readable timeline with current step, why Corvus paused, what needs attention, and expected deliverables.
- [ ] Provide My Work, Automations, and Files views with plain-language actions and technical detail drawers.
- [ ] Make approvals explain the proposed action, affected data/system, reversibility, cost, and safe alternatives.

### Developer Personal

- [ ] Build repository registration and project association contracts before exposing repository navigation.
- [ ] Add repositories, threads, changes, runs, and skills views using existing workflows, artifacts, conversations, routines, and skills where possible.
- [ ] Add typed Git/repository ports for status, branches/worktrees, diffs, and commit metadata; keep native operations in trusted backend/desktop adapters.
- [ ] Expose branch, environment, model/provider reference, autonomy, budget, logs, checkpoints, artifacts, and test results.
- [ ] Add review actions with explicit diffs and governed apply/commit boundaries; never let the React client manufacture authority.

### Likely backend files

- `corvus/domain/` — repository/work-context records only where missing.
- `corvus/application/` — repository inspection and developer-workspace use cases.
- `corvus/ports/` and `corvus/adapters/` — typed Git/filesystem inspection boundaries.
- `corvus/api.py` and `openapi/corvus-mvp.json` — tenant-scoped endpoints and generated contracts.
- `tests/mvp/` — authorization, traversal, redaction, and adapter behavior.

### Gate

- A non-technical user can create, monitor, approve, and retrieve a result without seeing IDs or execution jargon.
- A developer can inspect the same run’s repository context, changes, logs, artifacts, and controls.
- Cross-view tests prove both presentations reference the same durable records.
- Desktop and responsive visual audits pass.

### Commit

- `feat(ui): deliver tailored personal workspaces`

## Milestone 3 — Real Team Collaboration Core

**Purpose:** Make Team a correct multi-user product surface before building team dashboards.

### Domain and persistence

- [ ] Add tenant/workspace-scoped invitations with expiry, acceptance, cancellation, and replay protection.
- [ ] Extend membership lifecycle with owner/admin/member/viewer responsibilities, role changes, suspension, removal, and last-owner protection.
- [ ] Add work assignment, owner, due date, status, watcher, and handoff records linked to existing outcomes/workflows/work items.
- [ ] Add threaded comments, mentions, reactions only if required by the approved spec, edits with audit history, and soft deletion policy.
- [ ] Add durable in-app notifications with read state, deduplication, cursor pagination, and preference controls.
- [ ] Add team policy records for approval thresholds, autonomy ceilings, budget limits, provider grants, retention, and member capabilities.
- [ ] Add workspace-scoped shared knowledge visibility and provenance rules.
- [ ] Ensure every mutation records the acting principal and audit event.

### API and synchronization

- [ ] Expose generated, tenant-scoped endpoints for invitation, membership, assignment, comment, notification, policy, and knowledge operations.
- [ ] Add optimistic concurrency/version checks for editable shared records.
- [ ] Extend SSE with workspace-scoped invalidation events and reconnect cursors; avoid premature presence/chat protocols.
- [ ] Verify revocation takes effect on the next request and active streams terminate or lose access safely.
- [ ] Add PostgreSQL-backed integration coverage where available while retaining a functional SQLite local adapter.

### Security tests

- [ ] Cross-tenant access denial for every new repository and endpoint.
- [ ] Role escalation, invitation replay, removed-member access, mention leakage, notification leakage, stale update, and audit tamper tests.
- [ ] Secret-reference and sensitive-payload redaction tests.

### Gate

- Two distinct principals can join one workspace, assign work, discuss it, receive an in-app notification, and observe the same durable state.
- A removed member immediately loses access.
- Cross-tenant and stale-write tests pass.

### Commit

- `feat(teams): add governed multi-user collaboration core`

## Milestone 4 — Team Workspaces

**Purpose:** Build two team experiences over Milestone 3’s real collaboration services.

### Everyday Team

- [ ] Team Home: shared goals, health, blocked work, recent outcomes, and a clear “needs attention” queue.
- [ ] Assigned Work: owner/date/status-oriented list and board views without execution internals.
- [ ] Approvals: impact-first review queue with delegation/handoff and policy explanation.
- [ ] Shared Knowledge: provenance, visibility, freshness, and source-aware retrieval.
- [ ] People: invitations, roles, availability/status only when truthful, and responsibility summaries.

### Developer Team

- [ ] Repositories: registered repos, branch/worktree state, ownership, and current activity.
- [ ] Work Queue: assignments, dependencies, runs, failures, and developer-level filters.
- [ ] Reviews: diffs, checks, artifacts, comments, approvals, and governed commit/apply controls.
- [ ] Environments: provider references, readiness, deployment state, and audit trail—never secret values.
- [ ] Policies: autonomy ceilings, approval requirements, budget/cost, role capabilities, and retention.

### Cross-workspace behavior

- [ ] Provide permalinks and consistent object identity across Everyday and Developer views.
- [ ] Translate technical statuses into Everyday copy without hiding risk or inventing certainty.
- [ ] Support comments/mentions/notifications from contextual side panels, not a disconnected admin page.
- [ ] Add empty states for new teams and migration guidance for an existing personal project joining a team.

### Gate

- End-to-end browser tests cover invite → join → assign → execute → comment → approve → deliver → notify.
- Role-specific screenshots prove each user sees appropriate navigation and actions.
- Keyboard, reduced-motion, offline/reconnect, desktop, and responsive audits pass.

### Commit

- `feat(ui): deliver everyday and developer team workspaces`

## Milestone 5 — Desktop Integration and Operational Hardening

**Purpose:** Make the adaptive product feel native and remain safe under real desktop lifecycle conditions.

### Tasks

- [ ] Preserve the existing fixed-argument sidecar launch, authenticated readiness, one-time fragment pairing, navigation restrictions, CSP, graceful shutdown, and redacted diagnostics.
- [ ] Add native project/repository/file selection only through narrow Tauri commands with validated paths and least privilege.
- [ ] Restore the last valid workspace and route after sidecar restart without persisting pairing secrets.
- [ ] Surface starting, ready, reconnecting, offline, failed, and stopped states in all four experiences using persona-appropriate copy.
- [ ] Validate Windows scaling, window resizing, keyboard accelerators, minimum window size, high contrast, and screen-reader labels.
- [ ] Run Rust lifecycle/security tests, web tests/build, Python focused/full tests, type checks, lint, security scan, desktop no-bundle build, and package smoke test.
- [ ] Update `README.md`, `HACKATHON_STATUS.md`, and `PROJECT_LOG.md` with truthful local/remote/team setup and limitations.

### Gate

- The packaged Windows app launches, pairs, switches among allowed workspaces, reconnects after sidecar restart, and shuts down without orphan processes.
- All affected CI jobs are green on the pushed main commit.
- The worktree is clean.

### Commit

- `release: certify adaptive Corvus desktop MVP`

## Verification Matrix

| Concern | Automated evidence | Runtime evidence |
|---|---|---|
| Shared authority | Python service/repository tests | Attempt forbidden UI/API action |
| Persona composition | Vitest route/copy/action tests | Four desktop screenshots |
| Team isolation | Cross-tenant API and persistence tests | Two-browser/principal scenario |
| Collaboration recovery | SSE cursor, stale write, notification tests | Disconnect/reconnect scenario |
| Accessibility | semantic queries and automated audit | keyboard, focus, reduced motion, high contrast |
| Desktop lifecycle | Rust unit/integration tests | launch, sidecar restart, close/process check |
| Responsive behavior | layout tests where useful | 390x844 screenshots for all core routes |
| Supply chain | existing build/SBOM/provenance checks | packaged artifact smoke test |

## Git and Release Procedure for Every Milestone

- [ ] Confirm `git status --short --branch` and preserve unrelated user changes.
- [ ] Pull/fetch and verify the milestone is based on current `origin/main`; never rewrite history.
- [ ] Run the milestone’s focused gate, then the proportional regression suite.
- [ ] Update `PROJECT_LOG.md` using the required format and record assumptions/deferred work.
- [ ] Review `git diff --check`, staged diff, and secret scan.
- [ ] Commit with the milestone message and required co-author trailer.
- [ ] Push the tested commit directly to GitHub `main` as requested.
- [ ] Confirm the remote main SHA and CI run; fix failures in a follow-up milestone commit before proceeding.

## Explicit Stop Boundaries

1. **Current stop:** this plan is delivered for review; no product code is changed.
2. **After Milestone 0:** stop for approval of the four workspace storyboards and visual system.
3. **After Milestone 2:** stop for hands-on review of both Personal experiences before adding collaboration migrations.
4. **After Milestone 3:** stop for a security/correctness review of multi-user behavior before Team UI implementation.
5. **After Milestone 5:** stop after release evidence; production hosting, external IdP registration, email/chat notification delivery, subscription billing, notarization, and multi-OS certification require separate authorization.

## Planning Assumptions to Review

- One binary and one account can access multiple workspace experiences.
- Experience selection changes information architecture and defaults, never permissions or stored truth.
- Existing projects remain valid and default to Everyday Personal until a user chooses otherwise.
- Team collaboration is remote-capable and tenant-scoped; SQLite remains a local/demo mode rather than the shared production database.
- In-app notifications and SSE are sufficient for the first complete Team solution.
- Repository/Git capabilities are required for Developer workspaces but remain behind typed trusted adapters.
- The current React/Vite/Tauri/Python stack remains; no framework rewrite is planned.

## Known Scope Deferred by This Plan

- Production cloud provisioning and managed service operations.
- External OIDC application registration and enterprise directory provisioning.
- Email, Slack, Microsoft Teams, or push-notification delivery adapters.
- Subscription billing and marketplace flows.
- Live cursors/presence, voice/video, and full chat replacement.
- macOS signing/notarization and unsupported multi-platform installer certification.
- A separate mobile application.
