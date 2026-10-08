from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.project_paths import project_root

from agents.legacy_composer_analysis.agent import run_legacy_composer_analysis
from agents.migration_planning.agent import get_operations_for_planning
from models.common_models import RunConfig, RunMode, TargetLanguage
from tools.conversion_tools.context_hierarchy_resolver_tool import build_all_context_hierarchies
from tools.shared_artifact_classifier_tools.classifier import run_shared_artifact_classification
from tools.state_store_tools.db import create_all_tables, get_connection
from tools.state_store_tools.runs import upsert_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a self-cleaning inventory smoke test.")
    parser.add_argument("--channel", default="INTERNET")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args(argv)

    workspace_root = project_root() / "bank-demo" / "composer" / "Workspace"
    mapper_jar = ROOT / "composer-mapper" / "target" / "composer-mapper-1.1.1-jar-with-dependencies.jar"
    if not workspace_root.exists():
        print(f"Missing bank demo workspace: {workspace_root}")
        return 1
    if not mapper_jar.exists():
        print(f"Missing composer-mapper jar: {mapper_jar}")
        return 1

    temp_context = tempfile.TemporaryDirectory(prefix="snapir-inventory-smoke-")
    temp_root = Path(temp_context.name)
    try:
        return _run_smoke_test(temp_root, workspace_root, mapper_jar, args.channel)
    finally:
        if args.keep_temp:
            print(f"Temp files kept at: {temp_root}")
        else:
            temp_context.cleanup()


def _run_smoke_test(temp_root: Path, workspace_root: Path, mapper_jar: Path, channel: str) -> int:
    vault_root = temp_root / "vault"
    db_path = temp_root / "state.db"
    print(f"Temp root: {temp_root}")
    print("Generating composer-mapper vault...")
    mapper = subprocess.run(
        [
            "java",
            "-jar",
            str(mapper_jar),
            "--root",
            str(workspace_root),
            "--vault",
            str(vault_root),
            "--md",
            "--channel",
            channel,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if mapper.returncode != 0:
        print(mapper.stdout)
        print(mapper.stderr)
        return mapper.returncode
    print(mapper.stdout.strip())

    conn = get_connection(str(db_path))
    try:
        create_all_tables(conn)
        run_config = _run_config(vault_root, db_path, channel)
        upsert_run(
            conn,
            run_id=run_config.run_id,
            run_mode=run_config.run_mode.value,
            status="started",
            run_config=run_config,
        )

        print("Importing vault and detecting invalidation...")
        analysis = run_legacy_composer_analysis(conn, run_config)
        print("Building context hierarchies...")
        hierarchies = build_all_context_hierarchies(conn, run_config.run_id)
        print("Classifying shared artifacts...")
        classification = run_shared_artifact_classification(conn, run_config.run_id)
        planning_rows = get_operations_for_planning(conn, run_config.run_id)
    finally:
        conn.close()

    print("\n=== Inventory Smoke Test Summary ===")
    print(f"Operations imported: {analysis['import_summary']['operations']}")
    print(f"OpSteps imported: {analysis['import_summary']['opsteps']}")
    print(f"Formats imported: {analysis['import_summary']['formats']}")
    print(f"Contexts imported: {analysis['import_summary']['contexts']}")
    print(f"Java classes imported: {analysis['import_summary']['java_classes']}")
    print(f"Channel operations: {analysis['import_summary']['channel_operations']}")
    print(f"Context hierarchies: {len(hierarchies)}")
    print(f"Shared formats: {classification.shared_formats}")
    print(f"Shared classes: {classification.shared_classes}")
    print(f"Shared contexts: {classification.shared_contexts}")
    print(f"XML contract candidates: {classification.xml_contract_candidates}")
    print(f"Planning operations: {len(planning_rows)}")

    print("\nOperations:")
    for item in planning_rows:
        print(
            "- "
            f"{item['operation_id']} [{item['channel']}]: "
            f"steps={item['step_count']}, branches={item['branch_count']}, "
            f"shared_formats={item['shared_formats_count']}, "
            f"shared_classes={item['shared_classes_count']}, "
            f"blocked_context={item['has_blocked_context']}"
        )
    return 0


def _run_config(vault_root: Path, db_path: Path, channel: str) -> RunConfig:
    return RunConfig(
        run_id="smoke-run",
        run_mode=RunMode.single_channel,
        source_root=str(project_root() / "bank-demo" / "composer" / "Workspace"),
        vault_root=str(vault_root),
        output_root=str(vault_root.parent / "out"),
        db_path=str(db_path),
        target_channels=[channel],
        composer_mapper_channel_filter=channel,
        target_languages=[TargetLanguage.java],
        enable_git=False,
        artifact_schema_version="v1",
        max_agent_task_retries=3,
        max_parallel_conversion_workers=4,
        max_parallel_llm_tasks=2,
        max_parallel_build_tasks=2,
        max_operations_per_batch=5,
        model_name="smoke",
        model_base_url="http://localhost",
        auto_rerun_impacted_operations=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
