from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Queue


class TrustedProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrustedProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


type _ThreadOutcome = tuple[TrustedProcessResult | None, BaseException | None]


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
