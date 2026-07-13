from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import corvus.quarantine as quarantine
from corvus.security import sha256_file

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "v1" / "quarantine"
FIXTURE_SOURCE = FIXTURE_ROOT / "source"
FIXTURE_MANIFEST = FIXTURE_ROOT / "fixture_manifest.json"
CANARY = "fixture-sensitive-value-123456"
SECOND_CANARY = "fixture-sensitive-value-654321"


def _copy_verified_fixture(tmp_path: Path, name: str) -> Path:
    manifest = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["fixture_schema_version"] == 1
    expected_files: dict[str, dict[str, Any]] = manifest["files"]
    actual_files = sorted(
        path.relative_to(FIXTURE_SOURCE).as_posix()
        for path in FIXTURE_SOURCE.rglob("*")
        if path.is_file()
    )
    assert actual_files == sorted(expected_files)
    for relative_path, expected in sorted(expected_files.items()):
        source = FIXTURE_SOURCE / relative_path
        assert source.stat().st_size == expected["size"]
        assert sha256_file(source) == expected["sha256"]

    destination = tmp_path / name
    shutil.copytree(FIXTURE_SOURCE, destination, copy_function=shutil.copy2)
    for relative_path, expected in sorted(expected_files.items()):
        copied = destination / relative_path
        assert copied.stat().st_size == expected["size"]
        assert sha256_file(copied) == expected["sha256"]
    return destination


def _capture(source: Path, quarantine_root: Path) -> quarantine.QuarantineReceipt:
    return quarantine.capture_v1_quarantine(
        database=source / "corvus.db",
        config_root=source / "config",
        artifact_root=source / "artifacts",
        bundle_root=source / "bundles",
        backup_root=source / "backups",
        quarantine_root=quarantine_root,
    )


def test_v1_quarantine_capture_is_sealed_redacted_and_idempotent(tmp_path: Path) -> None:
    source = _copy_verified_fixture(tmp_path, "source")
    database = source / "corvus.db"
    captures = tmp_path / "quarantine"
    database_before = sha256_file(database)

    first = _capture(source, captures)
    second = _capture(source, captures)

    assert first == second
    assert first.path == captures / first.capture_id
    assert first.capture_id != first.records_sha256
    assert quarantine.verify_v1_quarantine(first.path) is True
    assert sha256_file(database) == database_before
    assert [item.name for item in captures.iterdir()] == [first.capture_id]

    records = json.loads((first.path / "records.json").read_text(encoding="utf-8"))
    encoded = json.dumps(records, sort_keys=True)
    assert CANARY not in encoded
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
    assert manifest["records_sha256"] == first.records_sha256
    assert manifest["seal_algorithm"] == "sha256"
    assert len(manifest["source_database_sha256"]) == 64
    assert len(manifest["source_snapshot_sha256"]) == 64
    assert first.source_snapshot_sha256 == manifest["source_snapshot_sha256"]
    assert len(manifest["seal"]) == 64

    (first.path / "records.json").write_text("{}", encoding="utf-8")
    assert quarantine.verify_v1_quarantine(first.path) is False
    with pytest.raises(ValueError, match="existing quarantine capture failed verification"):
        _capture(source, captures)


def test_source_distinct_captures_cannot_alias_after_redaction(tmp_path: Path) -> None:
    source_a = _copy_verified_fixture(tmp_path, "source-a")
    source_b = _copy_verified_fixture(tmp_path, "source-b")
    with sqlite3.connect(source_b / "corvus.db") as connection:
        connection.execute(
            "UPDATE memories SET content = ? WHERE id = ?",
            (
                f"token={SECOND_CANARY}",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()

    captures = tmp_path / "quarantine"
    first = _capture(source_a, captures)
    second = _capture(source_b, captures)

    assert first.records_sha256 == second.records_sha256
    assert first.capture_id != second.capture_id
    assert first.path != second.path
    assert quarantine.verify_v1_quarantine(first.path) is True
    assert quarantine.verify_v1_quarantine(second.path) is True

    first_manifest = json.loads((first.path / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second.path / "manifest.json").read_text(encoding="utf-8"))
    assert first_manifest["source_database_sha256"] != second_manifest["source_database_sha256"]
    assert sorted(item.name for item in captures.iterdir()) == sorted(
        [first.capture_id, second.capture_id]
    )

    first_records = (first.path / "records.json").read_bytes()
    second_records = (second.path / "records.json").read_bytes()
    assert first_records == second_records
    assert SECOND_CANARY.encode() not in second_records


@pytest.mark.parametrize("relative_path", ("config/.env", "config/providers.yaml"))
def test_complete_raw_config_snapshot_prevents_redaction_equal_aliases(
    tmp_path: Path, relative_path: str
) -> None:
    source_a = _copy_verified_fixture(tmp_path, "source-a")
    source_b = _copy_verified_fixture(tmp_path, "source-b")
    changed = source_b / relative_path
    changed.write_text(
        changed.read_text(encoding="utf-8").replace(CANARY, SECOND_CANARY),
        encoding="utf-8",
    )

    captures = tmp_path / "quarantine"
    first = _capture(source_a, captures)
    second = _capture(source_b, captures)

    assert (first.path / "records.json").read_bytes() == (second.path / "records.json").read_bytes()
    assert first.records_sha256 == second.records_sha256
    assert first.capture_id != second.capture_id
    assert first.source_snapshot_sha256 != second.source_snapshot_sha256

    first_manifest = json.loads((first.path / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second.path / "manifest.json").read_text(encoding="utf-8"))
    assert first_manifest["source_database_sha256"] == second_manifest["source_database_sha256"]
    assert first_manifest["source_snapshot_sha256"] != second_manifest["source_snapshot_sha256"]
    assert CANARY not in json.dumps(first_manifest, sort_keys=True)
    assert SECOND_CANARY not in json.dumps(second_manifest, sort_keys=True)
    assert quarantine.verify_v1_quarantine(first.path) is True
    assert quarantine.verify_v1_quarantine(second.path) is True
