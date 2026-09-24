from __future__ import annotations

import subprocess
from pathlib import Path

from models.common_models.common import TargetLanguage
from models.conversion_models.conversion import ConversionStatus
from models.registry_models import ComponentRegistryRecord
from tools.artifact_registry_tools.component_registry import (
    get_component,
    increment_used_by_validated,
    mark_validated,
    register_component,
)
from tools.artifact_registry_tools.promotion import promote_to_common_lib
from tools.artifact_registry_tools.reuse_resolver import resolve_component_reuse
from tools.state_store_tools.db import create_all_tables, get_connection


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def component_record(
    *,
    source_hash: str = "hash-1",
    status: ConversionStatus = ConversionStatus.pending,
    generated_path: str = "generated/Shared.java",
    used_by_validated_operations: int = 0,
) -> ComponentRegistryRecord:
    return ComponentRegistryRecord(
        component_id="component-1",
        artifact_kind="ibm_java",
        logical_id="SharedImpl",
        source_path="src/SharedImpl.java",
        source_hash=source_hash,
        target_language=TargetLanguage.java,
        artifact_schema_version="v1",
        generated_path=generated_path,
        status=status,
        used_by_operations=["OpA", "OpB"],
        used_by_validated_operations=used_by_validated_operations,
    )


def test_cache_miss_on_empty_registry_returns_not_in_registry():
    conn = memory_conn()

    decision = resolve_component_reuse(
        conn,
        artifact_kind="ibm_java",
        logical_id="SharedImpl",
        source_hash="hash-1",
        channel="INTERNET",
        target_language="java",
    )

    assert decision.should_reuse is False
    assert decision.reason == "not_in_registry"


def test_validated_matching_component_returns_cache_hit():
    conn = memory_conn()
    register_component(conn, component_record())
    mark_validated(conn, "component-1")

    decision = resolve_component_reuse(
        conn,
        artifact_kind="ibm_java",
        logical_id="SharedImpl",
        source_hash="hash-1",
        channel="INTERNET",
        target_language="java",
    )

    assert decision.should_reuse is True
    assert decision.reason == "validated"
    assert decision.component_id == "component-1"
    assert decision.generated_path == "generated/Shared.java"


def test_hash_mismatch_returns_hash_mismatch():
    conn = memory_conn()
    register_component(conn, component_record(status=ConversionStatus.validated))

    decision = resolve_component_reuse(
        conn,
        artifact_kind="ibm_java",
        logical_id="SharedImpl",
        source_hash="hash-2",
        channel="INTERNET",
        target_language="java",
    )

    assert decision.should_reuse is False
    assert decision.reason == "hash_mismatch"


def test_status_not_validated_returns_status_invalid():
    conn = memory_conn()
    register_component(conn, component_record(status=ConversionStatus.converted))

    decision = resolve_component_reuse(
        conn,
        artifact_kind="ibm_java",
        logical_id="SharedImpl",
        source_hash="hash-1",
        channel="INTERNET",
        target_language="java",
    )

    assert decision.should_reuse is False
    assert decision.reason == "status_invalid"


def test_component_registry_validated_usage_count_increment():
    conn = memory_conn()
    register_component(conn, component_record())
    increment_used_by_validated(conn, "component-1")

    record = get_component(conn, "ibm_java", "SharedImpl", "java", "v1")

    assert record is not None
    assert record.used_by_validated_operations == 1


def test_promote_to_common_lib_with_one_validated_usage_does_not_promote(tmp_path):
    conn = memory_conn()
    source_file = tmp_path / "generated" / "Shared.java"
    source_file.parent.mkdir()
    source_file.write_text("class Shared {}\n")
    register_component(
        conn,
        component_record(
            generated_path=str(source_file),
            status=ConversionStatus.validated,
            used_by_validated_operations=1,
        ),
    )

    promoted = promote_to_common_lib(conn, "component-1", str(tmp_path / "common-lib"), "run-1")

    assert promoted is False


def test_promote_to_common_lib_with_two_validated_usages_promotes(tmp_path, monkeypatch):
    conn = memory_conn()
    source_file = tmp_path / "generated" / "Shared.java"
    source_file.parent.mkdir()
    source_file.write_text("class Shared {}\n")
    common_lib = tmp_path / "common-lib"
    register_component(
        conn,
        component_record(
            generated_path=str(source_file),
            status=ConversionStatus.validated,
            used_by_validated_operations=2,
        ),
    )
    calls = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    promoted = promote_to_common_lib(conn, "component-1", str(common_lib), "run-1")

    assert promoted is True
    assert (common_lib / "src" / "Shared.java").read_text() == "class Shared {}\n"
    assert calls == [(["mvn", "install"], common_lib, True)]
