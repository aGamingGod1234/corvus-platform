from __future__ import annotations

import sys
from pathlib import Path

import pytest

from corvus.safe_process import TrustedProcessError, run_trusted_argv


def test_trusted_process_runs_absolute_executable_without_a_shell(tmp_path: Path) -> None:
    result = run_trusted_argv(
        [sys.executable, "-c", "print('safe-process-ok')"],
        cwd=tmp_path,
        timeout_seconds=10,
    )

    assert result.returncode == 0
    assert result.stdout.decode().strip() == "safe-process-ok"
    assert result.stderr == b""


def test_trusted_process_rejects_path_lookup_and_missing_working_directory(tmp_path: Path) -> None:
    with pytest.raises(TrustedProcessError, match="absolute regular file"):
        run_trusted_argv(["python", "-V"], cwd=tmp_path)
    with pytest.raises(TrustedProcessError, match="working directory"):
        run_trusted_argv([sys.executable, "-V"], cwd=tmp_path / "missing")
