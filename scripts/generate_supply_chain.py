from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

_MATERIALS = ("pyproject.toml", "uv.lock")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_sbom(lock_path: Path) -> dict[str, Any]:
    with lock_path.open("rb") as source:
        lock = tomllib.load(source)
    components = []
    for package in lock.get("package", []):
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
            }
        )
    components.sort(key=lambda item: (item["name"], item["version"]))
    corvus = next(
        (component for component in components if component["name"] == "corvus"),
        {"type": "application", "name": "corvus", "version": "unknown"},
    )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {**corvus, "type": "application"}},
        "components": components,
    }


def build_provenance(root: Path, *, commit: str) -> dict[str, Any]:
    materials: list[dict[str, Any]] = [
        {"uri": name, "digest": {"sha256": _sha256_file(root / name)}}
        for name in _MATERIALS
    ]
    source_digest = hashlib.sha256(
        "".join(item["digest"]["sha256"] for item in materials).encode("ascii")
    ).hexdigest()
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "corvus-source", "digest": {"sha256": source_digest}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://corvus.local/build/python-wheel-v1",
                "externalParameters": {},
                "internalParameters": {},
                "resolvedDependencies": materials,
            },
            "runDetails": {"builder": {"id": "corvus-local-reproducible-builder"}},
            "vcs": {"commit": commit},
        },
    }


def _git_commit(root: Path) -> str:
    git_path = root / ".git"
    if git_path.is_file():
        marker = git_path.read_text(encoding="utf-8").strip()
        if not marker.startswith("gitdir: "):
            raise RuntimeError("git_directory_pointer_invalid")
        git_path = (root / marker.removeprefix("gitdir: ")).resolve()
    head = (git_path / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head
    ref = head.removeprefix("ref: ")
    ref_path = git_path / ref
    if not ref_path.is_file():
        raise RuntimeError("git_reference_not_loose")
    return ref_path.read_text(encoding="utf-8").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic Corvus SBOM and provenance")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("dist/supply-chain"))
    parser.add_argument("--commit")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    output_dir = arguments.output_dir
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    sbom = build_sbom(root / "uv.lock")
    provenance = build_provenance(root, commit=arguments.commit or _git_commit(root))
    (output_dir / "sbom.cdx.json").write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "provenance.intoto.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
