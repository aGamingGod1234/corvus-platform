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

## Sandbox image

Production builds default to the supported digest-pinned image:

```text
python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf
```

Existing installations that set `CORVUS_SANDBOX_IMAGE=python:3.12-slim` must either unset the variable to adopt this default or replace it with a verified `name@sha256:<digest>` reference. Tag-only production overrides are rejected before a container starts. Podman uses `--pull=never`, so pre-pull the exact reference during deployment; Docker deployments may also pre-pull it to make startup deterministic.

```bash
export CORVUS_SANDBOX_IMAGE='python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf'
docker pull "$CORVUS_SANDBOX_IMAGE"   # or: podman pull "$CORVUS_SANDBOX_IMAGE"
```

Unpinned `python:3.12-slim` remains available only when code explicitly selects non-production mode for local development or tests.

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

The readable Milestones 1–11 delivery outline is in [`ROADMAP.md`](ROADMAP.md). [`PLAN.md`](PLAN.md) remains the authoritative implementation and security specification; reviewer evidence and limitations are in [`PLAN-REVIEW-LOG.md`](PLAN-REVIEW-LOG.md).
