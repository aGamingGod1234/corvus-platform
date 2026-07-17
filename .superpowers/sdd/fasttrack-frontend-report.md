# Hackathon Fast-Track Frontend Report

Date: 2026-07-17

## Outcome

Corvus now opens into a functional chat-first local MVP while preserving the existing Google-first hosted onboarding and workspace authority boundaries. The paired local runtime can start and stop Local Codex runs through the bounded `/api/local-chat` adapter, stream output, and keep versioned thread history explicitly on this device. The adaptive web shell exposes real Settings and Schedule surfaces while hosted execution still hands off truthfully to the local runtime.

## TDD Evidence

- Device settings RED: missing `devicePreferences` module; GREEN: 2 focused tests.
- Chat/API RED: missing `conversationApi` and `ConversationWorkspace`; GREEN: 4 focused tests.
- Settings/Routines RED: missing component modules; GREEN: 2 focused tests.
- Adaptive navigation RED: four profile route expectation failures; GREEN: 4 focused tests.
- Integration repair: legacy console tests were updated to navigate explicitly to Repositories after chat became the default.

## Verification

- `pnpm test`: 22 files, 123 tests passed.
- `pnpm build`: TypeScript and Vite production build passed.
- No dependency installation, deploy, push, PR, billing, Cloud execution, E2B, or production migration.

## Truthful Boundaries

- Only paired Local Codex execution is active; the model is `Codex default`.
- Conversation history and device settings are labeled `This device`; cross-device transcript sync is not claimed.
- Other providers and MCP/integrations are labeled Coming soon.
- Cloud remains Preview and hosted users are directed to the local runtime.
- Timed recurrence is not claimed; Schedule supports the real create/list/run-now routine APIs only.
