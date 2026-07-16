# Change Plan

## Allowed files

- `apps/web/src/**`
- `apps/desktop/src-tauri/src/**`

## Forbidden files

- `corvus/domain/**`

## Approved frontend boundary

Future frontend tasks may implement the seven approved surfaces, source hooks, component hooks, responsive layouts, focus behavior, error/recovery states, and truthful capability presentation. Tauri tasks may add only the native client commands required by approved frontend flows. Task 1.1 itself changes no product code.

## Explicitly out of scope

- Domain authority, policy, membership, audit, budget, credential, or runtime semantics.
- Dependency additions or upgrades.
- Production credentials, billing activation, database mutations, deployment, or merge.
- Renaming or refactoring existing logic unless a later task explicitly requires it.

## Expected implementation selectors

- Surface roots: `[data-corvus-surface]` and `[data-source-refs]`.
- Sourced controls: `[data-component-source="shadcn-button"]` and `[data-component-source="lucide-send"]`.
- Conversation: `[data-ui="thread-view"]`, `[data-ui="composer"]`, `[data-ui="composer-send"]`.
- Run: `[data-ui="flightpath"]`, `[data-run-stage]`, `[data-ui="approval-gate"]`.
- Responsive overlays: semantic dialog/sheet roots with trigger focus restoration.

## Dependency changes

- None.

## Verification commands

- `ag design verify-packet --project-root . --require-approval`
- Frontend unit, accessibility, and API-contract tests named by each implementation task.
- Browser journeys and fixed screenshots at `1440x1000`, `1024x900`, and `390x844`.
- Reduced-motion and active-motion runtime evidence.
- Tauri verification only when native files are changed.

## Rollback strategy

Revert only files changed by the relevant frontend task. Do not roll back or replace `corvus/domain/**` to repair presentation behavior.
