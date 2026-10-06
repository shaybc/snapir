from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Callable

from constants import AGENT_MODEL
from models.conversion_models import ConversionReviewResult
from tools.state_store_tools._json import dumps, loads, utc_now

try:
    from google.adk.agents import LlmAgent
except ImportError:

    class LlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


NATIVE_JAVA_REVIEW_INSTRUCTION = """
You are reviewing a converted native Java class against its original IBM source.

REVIEW_KIND: {review_kind}  (ibm_java | xml_fmtdef_dto | context_class)
ORIGINAL_SOURCE: {original_source}
CONVERTED_CLASS: {converted_java}
PARENT_CLASS: {parent_class}
BEHAVIOR_TYPE: {behavior_types}

Check ALL of the following:
1. NO IBM imports remain (com.ibm.*, javax.ejb.*, org.omg.* etc.)
2. Business logic is preserved EXACTLY from original execute() or equivalent.
3. All return code values are unchanged.
4. All setter methods are present (from original XML attribute handling).
5. Context field access is correctly rewritten (setValueAt -> typed setter).
6. For dto review: no logic in the DTO, no DB calls, CCTableFormat absent.
7. For context review: flat class, no inheritance, all fields present.

Output JSON:
{
  "issues": ["description of each issue found"],
  "confidence": "high|medium|low",
  "review_status": "approved|needs_revision|needs_human_review"
}
- approved: no issues found, confidence=high or medium
- needs_revision: issues found but fixable by the converter agent
- needs_human_review: issues found that require human judgment
  (confidence=low, or IBM logic that cannot be automatically converted)

Output ONLY the JSON. No explanation.
"""


def review_native_java(
    original_source: str,
    converted_java: str,
    *,
    review_kind: str = "ibm_java",
    allowed_ibm_classes=(),
) -> ConversionReviewResult:
    """Run deterministic native Java review checks for tests and fallback review."""
    issues = []
    issues.extend(_forbidden_import_issues(converted_java, allowed_ibm_classes))
    issues.extend(_missing_setter_issues(original_source, converted_java))
    issues.extend(_return_code_issues(original_source, converted_java))
    issues.extend(_context_rewrite_issues(converted_java))
    if review_kind == "xml_fmtdef_dto":
        issues.extend(_dto_issues(converted_java))
    if review_kind == "context_class":
        issues.extend(_context_class_issues(converted_java))
    return ConversionReviewResult(
        conversion_id="review",
        issues=issues,
        confidence="high" if not issues else "medium",
        review_status="approved" if not issues else "needs_revision",
    )


def parse_review_output(conversion_id: str, output: str) -> ConversionReviewResult:
    """Parse reviewer JSON output into a ConversionReviewResult."""
    data = json.loads(output)
    return ConversionReviewResult(conversion_id=conversion_id, **data)


def dispatch_reviews_for_batch(
    conn: sqlite3.Connection,
    run_id: str,
    batch_converted_ids: list[str],
    reviewer: Callable[[str, str, str], ConversionReviewResult] | None = None,
    *,
    build_context=None,
) -> list[ConversionReviewResult]:
    """Review converted native Java artifacts and update review state."""
    results = []
    for artifact_id in batch_converted_ids:
        artifact = _native_artifact(conn, artifact_id, run_id)
        if artifact is None:
            continue
        converted_java = _read_text(artifact["artifact_path"])
        original_source = _original_source(conn, run_id, artifact["logical_id"])
        review_kind = _review_kind(artifact["kind"])
        result = reviewer(original_source, converted_java, review_kind) if reviewer else review_native_java(
            original_source,
            converted_java,
            review_kind=review_kind,
            allowed_ibm_classes=build_context.allowed_ibm_classes if build_context else (),
        )
        result = result.model_copy(update={"conversion_id": artifact["conversion_id"]})
        _apply_review_result(conn, artifact_id, result)
        results.append(result)
    return results


def build_human_gate2_report(
    review_results: list[ConversionReviewResult],
    *,
    common_lib_build_passed: bool,
    framework_tags_converted: int,
    sample_files: list[str],
) -> str:
    """Build the Human Gate 2 summary text."""
    approved = sum(1 for result in review_results if result.review_status == "approved")
    needs_revision = sum(1 for result in review_results if result.review_status == "needs_revision")
    needs_human_review = sum(1 for result in review_results if result.review_status == "needs_human_review")
    return "\n".join([
        "=== Human Gate 2 ===",
        f"Converted files reviewed: {len(review_results)}",
        f"Approved: {approved}",
        f"Needs revision (auto-retry pending): {needs_revision}",
        f"Needs human review: {needs_human_review}",
        "",
        f"common-lib build: {'PASSED' if common_lib_build_passed else 'FAILED'}",
        f"Framework tags converted: {framework_tags_converted}",
        "",
        f"Sample files for review: {sample_files}",
        "Approve to continue to Phase 4 (operation assembly)? (yes/no)",
    ])


