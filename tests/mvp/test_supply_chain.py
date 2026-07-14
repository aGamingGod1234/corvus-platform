from __future__ import annotations

from pathlib import Path

from scripts.generate_supply_chain import build_provenance, build_sbom

ROOT = Path(__file__).resolve().parents[2]


def test_sbom_is_reproducible_and_lists_locked_python_components() -> None:
    first = build_sbom(ROOT / "uv.lock")
    second = build_sbom(ROOT / "uv.lock")

    assert first == second
    assert first["bomFormat"] == "CycloneDX"
    names = {component["name"] for component in first["components"]}
    assert {"corvus", "cryptography", "sqlalchemy"}.issubset(names)


def test_provenance_binds_source_commit_and_build_inputs() -> None:
    provenance = build_provenance(ROOT, commit="test-commit")

    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    assert provenance["subject"][0]["name"] == "corvus-source"
    assert provenance["predicate"]["vcs"]["commit"] == "test-commit"
    materials = provenance["predicate"]["buildDefinition"]["resolvedDependencies"]
    assert {item["uri"] for item in materials} == {"pyproject.toml", "uv.lock"}
