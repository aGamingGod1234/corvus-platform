from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from corvus.mvp.core import CorvusService, DomainConflict, DomainNotFound
from corvus.mvp.models import EffectBinding, WorkItemDefinition

mvp_app = typer.Typer(help="Run the local Corvus M2-M11 hackathon MVP")
project_app = typer.Typer(help="Create and inspect MVP projects")
outcome_app = typer.Typer(help="Create versioned outcome contracts")
workflow_app = typer.Typer(help="Create and control durable workflows")
mvp_app.add_typer(project_app, name="project")
mvp_app.add_typer(outcome_app, name="outcome")
mvp_app.add_typer(workflow_app, name="workflow")

DatabaseOption = Annotated[Path, typer.Option("--database", help="MVP SQLite database")]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON")]


def _service(database: Path) -> CorvusService:
    return CorvusService.open(database.expanduser().resolve())


def _emit(value: Any, *, json_output: bool) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(value, ensure_ascii=False, sort_keys=True))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            typer.echo(f"{key}: {item}")
        return
    typer.echo(str(value))


def _fail(error: Exception) -> None:
    if isinstance(error, (DomainConflict, DomainNotFound, ValidationError, ValueError)):
        raise typer.BadParameter(str(error)) from error
    raise error


@project_app.command("create")
def project_create(
    name: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
    tenant_id: Annotated[str, typer.Option("--tenant-id")] = "local",
) -> None:
    try:
        project = _service(database).create_project(name=name, tenant_id=tenant_id)
    except Exception as error:
        _fail(error)
        return
    _emit(project, json_output=json_output)


@outcome_app.command("create")
def outcome_create(
    project_id: str,
    title: str,
    criterion: Annotated[list[str] | None, typer.Option("--criterion")] = None,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    try:
        outcome = _service(database).create_outcome(
            project_id=project_id,
            title=title,
            acceptance_criteria=criterion or (),
        )
    except Exception as error:
        _fail(error)
        return
    _emit(outcome, json_output=json_output)


@workflow_app.command("create")
def workflow_create(
    outcome_id: str,
    name: str,
    items_json: Annotated[str, typer.Option("--items-json")],
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    try:
        raw_items = json.loads(items_json)
        if not isinstance(raw_items, list):
            raise ValueError("items_json_must_be_an_array")
        definitions = tuple(WorkItemDefinition.model_validate(item) for item in raw_items)
        workflow = _service(database).create_workflow(
            outcome_id=outcome_id,
            name=name,
            items=definitions,
        )
    except Exception as error:
        _fail(error)
        return
    _emit(workflow, json_output=json_output)


@workflow_app.command("start")
def workflow_start(
    workflow_id: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    try:
        workflow = _service(database).start_workflow(workflow_id)
    except Exception as error:
        _fail(error)
        return
    _emit(workflow, json_output=json_output)


@workflow_app.command("status")
def workflow_status(
    workflow_id: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    try:
        workflow = _service(database).get_workflow(workflow_id)
    except Exception as error:
        _fail(error)
        return
    _emit(workflow, json_output=json_output)


@workflow_app.command("run-next")
def workflow_run_next(
    workflow_id: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
    worker_id: Annotated[str, typer.Option("--worker-id")] = "local-cli",
) -> None:
    try:
        item = _service(database).run_next(workflow_id, worker_id=worker_id)
        if item is None:
            raise DomainConflict("no_ready_work_item")
    except Exception as error:
        _fail(error)
        return
    _emit(item, json_output=json_output)


@workflow_app.command("pause")
def workflow_pause(
    workflow_id: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    _emit(_service(database).pause_workflow(workflow_id), json_output=json_output)


@workflow_app.command("resume")
def workflow_resume(
    workflow_id: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    _emit(_service(database).start_workflow(workflow_id), json_output=json_output)


@workflow_app.command("cancel")
def workflow_cancel(
    workflow_id: str,
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    _emit(_service(database).cancel_workflow(workflow_id), json_output=json_output)


@mvp_app.command("demo")
def demo(
    database: DatabaseOption = Path("corvus-mvp.sqlite3"),
    json_output: JsonOption = False,
) -> None:
    """Execute the durable local workflow, approval, budget, and restart path."""
    service = _service(database)
    project = service.create_project(name="Corvus hackathon demo")
    service.set_budget(project.id, limit_units=10)
    outcome = service.create_outcome(
        project_id=project.id,
        title="Complete the local demo",
        acceptance_criteria=("workflow and approved effect persist across restart",),
    )
    workflow = service.create_workflow(
        outcome_id=outcome.id,
        name="Local end-to-end demo",
        items=(
            WorkItemDefinition(key="prepare", title="Prepare deterministic artifact"),
            WorkItemDefinition(
                key="apply",
                title="Apply approved local effect",
                depends_on=("prepare",),
                cost_units=4,
                requires_approval=True,
                effect=EffectBinding(
                    kind="filesystem",
                    target="demo/output.txt",
                    payload={"content": "approved"},
                ),
            ),
        ),
    )
    service.start_workflow(workflow.id)
    service.run_next(workflow.id, worker_id="demo-worker")
    service.run_next(workflow.id, worker_id="demo-worker")
    effect = service.list_effects(workflow.id)[0]
    service.approve_effect(effect.id, actor_id="local-user")
    service.run_next(workflow.id, worker_id="demo-worker")
    restarted = _service(database)
    final_workflow = restarted.get_workflow(workflow.id)
    final_effect = restarted.get_effect(effect.id)
    budget = restarted.get_budget(project.id)
    _emit(
        {
            "project_id": project.id,
            "outcome_id": outcome.id,
            "workflow_id": workflow.id,
            "workflow_status": final_workflow.status.value,
            "effect_id": effect.id,
            "effect_execution_count": final_effect.execution_count,
            "budget": {
                "available": budget.available_units,
                "reserved": budget.reserved_units,
                "settled": budget.settled_units,
            },
            "events": len(restarted.list_events(workflow.id)),
            "restart_verified": final_workflow.status.value == "succeeded",
        },
        json_output=json_output,
    )
