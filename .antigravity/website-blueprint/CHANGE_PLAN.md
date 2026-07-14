# Change Plan

## Allowed Files
- apps/web/**
- apps/desktop/**
- corvus/mvp/**
- openapi/**
- tests/**
- docs/**
- scripts/**
- .antigravity/website-blueprint/**
- pyproject.toml
- uv.lock
- README.md
- HACKATHON_STATUS.md
- PROJECT_LOG.md
- .env.example

## Forbidden Files
- corvus/core/**

## Expected Edits
- Describe the exact implementation edits before approval.

## Dependency Changes
- Add e2b>=2.3,<3 for E2B sandbox lifecycle and Authlib>=1.3,<2 for Google/OIDC authorization-code flows.

## Test Commands
- ag design verify-packet --require-approval
- ag design audit-packet --url <local-url>

## Rollback Strategy
- Revert only the files listed under Allowed Files.
