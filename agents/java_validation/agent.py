from __future__ import annotations

import sqlite3
import subprocess
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen

from constants import FORBIDDEN_DEPENDENCIES
from models.common_models import TargetLanguage
from models.conversion_models import RoutingPlan, ValidationFailureClass
from models.validation_models import GoldenXmlPair, TraceComparisonResult, ValidationPlan, ValidationReport, XmlDiffResult
from tools.state_store_tools._json import utc_now
from tools.trace_capture_tools.generated_trace_interceptor import read_generated_trace
from tools.trace_capture_tools.legacy_trace_interceptor import capture_legacy_trace
from tools.trace_capture_tools.trace_scenario_builder import derive_trace_scenarios
from tools.trace_comparator_tools.trace_comparator_tool import compare_traces
from tools.trace_comparator_tools.trace_report_writer import write_comparison_to_db
from tools.validation_tools.ibm_dependency_guard_tool import scan_for_ibm_dependencies
from tools.validation_tools.xml_diff_tool import compare_xml

try:
    from google.adk.agents import SequentialAgent
except ImportError:

    class SequentialAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


@dataclass(frozen=True)
class JavaBuildResult:
    """Maven compile result for a generated Java service."""

    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def validate_compile(generated_path: str) -> JavaBuildResult:
    """Run mvn compile on the generated Java project."""
    result = subprocess.run(
        ["mvn", "compile"],
        cwd=generated_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return JavaBuildResult(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def validate_ibm_guard(generated_path: str, forbidden: list[str]) -> list[str]:
    """Scan generated Java sources for forbidden IBM dependency patterns."""
    return scan_for_ibm_dependencies(generated_path, forbidden)


def review_code_equivalence(native_java: str, generated_java: str) -> dict:
    """Run deterministic fallback code-equivalence review."""
    if native_java and generated_java and "TODO" in generated_java:
        return {"passed": False, "issues": ["generated service contains TODO"]}
    return {"passed": True, "issues": []}


def run_golden_xml_test(pair: GoldenXmlPair, service_base_url: str) -> XmlDiffResult:
    """Send a golden XML request to a running service and compare the response."""
    request = Request(
        service_base_url.rstrip("/"),
        data=pair.request_xml.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/xml"},
    )
    with urlopen(request, timeout=30) as response:
        actual_xml = response.read().decode("utf-8")
    result = compare_xml(pair.expected_response_xml, actual_xml)
    return result.model_copy(update={"operation_id": pair.operation_id, "scenario": pair.scenario})


def run_trace_comparison(
    operation_id: str,
    channel: str,
    routing_plan: RoutingPlan,
    legacy_base_url: str,
    service_base_url: str,
    run_id: str,
    conn: sqlite3.Connection | None = None,
) -> list[TraceComparisonResult]:
    """Capture and compare legacy/generated traces for derived routing scenarios."""
    results = []
    for scenario in derive_trace_scenarios(routing_plan):
        legacy = capture_legacy_trace(legacy_base_url, operation_id, channel, scenario, conn=conn, run_id=run_id)
        generated = read_generated_trace(operation_id, scenario, service_base_url, conn=conn, run_id=run_id, channel=channel)
        result = compare_traces(legacy, generated)
        if conn:
            write_comparison_to_db(conn, result, operation_id, channel, run_id, scenario.name)
        results.append(result)
    return results


def run_performance_benchmark(service_base_url: str, request_xml: str) -> dict:
    """Send 100 requests and report simple latency percentiles."""
    timings = []
    for _ in range(100):
        start = time.perf_counter()
        request = Request(
            service_base_url.rstrip("/"),
            data=request_xml.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/xml"},
        )
        with urlopen(request, timeout=30):
            pass
        timings.append((time.perf_counter() - start) * 1000)
    sorted_timings = sorted(timings)
    return {
        "request_count": len(sorted_timings),
        "p50_ms": sorted_timings[49],
        "p95_ms": sorted_timings[94],
    }


def route_validation_failure(result: ValidationReport) -> str:
    """Return the agent/tool target that should handle a validation failure."""
    routes = {
        ValidationFailureClass.build_failure: "JavaServiceGenerationAgent",
        ValidationFailureClass.conversion_gap: "IbmJavaCleanerAgent",
        ValidationFailureClass.equivalence_gap: "JavaServiceGenerationAgent",
        ValidationFailureClass.shared_component_gap: "IbmJavaCleanerAgent",
        ValidationFailureClass.routing_mismatch: "StepImplementationInserterAgent",
        ValidationFailureClass.validation_fixture_gap: "validation_tools",
    }
    return routes.get(result.failure_class, "")


def run_java_validation(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    operation_id: str,
    channel: str,
    run_id: str,
    generated_path: str,
    routing_plan: RoutingPlan,
    validation_plan: ValidationPlan | None = None,
    legacy_base_url: str = "",
    service_base_url: str = "",
    native_java_source: str = "",
    generated_java_source: str = "",
    compile_validator=validate_compile,
    ibm_guard_validator=validate_ibm_guard,
    code_reviewer=review_code_equivalence,
    golden_runner=run_golden_xml_test,
    trace_runner=run_trace_comparison,
    behavior_runner=None,
    performance_runner=run_performance_benchmark,
    build_context=None,
) -> ValidationReport:
    """Run Java service validation steps and update generated artifact state."""
    artifact = _artifact(conn, artifact_id)
    attempt_number = int(artifact["attempt_number"] or 0) if artifact else 0
    plan = validation_plan or ValidationPlan(operation_id=operation_id)

    if build_context is not None:
        compiled = build_context.verifier.compile_project(generated_path, build_context.allowed_ibm_artifacts)
        build_result = JavaBuildResult(compiled.returncode, compiled.stdout, compiled.stderr)
    else:
        build_result = compile_validator(generated_path)
    if not build_result.passed:
        _set_artifact_state(conn, artifact_id, "blocked", "compile_failed")
        return _report(run_id, operation_id, False, False, False, False, False, attempt_number, ValidationFailureClass.build_failure)

    findings = (scan_for_ibm_dependencies(generated_path, FORBIDDEN_DEPENDENCIES,
                allowed_classes=build_context.allowed_ibm_classes) if build_context is not None else
                ibm_guard_validator(generated_path, FORBIDDEN_DEPENDENCIES))
    if findings:
        _set_artifact_state(conn, artifact_id, "blocked", "ibm_dependency_found")
        return _report(run_id, operation_id, True, False, False, False, False, attempt_number, ValidationFailureClass.build_failure)

    equivalence = code_reviewer(native_java_source, generated_java_source)
    if not equivalence.get("passed", False):
        _set_artifact_state(conn, artifact_id, "blocked", "equivalence_gap")
        return _report(run_id, operation_id, True, False, False, True, False, attempt_number, ValidationFailureClass.equivalence_gap)

    xml_diffs = [golden_runner(pair, service_base_url) for pair in plan.golden_pairs]
    if any(not diff.passed for diff in xml_diffs):
        _set_artifact_state(conn, artifact_id, "blocked", "conversion_gap")
        return _report(run_id, operation_id, True, False, False, True, False, attempt_number, ValidationFailureClass.conversion_gap, xml_diffs)

    trace_results = trace_runner(operation_id, channel, routing_plan, legacy_base_url, service_base_url, run_id, conn)
    trace_failure = _trace_failure_class(trace_results)
    if trace_failure:
        _set_artifact_state(conn, artifact_id, "blocked", trace_failure.value)
        return _report(run_id, operation_id, True, False, True, True, False, attempt_number, trace_failure, xml_diffs)

    behavior_diffs = behavior_runner() if behavior_runner else []
    if any(not diff.passed for diff in behavior_diffs):
        _set_artifact_state(conn, artifact_id, "blocked", "equivalence_gap")
        return _report(run_id, operation_id, True, False, False, True, False, attempt_number, ValidationFailureClass.equivalence_gap, [*xml_diffs, *behavior_diffs])

    if plan.golden_pairs and service_base_url:
        performance_runner(service_base_url, plan.golden_pairs[0].request_xml)
    _set_artifact_state(conn, artifact_id, "validated", None)
    return _report(run_id, operation_id, True, True, True, True, True, attempt_number, None, xml_diffs)


def _trace_failure_class(results: list[TraceComparisonResult]) -> ValidationFailureClass | None:
    for failure_class in (
        ValidationFailureClass.routing_mismatch,
        ValidationFailureClass.conversion_gap,
        ValidationFailureClass.equivalence_gap,
    ):
        if any(result.failure_class == failure_class for result in results):
            return failure_class
    return None


def _report(
    run_id: str,
    operation_id: str,
    build_passed: bool,
    test_passed: bool,
    xml_compat_passed: bool,
    ibm_guard_passed: bool,
    behavior_equiv_passed: bool,
    attempt_number: int,
    failure_class: ValidationFailureClass | None,
    xml_diffs: list[XmlDiffResult] | None = None,
) -> ValidationReport:
    return ValidationReport(
        run_id=run_id,
        operation_id=operation_id,
        target_language=TargetLanguage.java,
        build_passed=build_passed,
        test_passed=test_passed,
        xml_compat_passed=xml_compat_passed,
        ibm_guard_passed=ibm_guard_passed,
        behavior_equiv_passed=behavior_equiv_passed,
        xml_diffs=xml_diffs or [],
        failure_class=failure_class,
        attempt_number=attempt_number,
        evidence_paths=[],
    )


def _artifact(conn: sqlite3.Connection, artifact_id: str) -> dict | None:
    return conn.execute("SELECT * FROM generated_artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()


def _set_artifact_state(
    conn: sqlite3.Connection,
    artifact_id: str,
    status: str,
    blocking_reason: str | None,
) -> None:
    conn.execute(
        """
        UPDATE generated_artifacts
        SET status = ?, blocking_reason = ?, updated_at = ?
        WHERE artifact_id = ?
        """,
        (status, blocking_reason, utc_now(), artifact_id),
    )
    conn.commit()


java_validation_agent = SequentialAgent(
    name="JavaValidationAgent",
    description="Runs all 7 validation steps for a generated Java service.",
    sub_agents=[],
)
