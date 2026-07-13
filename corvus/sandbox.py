from __future__ import annotations

import asyncio
import io
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import docker
from docker.errors import DockerException

from corvus.models import SandboxPolicy


class SandboxError(RuntimeError):
    pass


def _docker_unavailable_detail() -> str:
    runtime = "Docker Desktop" if sys.platform in {"darwin", "win32"} else "Docker Engine"
    return (
        f"{runtime} is not reachable. Install or start it, then retry. "
        "Ordinary chat remains available; isolated /build is disabled."
    )


def _podman_unavailable_detail() -> str:
    runtime = (
        "Podman Desktop or its Podman machine" if sys.platform in {"darwin", "win32"} else "Podman"
    )
    return (
        f"{runtime} is not reachable. Install or start it, then retry. "
        "Ordinary chat remains available; isolated /build is disabled."
    )


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _archive_source(source: Path) -> bytes:
    if source.is_symlink() or source.is_junction():
        raise SandboxError(f"source symlink or junction rejected: {source}")
    if not source.is_dir():
        raise SandboxError(f"sandbox source is not a directory: {source}")
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for path in source.rglob("*"):
            if path.is_symlink() or path.is_junction():
                raise SandboxError(f"source symlink or junction rejected: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise SandboxError(f"unsupported source entry rejected: {path}")
            info = tar.gettarinfo(str(path), arcname=path.relative_to(source).as_posix())
            info.uid = 65534
            info.gid = 65534
            info.uname = "nobody"
            info.gname = "nogroup"
            info.mode &= 0o777
            with path.open("rb") as handle:
                tar.addfile(info, handle)
    return archive.getvalue()


class DockerSandbox:
    def __init__(
        self,
        image: str = "python:3.12-slim",
        policy: SandboxPolicy | None = None,
        client: Any | None = None,
    ) -> None:
        self.image = image
        self.policy = policy or SandboxPolicy()
        self.client = client
        self.container: Any | None = None

    @staticmethod
    def available() -> tuple[bool, str]:
        client: Any | None = None
        try:
            client = docker.from_env()
            client.ping()
            version_info = client.version()
            version = (
                version_info.get("Version", "unknown")
                if isinstance(version_info, dict)
                else "unknown"
            )
            return True, str(version)
        except DockerException:
            # Missing daemons and inaccessible sockets are expected optional-capability states.
            # Do not expose Docker SDK transport exceptions or host-specific pipe paths.
            return False, _docker_unavailable_detail()
        finally:
            if client is not None:
                try:
                    client.close()
                except (DockerException, OSError):
                    pass

    def container_options(self) -> dict[str, Any]:
        if self.policy.network_default:
            raise SandboxError(
                "direct worker networking is forbidden; configure the domain egress proxy"
            )
        return {
            "image": self.image,
            "command": ["sleep", "infinity"],
            "detach": True,
            "network_disabled": True,
            "read_only": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "mem_limit": f"{self.policy.memory_mb}m",
            "nano_cpus": int(self.policy.cpu_limit * 1_000_000_000),
            "pids_limit": self.policy.pids_limit,
            "tmpfs": {
                "/workspace": "rw,noexec,nosuid,size=1g",
                "/tmp": "rw,noexec,nosuid,size=256m",  # noqa: S108 - container tmpfs
            },
            "working_dir": "/workspace",
            "user": "65534:65534",
            "environment": {
                "HOME": "/tmp",  # noqa: S108 - container tmpfs
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            "labels": {"io.corvus.sandbox": "true"},
        }

    async def start(self) -> None:
        if self.container is not None:
            return
        if self.client is None:
            try:
                self.client = docker.from_env()
            except DockerException as exc:
                raise SandboxError("Docker is unavailable") from exc
        client = self.client

        def create_container() -> Any:
            return client.containers.run(**self.container_options())

        try:
            self.container = await asyncio.to_thread(create_container)
        except DockerException as exc:
            raise SandboxError("failed to create constrained Docker sandbox") from exc

    async def stage(self, source: Path) -> None:
        if self.container is None:
            raise SandboxError("sandbox has not started")
        archive_data = await asyncio.to_thread(self._archive_source, source)
        ok = await asyncio.to_thread(self.container.put_archive, "/workspace", archive_data)
        if not ok:
            raise SandboxError("Docker rejected source archive")

    @staticmethod
    def _archive_source(source: Path) -> bytes:
        return _archive_source(source)

    async def run(self, command: list[str], timeout_seconds: float = 300) -> CommandResult:
        if self.container is None:
            raise SandboxError("sandbox has not started")
        container = self.container

        def execute() -> Any:
            return container.exec_run(command, demux=True, workdir="/workspace", user="65534:65534")

        try:
            result = await asyncio.wait_for(asyncio.to_thread(execute), timeout_seconds)
        except TimeoutError:
            await asyncio.to_thread(self.container.kill)
            return CommandResult(
                exit_code=124, stdout="", stderr="command timed out", timed_out=True
            )
        stdout, stderr = result.output
        return CommandResult(
            exit_code=int(result.exit_code),
            stdout=(stdout or b"").decode(errors="replace"),
            stderr=(stderr or b"").decode(errors="replace"),
        )

    async def close(self) -> None:
        if self.container is not None:
            try:
                await asyncio.to_thread(self.container.remove, force=True)
            finally:
                self.container = None
        if self.client is not None:
            self.client.close()

    async def __aenter__(self) -> DockerSandbox:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


class PodmanSandbox:
    """A rootless-friendly Podman backend with Docker security parity.

    The backend intentionally uses the Podman CLI rather than its Docker-compatible
    socket. Every invocation is an argv vector (never a shell command), and source
    content is transferred as a validated tar stream over stdin instead of a bind mount.
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        policy: SandboxPolicy | None = None,
        executable: str | Path | None = None,
    ) -> None:
        self.image = image
        self.policy = policy or SandboxPolicy()
        self.executable = str(executable) if executable is not None else None
        self.container: str | None = None

    @staticmethod
    def available() -> tuple[bool, str]:
        executable = shutil.which("podman")
        if executable is None:
            return False, _podman_unavailable_detail()
        try:
            result = subprocess.run(  # noqa: S603 - executable was resolved with which()
                [executable, "info", "--format", "{{.Version.Version}}"],
                capture_output=True,
                check=False,
                timeout=10,
                text=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False, _podman_unavailable_detail()
        if result.returncode != 0:
            return False, _podman_unavailable_detail()
        return True, result.stdout.strip() or "unknown"

    def container_options(self) -> list[str]:
        if self.policy.network_default:
            raise SandboxError(
                "direct worker networking is forbidden; configure the domain egress proxy"
            )
        return [
            "--detach",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--read-only-tmpfs=false",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            f"--memory={self.policy.memory_mb}m",
            f"--cpus={self.policy.cpu_limit}",
            f"--pids-limit={self.policy.pids_limit}",
            "--tmpfs=/workspace:rw,noexec,nosuid,size=1g,uid=65534,gid=65534,mode=0700",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=256m,uid=65534,gid=65534,mode=0700",
            "--workdir=/workspace",
            "--user=65534:65534",
            "--env=HOME=/tmp",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            "--label=io.corvus.sandbox=true",
        ]

    def _resolve_executable(self) -> str:
        executable = self.executable or shutil.which("podman")
        if executable is None:
            raise SandboxError("Podman is unavailable")
        return executable

    async def _invoke(
        self,
        arguments: list[str],
        *,
        input_data: bytes | None = None,
        timeout_seconds: float = 60,
    ) -> CommandResult:
        executable = self._resolve_executable()
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *arguments,
                stdin=(
                    asyncio.subprocess.PIPE
                    if input_data is not None
                    else asyncio.subprocess.DEVNULL
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise SandboxError("Podman is unavailable") from exc
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input_data), timeout=timeout_seconds
            )
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            stdout, stderr = await process.communicate()
            return CommandResult(
                exit_code=124,
                stdout=stdout.decode(errors="replace"),
                stderr=(stderr.decode(errors="replace") or "Podman command timed out"),
                timed_out=True,
            )
        except asyncio.CancelledError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.communicate()
            raise
        returncode = process.returncode if process.returncode is not None else 1
        return CommandResult(
            exit_code=returncode,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )

    async def _remove(self, container: str) -> None:
        try:
            await self._invoke(["rm", "--force", "--time=0", container], timeout_seconds=30)
        except SandboxError:
            # Removal is best effort when the runtime itself has disappeared. The unique
            # name is never reused, so a later invocation cannot target another container.
            pass

    async def start(self) -> None:
        if self.container is not None:
            return
        container = f"corvus-{uuid4().hex}"
        # Track the generated name before invoking Podman so cancellation and partial
        # creation can only clean up this exact container.
        self.container = container
        try:
            result = await self._invoke(
                [
                    "run",
                    *self.container_options(),
                    f"--name={container}",
                    "--",
                    self.image,
                    "sleep",
                    "infinity",
                ],
                timeout_seconds=60,
            )
            if result.timed_out or result.exit_code != 0:
                raise SandboxError("failed to create constrained Podman sandbox")
        except (Exception, asyncio.CancelledError):
            try:
                await asyncio.shield(self._remove(container))
            finally:
                self.container = None
            raise

    async def stage(self, source: Path) -> None:
        if self.container is None:
            raise SandboxError("sandbox has not started")
        archive_data = await asyncio.to_thread(self._archive_source, source)
        result = await self._invoke(
            ["cp", "-", f"{self.container}:/workspace"],
            input_data=archive_data,
            timeout_seconds=300,
        )
        if result.timed_out or result.exit_code != 0:
            container = self.container
            await asyncio.shield(self._remove(container))
            self.container = None
            raise SandboxError("Podman rejected source archive")

    @staticmethod
    def _archive_source(source: Path) -> bytes:
        return _archive_source(source)

    async def run(self, command: list[str], timeout_seconds: float = 300) -> CommandResult:
        if self.container is None:
            raise SandboxError("sandbox has not started")
        if not command:
            raise SandboxError("sandbox command must not be empty")
        container = self.container
        result = await self._invoke(
            [
                "exec",
                "--user=65534:65534",
                "--workdir=/workspace",
                "--",
                container,
                *command,
            ],
            timeout_seconds=timeout_seconds,
        )
        if result.timed_out:
            await asyncio.shield(self._remove(container))
            self.container = None
            return CommandResult(
                exit_code=124,
                stdout=result.stdout,
                stderr="command timed out",
                timed_out=True,
            )
        if result.exit_code == 125:
            # Podman reserves 125 for engine/CLI errors. Its raw stderr can contain
            # host socket paths or runtime implementation details, so it is not evidence
            # produced by the sandboxed command and must not be persisted.
            return CommandResult(
                exit_code=125,
                stdout="",
                stderr="Podman failed to execute the sandbox command",
            )
        return result

    async def close(self) -> None:
        if self.container is None:
            return
        container = self.container
        try:
            await asyncio.shield(self._remove(container))
        finally:
            self.container = None

    async def __aenter__(self) -> PodmanSandbox:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
