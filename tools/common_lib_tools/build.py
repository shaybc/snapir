from __future__ import annotations

import sqlite3
import subprocess
import time
from pathlib import Path

from models.java_models import JavaBuildResult
from tools.java_analysis_tools.java_source_reader import resolve_source_path
from agents.source_conversion.ibm_java_cleaner.agent import clean_ibm_java_source


def run_common_lib_build(common_lib_root: str, *, build_context=None) -> JavaBuildResult:
    """Run mvn install on the common-lib project."""
    started = time.perf_counter()
    result = build_context.verifier.compile_project(common_lib_root, build_context.allowed_ibm_artifacts, goal="install") if build_context else subprocess.run(
        ["mvn", "install"],
        cwd=common_lib_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return JavaBuildResult(
        operation_id="common-lib",
        target_language="java",
        success=result.returncode == 0,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


def convert_framework_tags(
    conn: sqlite3.Connection,
    tag_registry_channel: str,
    common_lib_root: str,
    composer_root: str,
    run_id: str,
) -> list[str]:
    """Synchronously convert formatter/decorator tag classes into common-lib."""
    rows = conn.execute(
        """
        SELECT fqcn FROM tag_registry
        WHERE run_id = ? AND channel = ?
        ORDER BY tag_name
        """,
        (run_id, tag_registry_channel),
    ).fetchall()
    converted = []
    for row in rows:
        fqcn = row["fqcn"]
        source_path = resolve_source_path(composer_root, fqcn)
        if source_path is None:
            continue
        output_path = _common_lib_source_path(common_lib_root, fqcn)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            clean_ibm_java_source(Path(source_path).read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        converted.append(fqcn)
    if converted:
        run_common_lib_build(common_lib_root)
    return converted


def _common_lib_source_path(common_lib_root: str, fqcn: str) -> Path:
    return Path(common_lib_root) / "src" / "main" / "java" / Path(*fqcn.split(".")).with_suffix(".java")
