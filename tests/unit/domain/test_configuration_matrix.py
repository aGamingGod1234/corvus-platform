from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from corvus.domain.client import ClientContext, ClientSurface
from corvus.domain.deployment import (
    AuthorityMode,
    AuthProfile,
    ConfigurationContractError,
    DeploymentProfile,
    NetworkProfile,
    StorageProfile,
    validate_configuration_combination,
)
from corvus.domain.execution import ExecutionKind, ExecutionPlacement
from corvus.domain.workspace import CollaborationMode, WorkspaceConfig


def test_deployment_profile_rejects_workspace_and_execution_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DeploymentProfile.model_validate(
            {
                "authority_mode": AuthorityMode.EMBEDDED_LOCAL,
                "auth_profile": AuthProfile.LOCAL_OS,
                "network_profile": NetworkProfile.IN_PROCESS,
                "storage_profile": StorageProfile.SQLITE,
                "enabled_adapters": {"cli"},
                "protocol_version": "v2alpha1",
                "collaboration_mode": "individual",
                "execution_placement_id": str(uuid4()),
            }
        )

    forbidden = {
        tuple(error["loc"])
        for error in exc_info.value.errors()
        if error["type"] == "extra_forbidden"
    }
    assert forbidden == {("collaboration_mode",), ("execution_placement_id",)}


def test_embedded_local_rejects_team_workspace_with_reason_code() -> None:
    profile = DeploymentProfile(
        authority_mode=AuthorityMode.EMBEDDED_LOCAL,
        auth_profile=AuthProfile.LOCAL_OS,
        network_profile=NetworkProfile.IN_PROCESS,
        storage_profile=StorageProfile.SQLITE,
        enabled_adapters={"cli"},
        protocol_version="v2alpha1",
    )
    workspace = WorkspaceConfig(collaboration_mode=CollaborationMode.TEAM)
    placement = ExecutionPlacement(
        kind=ExecutionKind.LOCAL_RUNNER,
        runner_id=uuid4(),
        sandbox_profile="default",
        data_policy_digest="a" * 64,
    )

    with pytest.raises(ConfigurationContractError) as exc_info:
        validate_configuration_combination(profile, workspace, placement)

    assert exc_info.value.reason_code == "embedded_local_requires_individual_workspace"


def test_client_context_cannot_grant_authority() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ClientContext.model_validate(
            {
                "surface": ClientSurface.CLI,
                "session_id": str(uuid4()),
                "origin": "local-terminal",
                "capabilities": ["workspace.admin"],
                "autonomy_ceiling": 5,
            }
        )

    forbidden = {
        tuple(error["loc"])
        for error in exc_info.value.errors()
        if error["type"] == "extra_forbidden"
    }
    assert forbidden == {("autonomy_ceiling",), ("capabilities",)}


def test_vendor_cloud_rejects_sqlite_with_reason_code() -> None:
    profile = DeploymentProfile(
        authority_mode=AuthorityMode.VENDOR_CLOUD,
        auth_profile=AuthProfile.OIDC,
        network_profile=NetworkProfile.NETWORK_TLS,
        storage_profile=StorageProfile.SQLITE,
        enabled_adapters={"web"},
        protocol_version="v2alpha1",
    )
    workspace = WorkspaceConfig(collaboration_mode=CollaborationMode.TEAM)
    placement = ExecutionPlacement(
        kind=ExecutionKind.CLOUD_WORKER,
        runner_id=uuid4(),
        sandbox_profile="default",
        data_policy_digest="b" * 64,
    )

    with pytest.raises(ConfigurationContractError) as exc_info:
        validate_configuration_combination(profile, workspace, placement)

    assert exc_info.value.reason_code == "vendor_cloud_requires_postgresql"


def test_embedded_local_rejects_cloud_worker_with_reason_code() -> None:
    profile = DeploymentProfile(
        authority_mode=AuthorityMode.EMBEDDED_LOCAL,
        auth_profile=AuthProfile.LOCAL_OS,
        network_profile=NetworkProfile.IN_PROCESS,
        storage_profile=StorageProfile.SQLITE,
        enabled_adapters={"cli"},
        protocol_version="v2alpha1",
    )
    workspace = WorkspaceConfig(collaboration_mode=CollaborationMode.INDIVIDUAL)
    placement = ExecutionPlacement(
        kind=ExecutionKind.CLOUD_WORKER,
        runner_id=uuid4(),
        sandbox_profile="default",
        data_policy_digest="c" * 64,
    )

    with pytest.raises(ConfigurationContractError) as exc_info:
        validate_configuration_combination(profile, workspace, placement)

    assert exc_info.value.reason_code == "embedded_local_requires_local_runner"
