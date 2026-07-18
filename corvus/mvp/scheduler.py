from __future__ import annotations

from datetime import UTC, datetime

from corvus.mvp.run_coordinator import RunCoordinator, RunCoordinatorConflict
from corvus.mvp.run_models import RunRecord, StartRunRequest
from corvus.mvp.schedules import ScheduleClaim, ScheduleRecord, ScheduleStore


class LocalScheduler:
    def __init__(self, schedules: ScheduleStore, runs: RunCoordinator) -> None:
        self.schedules = schedules
        self.runs = runs

    async def tick(self, now: datetime | None = None) -> tuple[str, ...]:
        run_ids: list[str] = []
        for claim in self.schedules.claim_due(now or datetime.now(UTC)):
            try:
                run = await self._start_claim(claim)
            except RunCoordinatorConflict:
                self.schedules.attach_run(claim, "", "skipped")
                continue
            self.schedules.attach_run(claim, run.id)
            run_ids.append(run.id)
        return tuple(run_ids)

    async def run_now(self, tenant_id: str, schedule_id: str) -> RunRecord:
        schedule = self.schedules.get(tenant_id, schedule_id)
        if schedule.status == "archived":
            raise RunCoordinatorConflict("schedule_archived")
        return await self.runs.start(tenant_id, self._request(schedule, occurrence_key=None))

    async def _start_claim(self, claim: ScheduleClaim) -> RunRecord:
        occurrence_key = f"{claim.schedule.revision_id}:{claim.scheduled_for.isoformat()}"
        return await self.runs.start(
            claim.schedule.tenant_id,
            self._request(claim.schedule, occurrence_key=occurrence_key),
        )

    @staticmethod
    def _request(schedule: ScheduleRecord, occurrence_key: str | None) -> StartRunRequest:
        return StartRunRequest(
            repository_id=schedule.repository_id,
            task=schedule.task,
            provider="codex",
            model=schedule.model,
            effort=schedule.effort,
            mode=schedule.mode,
            safety_digest=schedule.safety_digest,
            skill_version_id=schedule.skill_version_id,
            schedule_id=schedule.id if occurrence_key is not None else None,
            occurrence_key=occurrence_key,
            output_policy=schedule.output_policy,
        )
