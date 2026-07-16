from __future__ import annotations

from fastapi import APIRouter

from corvus.platform.api.dependencies import IdentityApiDependencies
from corvus.platform.api.identity import create_identity_router


def create_platform_router(
    dependencies: IdentityApiDependencies | None,
) -> APIRouter:
    router = APIRouter()
    router.include_router(create_identity_router(dependencies))
    return router
