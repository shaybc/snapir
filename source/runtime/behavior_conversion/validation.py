"""Require real test execution and retain bounded compiler feedback for candidates."""

from pathlib import Path
from xml.etree import ElementTree
from models.native_unit_validation import NativeUnitValidation
from runtime.behavior_conversion.validation_progress import progress_step


def build_candidate(project, context, require_tests=True, required_tests=()):
    """Compile and test; Maven exit zero without executed tests is not test evidence."""
    result = NativeUnitValidation()
    for goal in (["compile", "test"] if require_tests else ["compile"]):
        with progress_step("Compiling Java sources" if goal == "compile" else "Running tests and checking execution reports", failed=lambda: bool(result.issues)):
            build = context.verifier.compile_project(project, context.allowed_ibm_artifacts, goal=goal)
            if build.returncode:
                result.issues.append("Maven " + goal + ": " + (build.stdout or "") + "\n" + (build.stderr or ""))
                return result
            if goal == "compile":
                result.build_passed = True
            else:
                reports = list((Path(project) / "target/surefire-reports").glob("TEST-*.xml"))
                for path in reports:
                    root = ElementTree.parse(path).getroot()
                    result.test_count += int(root.get("tests", "0")) - int(root.get("skipped", "0"))
                    if int(root.get("tests", "0")) > int(root.get("skipped", "0")):
                        result.executed_test_classes.append(root.get("name") or path.stem.removeprefix("TEST-"))
                    if int(root.get("failures", "0")) or int(root.get("errors", "0")):
                        result.issues.append("Failed behavioral tests: " + path.name)
                result.tests_passed = result.test_count > 0 and not result.issues
                if not result.tests_passed:
                    result.issues.append("No passing executable behavior-test evidence")
                for name in required_tests:
                    expected = name.removeprefix("src/test/java/").removesuffix(".java").replace("/", ".")
                    if not any(value == expected or value.startswith(expected + "$") for value in result.executed_test_classes):
                        result.issues.append("Required behavior tests were not executed: " + name)
                result.tests_passed = result.tests_passed and not result.issues
    return result
