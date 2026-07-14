from __future__ import annotations

from corvus.mvp.openapi import build_openapi_document


def test_openapi_document_contains_connected_operator_routes() -> None:
    document = build_openapi_document()
    paths = document["paths"]

    assert "/api/projects" in paths
    assert "/api/projects/{project_id}/outcomes" in paths
    assert "/api/outcomes/{outcome_id}/workflows" in paths
    assert "/api/workflows/{workflow_id}/events" in paths
