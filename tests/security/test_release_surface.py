from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release.yml"
VERCEL_CONFIG = ROOT / "apps" / "web" / "vercel.json"
HOSTED_RUNTIME_POLICY = ROOT / "apps" / "web" / "HOSTED_RUNTIME_SECURITY.md"


def _workflow_trigger_block() -> str:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    return workflow.split("\non:\n", maxsplit=1)[1].split("\njobs:\n", maxsplit=1)[0]


def test_desktop_packaging_cannot_be_started_by_pull_requests() -> None:
    triggers = _workflow_trigger_block()

    assert "  pull_request:" not in triggers
    assert "  pull_request_target:" not in triggers
    assert "  workflow_dispatch:" in triggers
    assert '      - "v*"' in triggers


def test_hosted_alpha_keeps_a_documented_same_origin_network_policy() -> None:
    assert HOSTED_RUNTIME_POLICY.exists(), "hosted runtime network policy must be documented"

    policy = HOSTED_RUNTIME_POLICY.read_text(encoding="utf-8")
    normalized_policy = " ".join(policy.split())
    vercel = json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))
    content_security_policy = next(
        header["value"]
        for rule in vercel["headers"]
        for header in rule["headers"]
        if header["key"] == "Content-Security-Policy"
    )

    assert "connect-src 'self'" in content_security_policy
    assert "No external streaming or API origin is required for the alpha" in normalized_policy
    assert "unverified trust boundary" in normalized_policy
