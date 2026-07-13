from __future__ import annotations

import importlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine

from corvus.security import sha256_file
from corvus.store import Base


def _legacy_database(path: Path, canary: str) -> None:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO memories "
            "(id, project_id, identity_id, kind, content, source, confidence, pinned, "
            "expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                "legacy-user",
                "semantic",
                f"token={canary}",
                "legacy fixture",
                "1.0",
                0,
                None,
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.commit()


def test_v1_quarantine_capture_is_sealed_redacted_and_idempotent(tmp_path: Path) -> None:
    quarantine = importlib.import_module("corvus.quarantine")
    canary = "fixture-sensitive-value-123456"
    database = tmp_path / "legacy.db"
    config = tmp_path / "config"
    artifacts = tmp_path / "artifacts"
    bundles = tmp_path / "bundles"
    backups = tmp_path / "backups"
    captures = tmp_path / "quarantine"
    _legacy_database(database, canary)
    config.mkdir()
    (config / "policy.yaml").write_text(
        yaml.safe_dump({"autonomy": 3, "budgets": {"max_runtime_seconds": 120}}),
        encoding="utf-8",
    )
    (config / "providers.yaml").write_text(
        yaml.safe_dump(
            {
                "active_provider": "fixture",
                "providers": [
                    {
                        "name": "fixture",
                        "kind": "openai",
                        "base_url": "https://api.example.invalid",
                        "model": "fixture-model",
                        "keyring_service": "corvus-model-provider",
                        "api_key": canary,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (config / "onboarding.json").write_text(
        json.dumps({"schema_version": 1, "completed": False}),
        encoding="utf-8",
    )
    (config / ".env").write_text(f"API_KEY={canary}\n", encoding="utf-8")
    for root, name, data in (
        (artifacts, "aa/artifact.bin", b"artifact"),
        (bundles, "bundle/bundle.json", b'{"schema_version":1}'),
        (backups, "backup/checkpoint.enc", b"ciphertext"),
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    database_before = sha256_file(database)

    first = quarantine.capture_v1_quarantine(
        database=database,
        config_root=config,
        artifact_root=artifacts,
        bundle_root=bundles,
        backup_root=backups,
        quarantine_root=captures,
    )
    second = quarantine.capture_v1_quarantine(
        database=database,
        config_root=config,
        artifact_root=artifacts,
        bundle_root=bundles,
        backup_root=backups,
        quarantine_root=captures,
    )

    assert first == second
    assert first.path == captures / first.capture_id
    assert quarantine.verify_v1_quarantine(first.path) is True
    assert sha256_file(database) == database_before
    assert [item.name for item in captures.iterdir()] == [first.capture_id]

    records = json.loads((first.path / "records.json").read_text(encoding="utf-8"))
    encoded = json.dumps(records, sort_keys=True)
    assert canary not in encoded
    assert "[REDACTED]" in encoded
    assert ".env" not in records["config"]
    assert sorted(records["database"]) == [
        "deliveries",
        "memories",
        "run_events",
        "skill_versions",
    ]
    assert records["config"]["providers.yaml"]["providers"][0]["keyring_service"] == (
        "corvus-model-provider"
    )
    assert "api_key" in records["config"]["providers.yaml"]["providers"][0]
    for domain in ("artifacts", "bundles", "backups"):
        assert records[domain]
        assert set(records[domain][0]) == {"relative_path", "sha256", "size"}

    manifest = json.loads((first.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["capture_id"] == first.capture_id
    assert manifest["seal_algorithm"] == "sha256"
    assert len(manifest["seal"]) == 64

    (first.path / "records.json").write_text("{}", encoding="utf-8")
    assert quarantine.verify_v1_quarantine(first.path) is False
    with pytest.raises(ValueError, match="existing quarantine capture failed verification"):
        quarantine.capture_v1_quarantine(
            database=database,
            config_root=config,
            artifact_root=artifacts,
            bundle_root=bundles,
            backup_root=backups,
            quarantine_root=captures,
        )
