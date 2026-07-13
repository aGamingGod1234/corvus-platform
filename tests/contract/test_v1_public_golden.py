from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any

from typer.main import get_command
from typer.testing import CliRunner

from corvus import __version__
from corvus.cli import app
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
    Skill,
    SkillVersion,
)
from corvus.onboarding import OnboardingChoices, OnboardingState

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "v1"
CONTRACT_PATH = FIXTURE_ROOT / "public_contract.json"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


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
        parameter_type = getattr(parameter.type, "name", parameter.type.__class__.__name__)
        parameters.append(
            {
                "default": _json_value(parameter.default),
                "multiple": bool(getattr(parameter, "multiple", False)),
                "name": parameter.name,
                "nargs": parameter.nargs,
                "options": sorted(
                    [
                        *getattr(parameter, "opts", ()),
                        *getattr(parameter, "secondary_opts", ()),
                    ]
                ),
                "required": parameter.required,
                "type": parameter_type,
            }
        )
    current = {
        "help": command.help or "",
        "parameters": parameters,
        "path": list(path),
    }
    contracts = [current]
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


def build_public_contract(tmp_path: Path, monkeypatch) -> dict[str, object]:
    monkeypatch.setenv("CORVUS_HOME", str(tmp_path / "corvus-home"))
    result = CliRunner().invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output
    doctor = json.loads(result.stdout)
    schemas = {
        model.__name__: model.model_json_schema()
        for model in (
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
    }
    return {
        "autonomy": {item.name: item.value for item in AutonomyLevel},
        "commands": _command_contract(get_command(app), ("corvus",)),
        "database": {
            table: sorted(columns) for table, columns in sorted(V1_REQUIRED_COLUMNS.items())
        },
        "doctor_json_shape": _shape(doctor),
        "schemas": schemas,
        "version": __version__,
    }


def test_v1_public_contract_matches_hashed_golden(tmp_path: Path, monkeypatch) -> None:
    fixture_bytes = CONTRACT_PATH.read_bytes()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == {
        "algorithm": "sha256",
        "files": {"public_contract.json": hashlib.sha256(fixture_bytes).hexdigest()},
        "schema_version": 1,
    }
    expected = json.loads(fixture_bytes)
    assert build_public_contract(tmp_path, monkeypatch) == expected
