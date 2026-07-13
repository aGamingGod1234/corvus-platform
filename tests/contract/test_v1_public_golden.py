from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from typer.main import get_command
from typer.testing import CliRunner

from corvus import __version__
from corvus.cli import app
from corvus.config import CorvusPaths
from corvus.conversations import (
    ConversationEvent,
    ConversationLimits,
    ConversationMessage,
    ConversationSnapshot,
    SubagentPolicy,
)
from corvus.database import V1_REQUIRED_COLUMNS
from corvus.models import (
    Artifact,
    ArtifactManifest,
    AutonomyLevel,
    Checkpoint,
    DeliveryBundle,
    MemoryRecord,
    ModelProvider,
    Policy,
    RunEvent,
    RunPhase,
    Skill,
    SkillVersion,
)
from corvus.onboarding import OnboardingChoices, OnboardingState
from corvus.store import TraceStore

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "v1"
CONTRACT_PATH = FIXTURE_ROOT / "public_contract.json"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"

_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_DIGEST_RE = re.compile(r"\b[0-9a-f]{64}\b")
_TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")


def _normalize_text(text: str, root: Path) -> str:
    normalized = text
    normalized = normalized.replace("\\", "/")
    normalized = normalized.replace(str(root).replace("\\", "/"), "<corvus-home>")
    normalized = normalized.replace(str(Path.home()).replace("\\", "/"), "<user-home>")
    normalized = _UUID_RE.sub("<uuid>", normalized)
    normalized = _DIGEST_RE.sub("<digest>", normalized)
    normalized = _TIMESTAMP_RE.sub("<timestamp>", normalized)
    return normalized.strip()


def _normalize_payload(value: object, root: Path) -> object:
    if isinstance(value, dict):
        return {str(key): _normalize_payload(item, root) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize_payload(item, root) for item in value]
    if isinstance(value, str):
        return _normalize_text(value, root)
    if isinstance(value, Enum):
        return _normalize_payload(value.value, root)
    if isinstance(value, Path):
        return _normalize_text(value.as_posix(), root)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda x: str(x[0]))
        }
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return value.__class__.__name__


def _command_contract(command: Any, path: tuple[str, ...]) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    for parameter in command.params:
        parameters.append(
            {
                "default": _json_value(parameter.default),
                "multiple": bool(getattr(parameter, "multiple", False)),
                "name": parameter.name,
                "nargs": parameter.nargs,
                "options": sorted(
                    [*getattr(parameter, "opts", ()), *getattr(parameter, "secondary_opts", ())]
                ),
                "required": parameter.required,
                "type": getattr(parameter.type, "name", parameter.type.__class__.__name__),
            }
        )
    contracts = [
        {
            "help": command.help or "",
            "parameters": parameters,
            "path": list(path),
        }
    ]
    if hasattr(command, "commands"):
        for name, child in sorted(command.commands.items()):
            contracts.extend(_command_contract(child, (*path, name)))
    return contracts


def _shape(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(item) for item in value]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _run_command_golden(
    corvus_home: Path, *argv: str, input_data: str | None = None
) -> dict[str, Any]:
    result = CliRunner().invoke(
        app, list(argv), input=input_data, env={"CORVUS_HOME": str(corvus_home)}
    )
    raw_output = result.output or ""
    if "--json" in argv:
        parsed_output: object
        if raw_output.strip():
            try:
                parsed_output = _normalize_payload(json.loads(raw_output), corvus_home)
            except json.JSONDecodeError:
                parsed_output = [
                    _normalize_payload(json.loads(raw), corvus_home)
                    for raw in raw_output.splitlines()
                    if raw.strip()
                ]
        else:
            parsed_output = []
    else:
        parsed_output = _normalize_text(raw_output, corvus_home)
    return {
        "command": [_normalize_text(argument, corvus_home) for argument in argv],
        "exit_code": result.exit_code,
        "output": parsed_output,
    }


def _build_trace_subject(corvus_home: Path) -> UUID:
    store = TraceStore(CorvusPaths(corvus_home).db)
    run_id = uuid4()
    store.append(
        run_id,
        "run.created",
        RunPhase.UNDERSTAND,
        {
            "prompt": "golden contract command",
            "project": str(corvus_home / "project"),
            "autonomy": 3,
            "sandbox_requested": "auto",
        },
    )
    store.append(
        run_id,
        "run.blocked",
        RunPhase.BLOCKED,
        {
            "reason": "contract fixture sandbox guard",
            "sandbox_backend": "none",
            "host_writes": False,
        },
    )
    return run_id


def _command_golden_matrix(corvus_home: Path) -> list[dict[str, Any]]:
    trace_run_id = _build_trace_subject(corvus_home)
    return [
        _run_command_golden(corvus_home, "doctor", "--json"),
        _run_command_golden(corvus_home, "model", "list"),
        _run_command_golden(corvus_home, "model", "status", "default"),
        _run_command_golden(corvus_home, "memory", "list", "00000000-0000-0000-0000-000000000000"),
        _run_command_golden(corvus_home, "skills", "list"),
        _run_command_golden(corvus_home, "trace", "--json", str(trace_run_id)),
        _run_command_golden(corvus_home, "chat", "--json", "golden contract prompt"),
        _run_command_golden(
            corvus_home, "review", "00000000-0000-0000-0000-000000000000", "--json"
        ),
        _run_command_golden(corvus_home, "--version"),
    ]


def build_public_contract(corvus_home: Path) -> dict[str, object]:
    doctor_golden = _run_command_golden(corvus_home, "doctor", "--json")
    doctor_json = doctor_golden["output"] if isinstance(doctor_golden["output"], dict) else {}
    schema_models = (
        Policy,
        OnboardingChoices,
        OnboardingState,
        ModelProvider,
        MemoryRecord,
        SkillVersion,
        Skill,
        ConversationLimits,
        SubagentPolicy,
        ConversationMessage,
        ConversationEvent,
        ConversationSnapshot,
        RunEvent,
        DeliveryBundle,
        Artifact,
        ArtifactManifest,
        Checkpoint,
    )
    return {
        "autonomy": {item.name: item.value for item in AutonomyLevel},
        "commands": _command_contract(get_command(app), ("corvus",)),
        "command_goldens": _command_golden_matrix(corvus_home),
        "database": {
            table: sorted(columns) for table, columns in sorted(V1_REQUIRED_COLUMNS.items())
        },
        "doctor_json_shape": _shape(doctor_json),
        "schemas": {model.__name__: model.model_json_schema() for model in schema_models},
        "version": __version__,
    }


def test_v1_public_contract_matches_hashed_golden(tmp_path: Path) -> None:
    corvus_home = tmp_path / "corvus-home"
    fixture_bytes = CONTRACT_PATH.read_bytes()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == {
        "algorithm": "sha256",
        "files": {"public_contract.json": hashlib.sha256(fixture_bytes).hexdigest()},
        "schema_version": 1,
    }
    expected = json.loads(fixture_bytes)
    assert build_public_contract(corvus_home) == expected
