from __future__ import annotations

import asyncio
import ctypes
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import cast


class TrustedProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrustedProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


type _ThreadOutcome = tuple[TrustedProcessResult | None, BaseException | None]


def path_is_link_or_reparse(path: Path) -> bool:
    """Return whether an existing path is a symlink or Windows reparse point."""

    try:
        metadata = path.lstat()
    except OSError:
        return False
    if path.is_symlink():
        return True
    reparse_flag = getattr(metadata, "st_file_attributes", 0) & 0x400
    return bool(reparse_flag)


def windows_system_directory() -> Path:
    """Resolve the OS-reported System32 directory without trusting PATH."""

    if os.name != "nt":
        raise TrustedProcessError("windows system directory is unavailable")
    buffer = ctypes.create_unicode_buffer(32_768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if length <= 0 or length >= len(buffer):
        raise TrustedProcessError("windows system directory is unavailable")
    directory = Path(buffer.value)
    try:
        canonical = directory.resolve(strict=True)
    except OSError as exc:
        raise TrustedProcessError("windows system directory is unavailable") from exc
    if not canonical.is_absolute() or not canonical.is_dir() or path_is_link_or_reparse(canonical):
        raise TrustedProcessError("windows system directory is unavailable")
    return canonical


def build_clean_process_environment(
    executable: Path,
    explicit: Mapping[str, str],
) -> dict[str, str]:
    """Build a minimal child environment without inheriting the parent environment."""

    executable_directory = executable.parent.resolve(strict=True)
    path_entries = [executable_directory]
    environment: dict[str, str] = {}
    if os.name == "nt":
        system_directory = windows_system_directory()
        windows_directory = system_directory.parent
        path_entries.extend((system_directory, windows_directory))
        environment.update(
            {
                "ComSpec": os.fspath(system_directory / "cmd.exe"),
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
                "SystemRoot": os.fspath(windows_directory),
                "WINDIR": os.fspath(windows_directory),
            }
        )
    else:
        for candidate in (Path("/usr/local/bin"), Path("/usr/bin"), Path("/bin")):
            if candidate.is_dir():
                path_entries.append(candidate.resolve(strict=True))
        environment.update({"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
    environment["PATH"] = os.pathsep.join(dict.fromkeys(os.fspath(item) for item in path_entries))
    environment.update(explicit)
    return environment


async def create_grouped_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    stdin: int | None,
) -> asyncio.subprocess.Process:
    """Spawn an argv directly in a separately terminable process group."""

    if os.name == "nt":
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=dict(env),
            stdin=stdin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=dict(env),
        stdin=stdin,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )


async def terminate_process_tree(
    process: asyncio.subprocess.Process,
    *,
    grace_seconds: float,
) -> bool:
    """Terminate a process tree and report only confirmed tree termination."""

    if process.returncode is not None:
        return True
    if os.name == "nt":
        confirmed = await _terminate_windows_process_tree(process)
        if confirmed:
            return True
        await _direct_process_cleanup(process)
        return False
    return await _terminate_posix_process_tree(process, grace_seconds=grace_seconds)


async def _terminate_posix_process_tree(
    process: asyncio.subprocess.Process,
    *,
    grace_seconds: float,
) -> bool:
    kill_process_group = cast(
        Callable[[int, int], None],
        os.killpg,  # type: ignore[attr-defined]
    )
    try:
        kill_process_group(process.pid, int(signal.SIGTERM))
    except ProcessLookupError:
        await process.wait()
        return True
    try:
        await asyncio.wait_for(process.wait(), timeout=grace_seconds)
        return True
    except TimeoutError:
        pass
    try:
        kill_process_group(
            process.pid,
            cast(int, signal.SIGKILL),  # type: ignore[attr-defined]
        )
    except ProcessLookupError:
        pass
    await process.wait()
    return True


async def _terminate_windows_process_tree(process: asyncio.subprocess.Process) -> bool:
    try:
        taskkill = (windows_system_directory() / "taskkill.exe").resolve(strict=True)
    except (OSError, TrustedProcessError):
        return False
    if not taskkill.is_file() or path_is_link_or_reparse(taskkill):
        return False
    try:
        killer = await asyncio.create_subprocess_exec(
            os.fspath(taskkill),
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=build_clean_process_environment(taskkill, {}),
        )
        return_code = await killer.wait()
    except (OSError, RuntimeError):
        return False
    if return_code != 0:
        return False
    await process.wait()
    return True


async def _direct_process_cleanup(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.kill()
    except ProcessLookupError:
        pass
    await process.wait()


async def _run(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    timeout_seconds: float,
    env: Mapping[str, str] | None,
) -> TrustedProcessResult:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise TrustedProcessError("trusted process timed out") from exc
    return TrustedProcessResult(
        returncode=int(process.returncode or 0),
        stdout=stdout,
        stderr=stderr,
    )


def _run_in_thread(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    timeout_seconds: float,
    env: Mapping[str, str] | None,
) -> TrustedProcessResult:
    outcomes: Queue[_ThreadOutcome] = Queue(maxsize=1)

    def target() -> None:
        try:
            result = asyncio.run(_run(argv, cwd=cwd, timeout_seconds=timeout_seconds, env=env))
        except BaseException as exc:
            outcomes.put((None, exc))
        else:
            outcomes.put((result, None))

    worker = threading.Thread(target=target, name="corvus-trusted-process", daemon=True)
    worker.start()
    worker.join(timeout_seconds + 5)
    if worker.is_alive():
        raise TrustedProcessError("trusted process worker did not terminate")
    result, error = outcomes.get_nowait()
    if error is not None:
        raise error
    if result is None:
        raise TrustedProcessError("trusted process returned no result")
    return result


def run_trusted_argv(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float = 60,
    env: Mapping[str, str] | None = None,
) -> TrustedProcessResult:
    arguments = tuple(argv)
    if not arguments or any(not item or "\0" in item for item in arguments):
        raise TrustedProcessError("trusted process arguments are invalid")
    executable = Path(arguments[0])
    if not executable.is_absolute() or not executable.is_file():
        raise TrustedProcessError("trusted process executable must be an absolute regular file")
    working_directory = cwd.expanduser().resolve(strict=False)
    if not working_directory.is_dir():
        raise TrustedProcessError("trusted process working directory is unavailable")
    if timeout_seconds <= 0:
        raise TrustedProcessError("trusted process timeout must be positive")
    normalized = (os.fspath(executable.resolve(strict=True)), *arguments[1:])
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            _run(
                normalized,
                cwd=working_directory,
                timeout_seconds=timeout_seconds,
                env=env,
            )
        )
    return _run_in_thread(
        normalized,
        cwd=working_directory,
        timeout_seconds=timeout_seconds,
        env=env,
    )
