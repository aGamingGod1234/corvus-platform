"""Utilities for sealing and transporting audit history heads."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuditHistoryHeads(BaseModel):
    """Sealed history roots used to bind rollback-sensitive audit ledgers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_history_head: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_binding_history_head: str = Field(pattern=r"^[0-9a-f]{64}$")
