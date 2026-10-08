from __future__ import annotations

import pytest

import agents.legacy_composer_analysis.agent as agent_module
from agents.legacy_composer_analysis.agent import (
    AGENT_NAME,
    INVENTORY_COMPLETE,
    run_legacy_composer_analysis,
)
from models.common_models import RunConfig, RunMode, TargetLanguage
from tools.state_store_tools.agent_tasks import get_agent_task
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.native_java_artifacts import upsert_native_java_artifact
from tools.state_store_tools.runs import get_run, upsert_run


def memory_conn():
    conn = get_connection(":memory:")
    create_all_tables(conn)
    return conn


def run_config(tmp_path, *, auto_rerun=True, vault_root=None):
    vault_root = vault_root or tmp_path / "vault"
    return RunConfig(
        run_id="run-1",
        run_mode=RunMode.single_channel,
        source_root=str(tmp_path / "composer"),
        vault_root=str(vault_root),
        output_root=str(tmp_path / "out"),
        db_path=str(tmp_path / "state.db"),
        target_channels=["INTERNET"],
        composer_mapper_channel_filter="INTERNET",
        target_languages=[TargetLanguage.java],
        enable_git=False,
        artifact_schema_version="v1",
        max_agent_task_retries=3,
        max_parallel_conversion_workers=4,
        max_parallel_llm_tasks=2,
        max_parallel_build_tasks=2,
        max_operations_per_batch=5,
        model_name="model",
        model_base_url="http://localhost",
        auto_rerun_impacted_operations=auto_rerun,
    )


def seed_run(conn, config):
    upsert_run(
        conn,
        run_id=config.run_id,
        run_mode=config.run_mode.value,
        status="started",
        run_config=config,
    )


def make_vault(tmp_path, *, source_hash="hash-1"):
    vault = tmp_path / "vault"
    (vault / "analysis").mkdir(parents=True)
    (vault / "channels").mkdir()
    (vault / "operations").mkdir()
    (vault / "opsteps").mkdir()
    (vault / "formats").mkdir()
    (vault / "contexts").mkdir()
    (vault / "classes" / "com" / "bank").mkdir(parents=True)
    (vault / "analysis" / "channel-operation-registry.md").write_text(
        """
| Operation | Channel | XML File Path |
|---|---|---|
| OpA | INTERNET | `OpA.xml` |
"""
    )
    (vault / "operations" / "OpA.md").write_text(
        f"""
# OpA

---
entity_type: operation
entity_id: OpA
conversion_status: not_started
channel: INTERNET
source_file: OpA.xml
source_hash: {source_hash}
---

## Steps
- StepA
"""
    )
    return vault


def task_id(config):
    return f"{config.run_id}:{AGENT_NAME}:run:{config.run_id}:all:any:v1"


def test_successful_import_sets_inventory_complete(tmp_path):
    conn = memory_conn()
    config = run_config(tmp_path, vault_root=make_vault(tmp_path))
    seed_run(conn, config)

    result = run_legacy_composer_analysis(conn, config)

    assert result["paused"] is False
    assert get_run(conn, config.run_id)["current_phase"] == INVENTORY_COMPLETE
    assert get_agent_task(conn, task_id(config))["status"] == "completed"


def test_hash_change_with_auto_rerun_false_sets_run_paused(tmp_path):
    conn = memory_conn()
    config = run_config(tmp_path, auto_rerun=False, vault_root=make_vault(tmp_path, source_hash="new"))
    seed_run(conn, config)
    upsert_native_java_artifact(
        conn,
        artifact_id="native-op",
        run_id=config.run_id,
        conversion_id="conv-op",
        kind="operation",
        logical_id="OpA",
        source_hash="old",
        status="validated",
    )

    result = run_legacy_composer_analysis(conn, config)

    run = get_run(conn, config.run_id)
    assert result["paused"] is True
    assert run["status"] == "paused_awaiting_operator"
    assert "changed=1" in run["current_phase"]


def test_import_failure_sets_agent_task_failed(tmp_path, monkeypatch):
    conn = memory_conn()
    config = run_config(tmp_path, vault_root=make_vault(tmp_path))
    seed_run(conn, config)

    def fail_import(conn, vault_root, run_config):
        raise RuntimeError("import exploded")

    monkeypatch.setattr(agent_module, "import_vault", fail_import)

    with pytest.raises(Exception):
        run_legacy_composer_analysis(conn, config)

    task = get_agent_task(conn, task_id(config))
    assert task["status"] == "failed"
