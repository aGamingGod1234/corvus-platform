from __future__ import annotations

import asyncio
import ctypes
import os
import signal
import subprocess  # nosec B404
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
_POSIX_SIGKILL_NUMBER = 9


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
    windows_loader = getattr(ctypes, "windll", None)
    if windows_loader is None:
        raise TrustedProcessError("windows system directory is unavailable")
    length = windows_loader.kernel32.GetSystemDirectoryW(buffer, len(buffer))
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
        process_group_flag = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        no_window_flag = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=dict(env),
            stdin=stdin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=process_group_flag | no_window_flag,
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

    if os.name == "nt":
        if process.returncode is not None:
            return True
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
    process_group_kill = getattr(os, "killpg", None)
    if process_group_kill is None:
        raise TrustedProcessError("POSIX process groups are unavailable")
    kill_process_group = cast(Callable[[int, int], None], process_group_kill)
    process_group_id = process.pid
    if not _posix_process_group_exists(process_group_id, kill_process_group):
        return await _confirm_posix_leader_reaped(process, grace_seconds=grace_seconds)
    try:
        kill_process_group(process_group_id, int(signal.SIGTERM))
    except ProcessLookupError:
        return await _confirm_posix_leader_reaped(process, grace_seconds=grace_seconds)
    if await _wait_for_posix_group_absence(
        process_group_id,
        kill_process_group,
        timeout_seconds=grace_seconds,
    ):
        return await _confirm_posix_leader_reaped(process, grace_seconds=grace_seconds)
    try:
        kill_process_group(
            process_group_id,
            _POSIX_SIGKILL_NUMBER,
        )
    except ProcessLookupError:
        return await _confirm_posix_leader_reaped(process, grace_seconds=grace_seconds)
    if not await _wait_for_posix_group_absence(
        process_group_id,
        kill_process_group,
        timeout_seconds=grace_seconds,
    ):
        return False
    return await _confirm_posix_leader_reaped(process, grace_seconds=grace_seconds)


def _posix_process_group_exists(
    process_group_id: int,
    kill_process_group: Callable[[int, int], None],
) -> bool:
    try:
        kill_process_group(process_group_id, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


async def _wait_for_posix_group_absence(
    process_group_id: int,
    kill_process_group: Callable[[int, int], None],
    *,
    timeout_seconds: float,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        if not _posix_process_group_exists(process_group_id, kill_process_group):
            return True
        await asyncio.sleep(min(0.05, timeout_seconds))
    return not _posix_process_group_exists(process_group_id, kill_process_group)


async def _confirm_posix_leader_reaped(
    process: asyncio.subprocess.Process,
    *,
    grace_seconds: float,
) -> bool:
    if process.returncode is not None:
        return True
    try:
        await asyncio.wait_for(process.wait(), timeout=grace_seconds)
    except TimeoutError:
        return False
    return True


async def _terminate_windows_process_tree(process: asyncio.subprocess.Process) -> bool:
    before = _windows_process_snapshot()
    observed = (
        {process.pid, *_windows_descendant_pids(process.pid, before)}
        if before is not None
        else None
    )
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
    if return_code == 0:
        await process.wait()
        return True
    if process.returncode is None or observed is None:
        return False
    after = _windows_process_snapshot()
    if after is None:
        return False
    current_pids = set(after)
    newly_observed = _windows_descendant_pids(process.pid, after)
    return observed.isdisjoint(current_pids) and not newly_observed


def _windows_descendant_pids(root_pid: int, processes: Mapping[int, int]) -> set[int]:
    descendants: set[int] = set()
    frontier = {root_pid}
    while frontier:
        next_frontier = {
            pid
            for pid, parent_pid in processes.items()
            if parent_pid in frontier and pid not in descendants and pid != root_pid
        }
        descendants.update(next_frontier)
        frontier = next_frontier
    return descendants


def _windows_process_snapshot() -> dict[int, int] | None:
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            return None
        kernel32 = win_dll("kernel32", use_last_error=True)

        class ProcessEntry32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        create_snapshot = kernel32.CreateToolhelp32Snapshot
        create_snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        create_snapshot.restype = wintypes.HANDLE
        process_first = kernel32.Process32FirstW
        process_first.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W))
        process_first.restype = wintypes.BOOL
        process_next = kernel32.Process32NextW
        process_next.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W))
        process_next.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        snapshot = create_snapshot(0x00000002, 0)
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or snapshot == invalid_handle:
            return None
        try:
            entry = ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(entry)
            if not process_first(snapshot, ctypes.byref(entry)):
                return None
            processes: dict[int, int] = {}
            while True:
                processes[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                if not process_next(snapshot, ctypes.byref(entry)):
                    break
            return processes
        finally:
            close_handle(snapshot)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


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
    max_output_bytes: int,
) -> TrustedProcessResult:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout = bytearray()
    stderr = bytearray()
    total = [0]

    async def read_stream(
        reader: asyncio.StreamReader | None,
        destination: bytearray,
    ) -> None:
        if reader is None:
            raise TrustedProcessError("trusted process pipes are unavailable")
        while True:
            chunk = await reader.read(64 * 1024)
            if not chunk:
                return
            total[0] += len(chunk)
            if total[0] > max_output_bytes:
                raise TrustedProcessError("trusted process exceeded its output limit")
            destination.extend(chunk)

    tasks = (
        asyncio.create_task(read_stream(process.stdout, stdout)),
        asyncio.create_task(read_stream(process.stderr, stderr)),
        asyncio.create_task(process.wait()),
    )
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout_seconds)
    except TimeoutError as exc:
        await _direct_process_cleanup(process)
        raise TrustedProcessError("trusted process timed out") from exc
    except BaseException:
        await _direct_process_cleanup(process)
        raise
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return TrustedProcessResult(
        returncode=int(process.returncode or 0),
        stdout=bytes(stdout),
        stderr=bytes(stderr),
    )


def _run_in_thread(
    argv: tuple[str, ...],
    *,
    cwd: Path,
    timeout_seconds: float,
    env: Mapping[str, str] | None,
    max_output_bytes: int,
) -> TrustedProcessResult:
    outcomes: Queue[_ThreadOutcome] = Queue(maxsize=1)

    def target() -> None:
        try:
            result = asyncio.run(
                _run(
                    argv,
                    cwd=cwd,
                    timeout_seconds=timeout_seconds,
                    env=env,
                    max_output_bytes=max_output_bytes,
                )
            )
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
    max_output_bytes: int = 2 * 1024 * 1024,
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
    if max_output_bytes <= 0:
        raise TrustedProcessError("trusted process output limit must be positive")
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
                max_output_bytes=max_output_bytes,
            )
        )
    return _run_in_thread(
        normalized,
        cwd=working_directory,
        timeout_seconds=timeout_seconds,
        env=env,
        max_output_bytes=max_output_bytes,
    )
