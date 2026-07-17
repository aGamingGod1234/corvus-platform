from __future__ import annotations

import json

from corvus.mvp.provider_catalog import build_provider_catalog


def test_provider_catalog_is_truthful_and_contains_recommended_models() -> None:
    catalog = build_provider_catalog(codex_available=True, claude_available=True)

    by_id = {provider.id: provider for provider in catalog}

    assert tuple(by_id) == ("codex", "claude", "gemini", "cursor", "xai")
    assert by_id["codex"].status == "ready"
    assert by_id["claude"].status == "ready"
    assert by_id["gemini"].status == "preview"
    assert by_id["cursor"].status == "unavailable"
    assert by_id["xai"].status == "preview"
    assert by_id["codex"].transport == "local"
    assert by_id["xai"].transport == "api"
    assert {model.label for model in by_id["codex"].models} >= {
        "GPT-5.6 Sol",
        "GPT-5.6 Terra",
        "GPT-5.5",
    }
    assert any(model.recommended for model in by_id["claude"].models)
    assert by_id["claude"].thinking_levels[-1] == "max"
    assert by_id["codex"].status_label == "Detected; sign-in is checked when a run starts"
    assert by_id["claude"].status_label == "Detected; sign-in is checked when a run starts"


def test_provider_catalog_never_serializes_executable_paths_or_secrets() -> None:
    rendered = json.dumps(
        [provider.as_dict() for provider in build_provider_catalog(False, False)],
        sort_keys=True,
    ).lower()

    assert "c:\\" not in rendered
    assert "/users/" not in rendered
    assert "api_key" not in rendered
    assert "token" not in rendered
    assert "secret" not in rendered
    assert "executable" not in rendered
