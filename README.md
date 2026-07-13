# Corvus V2

Corvus is a configuration-driven, proof-carrying AI development platform. One authoritative Python core supports multiple interaction surfaces and deployment profiles without duplicating policy or run state.

## Product modes

- **Interaction:** CLI, browser web, cross-platform desktop, or approved third-party channels.
- **Collaboration:** Individual or Team.
- **Hosting:** Local/self-hosted or Corvus Cloud.
- **Models:** User-provided local endpoints, API credentials, or provider-owned OAuth such as Codex/ChatGPT.

Credentials are referenced through the OS keyring or a scoped cloud vault; plaintext secrets do not belong in runtime configuration or sandboxes.

## Current status

This repository is an early V2 migration from Corvus CLI V1. The CLI remains available while security boundaries, durable state, team authorization, and shared client protocols are introduced incrementally. Web, desktop, and channel clients must remain thin adapters over the same core.

Corvus build execution is fail-closed. If Docker or Podman is unavailable, ordinary chat may remain available but isolated builds do not fall back to host execution.

## Development

Requirements:

- Python 3.12
- `uv`

```bash
env -u PYTHONHOME -u PYTHONPATH uv sync --all-groups --locked
env -u PYTHONHOME -u PYTHONPATH uv run pytest -q
env -u PYTHONHOME -u PYTHONPATH uv run ruff check .
env -u PYTHONHOME -u PYTHONPATH uv run corvus --help
```

On Windows Git Bash, clearing `PYTHONHOME` and `PYTHONPATH` prevents a different Python standard library from contaminating the selected 3.12 interpreter.

The implementation and security migration plan is in [`PLAN.md`](PLAN.md); reviewer evidence and limitations are in [`PLAN-REVIEW-LOG.md`](PLAN-REVIEW-LOG.md).
