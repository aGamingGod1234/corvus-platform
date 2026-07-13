from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from corvus.delivery import DeliveryError, DeliveryManager


def _manager(tmp_path: Path) -> DeliveryManager:
    return DeliveryManager(
        tmp_path / "bundles",
        tmp_path / "backups",
        backup_key=Fernet.generate_key(),
    )


def _bundle(manager: DeliveryManager, destination: Path):
    return manager.package(
        uuid4(),
        destination,
        {"src/app.py": b"print('ok')\n"},
        {"passed": True},
        {"passed": True},
    )


def test_packaging_requires_passed_acceptance_and_tests(tmp_path: Path) -> None:
    destination = tmp_path / "project"
    destination.mkdir()
    manager = _manager(tmp_path)

    with pytest.raises(DeliveryError, match="block packaging"):
        manager.package(
            uuid4(),
            destination,
            {"app.py": b"pass\n"},
            {"passed": False},
            {"passed": True},
        )


def test_approval_is_bound_to_exact_manifest_and_files(tmp_path: Path) -> None:
    destination = tmp_path / "project"
    destination.mkdir()
    manager = _manager(tmp_path)
    bundle = _bundle(manager, destination)
    approval = manager.approve(bundle)

    altered = approval.model_copy(update={"manifest_digest": "0" * 64})

    with pytest.raises(DeliveryError, match="exact bundle"):
        manager.apply(bundle, altered)


def test_expired_approval_is_rejected(tmp_path: Path) -> None:
    destination = tmp_path / "project"
    destination.mkdir()
    manager = _manager(tmp_path)
    bundle = _bundle(manager, destination)
    approval = manager.approve(bundle).model_copy(
        update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
    )

    with pytest.raises(DeliveryError, match="expired"):
        manager.apply(bundle, approval)
