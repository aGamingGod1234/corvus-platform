from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from corvus.cli import app

runner = CliRunner()


def test_mvp_demo_runs_complete_restart_safe_path(tmp_path: Path) -> None:
    database = tmp_path / "corvus.sqlite3"

    result = runner.invoke(
        app,
        ["mvp", "demo", "--database", str(database), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["workflow_status"] == "succeeded"
    assert payload["effect_execution_count"] == 1
    assert payload["budget"] == {"available": 6, "reserved": 0, "settled": 4}
    assert payload["restart_verified"] is True
    assert database.is_file()


def test_mvp_project_create_uses_same_sqlite_core(tmp_path: Path) -> None:
    database = tmp_path / "corvus.sqlite3"

    result = runner.invoke(
        app,
        ["mvp", "project", "create", "CLI project", "--database", str(database), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["name"] == "CLI project"
    assert payload["tenant_id"] == "local"


def test_mvp_cli_manages_outcome_and_workflow_through_application_service(
    tmp_path: Path,
) -> None:
    database = tmp_path / "corvus.sqlite3"
    common = ["--database", str(database), "--json"]
    project_result = runner.invoke(app, ["mvp", "project", "create", "Managed", *common])
    project_id = json.loads(project_result.stdout)["id"]

    outcome_result = runner.invoke(
        app,
        ["mvp", "outcome", "create", project_id, "Managed outcome", "--criterion", "done", *common],
    )
    assert outcome_result.exit_code == 0, outcome_result.output
    outcome_id = json.loads(outcome_result.stdout)["id"]
    definitions = json.dumps(
        [
            {"key": "first", "title": "First"},
            {"key": "second", "title": "Second", "depends_on": ["first"]},
        ]
    )
    workflow_result = runner.invoke(
        app,
        [
            "mvp",
            "workflow",
            "create",
            outcome_id,
            "Managed workflow",
            "--items-json",
            definitions,
            *common,
        ],
    )
    assert workflow_result.exit_code == 0, workflow_result.output
    workflow_id = json.loads(workflow_result.stdout)["id"]

    assert runner.invoke(app, ["mvp", "workflow", "start", workflow_id, *common]).exit_code == 0
    first = runner.invoke(app, ["mvp", "workflow", "run-next", workflow_id, *common])
    second = runner.invoke(app, ["mvp", "workflow", "run-next", workflow_id, *common])
    assert json.loads(first.stdout)["key"] == "first"
    assert json.loads(second.stdout)["key"] == "second"
    status = runner.invoke(app, ["mvp", "workflow", "status", workflow_id, *common])
    assert json.loads(status.stdout)["status"] == "succeeded"
