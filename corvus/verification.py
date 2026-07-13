from __future__ import annotations

import time
from uuid import UUID

from corvus.models import CriterionStatus, Evidence, VerificationResult
from corvus.sandbox import DockerSandbox
from corvus.security import SecretRedactor
from corvus.store import ArtifactStore


class VerificationEngine:
    def __init__(self, artifacts: ArtifactStore, redactor: SecretRedactor | None = None) -> None:
        self.artifacts = artifacts
        self.redactor = redactor or SecretRedactor()

    async def command(
        self,
        sandbox: DockerSandbox,
        trace_id: UUID,
        criterion_id: str,
        command: list[str],
        timeout_seconds: float = 300,
    ) -> VerificationResult:
        started = time.monotonic()
        result = await sandbox.run(command, timeout_seconds)
        output = self.redactor.redact(result.stdout + result.stderr)
        digest, _ = self.artifacts.put(output.encode())
        evidence = Evidence(
            artifact_digest=digest,
            media_type="text/plain",
            description=f"Command {' '.join(command)} exited {result.exit_code}",
            trace_id=trace_id,
        )
        return VerificationResult(
            criterion_id=criterion_id,
            status=CriterionStatus.PASSED if result.exit_code == 0 else CriterionStatus.FAILED,
            method="sandbox command",
            evidence=[evidence],
            output=output,
            duration_seconds=time.monotonic() - started,
        )

    @staticmethod
    def completion_allowed(results: list[VerificationResult], required: set[str]) -> bool:
        passed = {item.criterion_id for item in results if item.status == CriterionStatus.PASSED}
        return required <= passed