def _forbidden_import_issues(java_source: str, allowed_ibm_classes=()) -> list[str]:
    issues = []
    for line in java_source.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") and stripped.removeprefix("import ").removesuffix(";") in allowed_ibm_classes:
            from tools.validation_tools.ibm_dependency_guard_tool import scan_source
            if not scan_source(stripped, ["com.ibm", "javax.ejb", "org.omg"], allowed_classes=allowed_ibm_classes):
                continue
        if stripped.startswith(("import com.ibm.", "import javax.ejb.", "import org.omg.")):
            issues.append(f"Forbidden IBM import remains: {stripped}")
    return issues


def _missing_setter_issues(original_source: str, converted_java: str) -> list[str]:
    issues = []
    for setter_name in sorted(set(re.findall(r"\bvoid\s+(set[A-Za-z0-9_]+)\s*\(", original_source))):
        if not re.search(rf"\bvoid\s+{re.escape(setter_name)}\s*\(", converted_java):
            issues.append(f"Missing setter method: {setter_name}")
    return issues


def _return_code_issues(original_source: str, converted_java: str) -> list[str]:
    original_codes = set(re.findall(r"\breturn\s+(-?\d+)\s*;", original_source))
    converted_codes = set(re.findall(r"\breturn\s+(-?\d+)\s*;", converted_java))
    missing = sorted(original_codes - converted_codes)
    return [f"Missing return code value: {code}" for code in missing]


def _context_rewrite_issues(converted_java: str) -> list[str]:
    if "setValueAt(" in converted_java or "getValueAt(" in converted_java:
        return ["IBM context access remains in converted class"]
    return []


def _dto_issues(converted_java: str) -> list[str]:
    issues = []
    if "CCTableFormat" in converted_java:
        issues.append("DTO contains CCTableFormat lookup field")
    if re.search(r"\b(Connection|DataSource|execute\s*\()", converted_java):
        issues.append("DTO contains logic or DB access")
    return issues


def _context_class_issues(converted_java: str) -> list[str]:
    issues = []
    if " extends " in converted_java:
        issues.append("Context class is not flat")
    if "@" in converted_java:
        issues.append("Context class contains annotations")
    return issues


def _native_artifact(conn: sqlite3.Connection, artifact_id: str, run_id: str):
    return conn.execute(
        """
        SELECT * FROM native_java_artifacts
        WHERE artifact_id = ? AND run_id = ?
        """,
        (artifact_id, run_id),
    ).fetchone()


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    source_path = Path(path)
    if not source_path.exists():
        return ""
    return source_path.read_text(encoding="utf-8")


def _original_source(conn: sqlite3.Connection, run_id: str, logical_id: str) -> str:
    row = conn.execute(
        """
        SELECT source_path, metadata_json
        FROM source_artifacts
        WHERE run_id = ? AND logical_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (run_id, logical_id),
    ).fetchone()
    if row is None:
        return ""
    if row["source_path"]:
        return _read_text(row["source_path"])
    metadata = loads(row["metadata_json"], {}) or {}
    return str(metadata.get("source", ""))


def _review_kind(artifact_kind: str) -> str:
    return {
        "ibm_java": "ibm_java",
        "xml_fmtdef": "xml_fmtdef_dto",
        "xml_context": "context_class",
    }.get(artifact_kind, artifact_kind)


def _apply_review_result(
    conn: sqlite3.Connection,
    artifact_id: str,
    result: ConversionReviewResult,
) -> None:
    blocking_reason = "needs_human_mapping" if result.review_status == "needs_human_review" else None
    conn.execute(
        """
        UPDATE native_java_artifacts
        SET review_status = ?,
            review_notes_json = ?,
            blocking_reason = ?,
            updated_at = ?
        WHERE artifact_id = ?
        """,
        (result.review_status, dumps(result.issues), blocking_reason, utc_now(), artifact_id),
    )
    conn.commit()


native_java_review_agent = LlmAgent(
    name="NativeJavaReviewAgent",
    description="Reviews converted native Java against original IBM source.",
    model=AGENT_MODEL,
    instruction=NATIVE_JAVA_REVIEW_INSTRUCTION,
    tools=[],
)
