# Corvus Adaptive Workspace Craft Brief

This packet explicitly applies `website-design-blueprint`, `impeccable`, and `design-motion-principles` to the authenticated Corvus application while preserving local product rules and truthful capability gates.

## Viewer intent

Start or resume meaningful agent work with the right level of explanation, team context, and runtime truth for the current user.

## Scene sentence

A warm, flight-path-inspired workspace becomes spacious and outcome-led for Everyday work or dense and exact for Developer work while Local/Cloud status stays visible and honest.

## Color strategy

Warm paper and ink establish calm; cobalt marks Personal action and connection; accessible teal marks Team scope alongside text and owner cues; copper is reserved for consequential approvals.

## Typography lane

Inter Tight carries interface language, Fraunces marks a few outcome-led headings, and IBM Plex Mono exposes code, IDs, branches, logs, diffs, and environment metadata.

## Media hierarchy

Real work state, progress/activity spines, files/diffs, artifacts, and owner context are primary. Decorative iconography is secondary and always labeled. There is no stock imagery or fabricated data.

## Card budget

Maximum generic cards: 3. Corvus uses continuous work surfaces, indexed rows, activity spines, and contextual panes instead of a generic dashboard card grid.

## Motion intent

Motion explains selection, route change, connection state, and inspector context; it never decorates loading or hides authority changes.

## Anti-patterns

Avoid generic SaaS card grids, glass panels, fake collaboration, fake checkout, hidden runtime truth, color-only roles, developer jargon in Everyday views, and desktop navigation stacked on mobile.

## Product job

Corvus is one agent workspace that changes its information density, language, and navigation for two independent choices: Everyday or Developer work style, and Personal or Team scope. The first release keeps the existing local Python core authoritative, presents E2B-backed Corvus Cloud as a truthful preview until its control plane exists, and preserves one recognizable Corvus identity across web and desktop.

## Experience promise

- Everyday users see goals, progress, decisions, owners, and results before implementation detail.
- Developers see repositories, runs, diffs, logs, policies, environments, and precise controls.
- Personal work emphasizes focus and private automations.
- Team work emphasizes assignments, approvals, knowledge, people, and audit context without implying collaboration before the backend grants it.
- Local means this computer only. Corvus Cloud means a signed-in E2B workspace shared across the user's desktop and web sessions.

## First-run sequence

1. **How do you want Corvus to work with you?** Choose Everyday or Developer.
2. **Who is this workspace for?** Choose Just me or My team. Team selection says invitations come after setup and does not grant team permissions.
3. **Where should Corvus run?** Choose On this computer or Corvus Cloud (E2B). Local is operational. Cloud is clearly labeled Preview and has no payment collection.

Every step includes Back, a visible step count, keyboard radio-card behavior, and “Change anytime.” Completion moves focus to the workspace heading.

## Four workspace compositions

| Composition | Navigation | Default surface | Detail treatment |
|---|---|---|---|
| Everyday Personal | Home, My Work, Automations, Files | Today, suggested help, recent outcomes, scheduled routines | Plan, sources, progress, result; technical metadata under Details |
| Developer Personal | Repositories, Threads, Changes, Runs, Skills | Repositories, active agents, checks, branches | Tool calls, logs, changed files, diffs, tests, artifacts, budget |
| Everyday Team | Team Home, Assigned Work, Approvals, Knowledge, People | Assigned work, review requests, team outcomes | Owners, decisions, comments, sources, handoff history |
| Developer Team | Repositories, Work Queue, Reviews, Environments, Policies | Engineering queue, failing checks, reviews, agent activity | Diffs, checks, review comments, approvals, audit, ownership, cost |

Routes and actions are filtered by server capabilities before render. A direct forbidden route opens an explanatory access page. Presentation changes never create authority or duplicate domain data.

## Visual direction

Keep the existing warm paper, ink, cobalt signal, copper approval, Fraunces/Inter Tight/IBM Plex Mono typography, graph-line texture, and flight-path activity spine. Everyday views are spacious and sentence-case with outcome-led grouping. Developer views are denser, use split panes and tabular rhythm, and expose mono metadata. Personal uses cobalt emphasis. Team adds accessible teal plus explicit owner/scope labels; color is never the only cue.

Desktop uses a 240px navigation rail, flexible content, and optional 360px inspector. At 390x844, use a compact top bar, four-item bottom navigation plus More, a context drawer, and a full-screen semantic inspector. Never stack the complete desktop rail above mobile content.

## Runtime and identity truthfulness

- Local status: “Local · Connected.” Data remains on the current machine and may be opened by a browser on that same machine.
- Cloud status: “Cloud · Synced” only after real authenticated synchronization exists.
- Cloud Preview: “Corvus Cloud is in preview. Cloud workspaces run in isolated E2B environments and sync across your signed-in devices. No payment will be collected.”
- Show “Sign in with Google” only when the auth capability is present. Otherwise show “Cloud setup is not available in this build” and “Use local workspace.”
- Plans show Preview, “Cloud plans are coming later,” “Not yet available,” and disabled “Billing not enabled.” Never collect payment details or show fake success.
- Never promise queued offline edits until durable queuing exists. Until then: “Editing is unavailable until connection returns.”

## Motion and accessibility

Use 160–280ms state transitions only for selection, navigation, inspector entry, and live status. Respect reduced motion. Provide visible focus, skip-to-main, semantic radio-card selection, `aria-live` status, focus restoration after route/sheet changes, Escape to close the mobile inspector, and high-contrast-safe borders and text.

## Source application

- T3Code: adopt project/thread hierarchy, changed-file readability, and developer density; reject a developer-only IA for Everyday users.
- Hermes Agent: adopt the idea of tool-rich agent capability and restrained dark-workbench confidence; preserve Corvus’s own warm identity and do not copy branding.
- Linear: adopt concise setup choices and calm hierarchy; reject marketing claims and product-specific copy.
- shadcn Tabs: adapt roving-keyboard and selected-state behavior with native typed React components; add no Radix dependency in the shell milestone.
- Lucide Cloud: adapt the cloud path as a decorative icon beside a full semantic label.

## Failure conditions

- Four duplicated applications, route trees, or data models.
- A cosmetic Team toggle that implies membership or permissions.
- Cloud, synchronization, payment, invitations, or offline mutation claims without matching capabilities.
- Pairing secrets, Google tokens, Corvus refresh tokens, or E2B credentials in React state persistence or localStorage.
- Generic card-grid sameness, desktop rails stacked on mobile, inaccessible custom selection controls, or process/blueprint text shown to users.

## Tool-contract applicability notes

This is an authenticated application workspace, not a marketing, ecommerce, local-business, bilingual, or reviews surface. Business reviews, Places imagery, marketing hero copy, checkout forms, and fabricated social proof are intentionally inapplicable and must not be rendered.
