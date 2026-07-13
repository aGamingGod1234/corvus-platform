import pytest

from corvus.cli import SandboxOption, resolve_sandbox_runtime
from corvus.models import SandboxPolicy
from corvus.sandbox import DockerSandbox, PodmanSandbox, SandboxError


def test_docker_options_are_offline_read_only_and_non_root() -> None:
    options = DockerSandbox().container_options()

    assert options["network_disabled"] is True
    assert options["read_only"] is True
    assert options["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in options["security_opt"]
    assert options["user"] == "65534:65534"
    assert set(options["tmpfs"]) == {"/workspace", "/tmp"}  # noqa: S108


def test_podman_options_match_the_fail_closed_contract() -> None:
    options = PodmanSandbox().container_options()

    for required in (
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65534:65534",
    ):
        assert required in options


def test_direct_worker_networking_is_rejected() -> None:
    policy = SandboxPolicy(network_default=True)

    with pytest.raises(SandboxError, match="egress proxy"):
        DockerSandbox(policy=policy).container_options()
    with pytest.raises(SandboxError, match="egress proxy"):
        PodmanSandbox(policy=policy).container_options()


def test_unavailable_explicit_sandbox_never_falls_back_to_host() -> None:
    runtime = resolve_sandbox_runtime(
        SandboxOption.DOCKER,
        docker_status=(False, "not running"),
        podman_status=(True, "available"),
    )

    assert runtime.backend == "none"
    assert runtime.factory is None
    assert runtime.available is False
