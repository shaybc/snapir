"""Record build evidence separately from unavailable runtime equivalence evidence."""

from pathlib import Path

from constants import FORBIDDEN_DEPENDENCIES
from tools.validation_tools.ibm_dependency_guard_tool import scan_for_ibm_dependencies


def validate_service_project(project, context):
    """Run managed compile, tests and packaging; never infer behavioral equivalence."""
    findings = scan_for_ibm_dependencies(str(project), FORBIDDEN_DEPENDENCIES,
                                        allowed_classes=context.allowed_ibm_classes)
    results = dict(ibm_guard_passed=not findings, findings=findings, build_passed=False,
                   test_status="not_run", package_passed=False, xml_compatibility="not_available",
                   behavioral_equivalence="not_available", legacy_trace_comparison="not_available")
    if findings:
        return results
    for goal in ("compile", "test", "package"):
        result = context.verifier.compile_project(project, context.allowed_ibm_artifacts, goal=goal)
        results[goal + "_log"] = dict(stdout=result.stdout, stderr=result.stderr)
        if result.returncode:
            results[goal + "_failed"] = True
            results["failure_class"] = "build_failure"
            return results
        if goal == "compile":
            results["build_passed"] = True
        elif goal == "test":
            from xml.etree import ElementTree
            reports = list((Path(project) / "target/surefire-reports").glob("TEST-*.xml"))
            count = sum(int(ElementTree.parse(path).getroot().get("tests", "0")) for path in reports)
            results["test_status"] = "passed" if count else "not_available"
            results["test_count"] = count
        else:
            results["package_passed"] = True
    return results
