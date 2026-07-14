# Change Plan

## Allowed Files
- apps/web/**
- .gitignore
- corvus/mvp/api.py
- corvus/mvp/core.py
- corvus/mvp/governance.py
- corvus/mvp/ingress.py
- openapi/**
- tests/mvp/test_api.py
- tests/mvp/test_openapi_export.py
- .antigravity/website-blueprint/**

## Forbidden Files
- corvus/core/**

## Expected Edits
- Add the connected React operator console and generated API contract.
- Add authenticated API list endpoints and response schemas needed by the console.
- Preserve dependency order when returning workflow work items.
- Add backend and frontend regression tests.

## Dependency Changes
- Approved React, Vite, TypeScript, generated-client, icon, and test tooling only

## Test Commands
- ag design verify-packet --require-approval
- ag design audit-packet --url <local-url>

## Rollback Strategy
- Revert only the files listed under Allowed Files.
