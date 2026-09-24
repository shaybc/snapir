from __future__ import annotations

import sqlite3

from models.registry_models import ArtifactReuseDecision
from tools.artifact_registry_tools.component_registry import get_component


def resolve_component_reuse(
    conn: sqlite3.Connection,
    artifact_kind: str,
    logical_id: str,
    source_hash: str,
    channel: str,
    target_language: str,
    schema_version: str = "v1",
) -> ArtifactReuseDecision:
    existing = get_component(
        conn,
        artifact_kind=artifact_kind,
        logical_id=logical_id,
        target_language=target_language,
        schema_version=schema_version,
    )
    if existing is None:
        return ArtifactReuseDecision(should_reuse=False, reason="not_in_registry")
    if existing.source_hash != source_hash:
        return ArtifactReuseDecision(
            should_reuse=False,
            component_id=existing.component_id,
            generated_path=existing.generated_path,
            reason="hash_mismatch",
        )
    if existing.status.value != "validated":
        return ArtifactReuseDecision(
            should_reuse=False,
            component_id=existing.component_id,
            generated_path=existing.generated_path,
            reason="status_invalid",
        )
    return ArtifactReuseDecision(
        should_reuse=True,
        component_id=existing.component_id,
        generated_path=existing.generated_path,
        reason="validated",
    )
