"""Capture executable test failures and their latest source evidence for correction."""

import re
from pathlib import Path
from xml.etree import ElementTree
from runtime.behavior_conversion.compiler_feedback import with_dependency_apis

TEST_CORRECTION_INSTRUCTION = """When test_correction is supplied, compare its failing test, setup,
assertion, exception and latest implementation sources against the original source evidence
and configuration in this request. Actual and expected values are observations when available,
not proof that the test expectation is correct. Determine whether the test, implementation or
both disagree with the evidence. Correct the mismatch without weakening assertions, dropping
behavior coverage or changing unrelated behavior or accepted APIs. Preserve passing cases and
return the complete corrected bundle and matching metadata; the full test suite will rerun."""


class TestCorrectionError(ValueError):
    """Retain test reports and sources after the temporary build directory disappears."""

    def __init__(self, message, correction):
        super().__init__(message)
        self.test_correction = correction


def test_correction(error, sources=(), dependency_apis=(), staged=None):
    """Read Surefire failures, or reconstruct available details from retained Maven output."""
    text = str(error)
    files = {item["path"]: item["content"] for item in sources}
    diagnostics = []
    if staged is not None:
        root = Path(staged).resolve()
        for path in sorted((root / "src").rglob("*.java")):
            if path.resolve().is_relative_to(root):
                files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
        for path in sorted((root / "target/surefire-reports").glob("TEST-*.xml")):
            if not path.resolve().is_relative_to(root):
                continue
            try:
                report = ElementTree.parse(path).getroot()
            except (ElementTree.ParseError, OSError):
                continue
            for case in report.iter("testcase"):
                for failure in list(case):
                    if failure.tag not in ("failure", "error"):
                        continue
                    diagnostics.append(dict(test_class=case.get("classname", report.get("name", "")),
                        test_method=case.get("name", ""), category="assertion_failure" if failure.tag == "failure" else "test_error",
                        message=failure.get("message", ""), exception_type=failure.get("type", ""),
                        stack_trace=failure.text or "", report_file=path.name,
                        test_output="\n".join(node.text or "" for node in list(case) + list(report) if node.tag in ("system-out", "system-err"))))
    if not diagnostics:
        pattern = r"\[ERROR\]\s+([\w.$]+)\.([\w$]+)\s+--[^\n]*<<< (FAILURE|ERROR)!\s*\n([^\n]+)"
        for match in re.finditer(pattern, text):
            diagnostics.append(dict(test_class=match[1], test_method=match[2],
                category="assertion_failure" if match[3] == "FAILURE" else "test_error",
                message=match[4], stack_trace=text[match.end():].split("[INFO]", 1)[0], exception_type=match[4].split(":", 1)[0]))
    if not diagnostics:
        return None
    failed = {}
    for diagnostic in diagnostics:
        name = diagnostic["test_class"]
        path = "src/test/java/" + name.split("$", 1)[0].replace(".", "/") + ".java"
        diagnostic["file"] = path
        values = re.search(r"expected: <(.*?)> but was: <(.*?)>", diagnostic["message"], re.DOTALL)
        if values:
            diagnostic.update(expected_value=values[1], actual_value=values[2])
        method = diagnostic["test_method"].split("(", 1)[0].split("[", 1)[0]
        frame = re.search(re.escape(name) + r"\." + re.escape(method) + r"\([^():]+:(\d+)\)", diagnostic["stack_trace"])
        if frame:
            diagnostic["line"] = int(frame[1])
        source = files.get(path)
        if source is not None:
            failed[path] = source
            lines = source.splitlines()
            line = diagnostic.get("line", 0)
            if 0 < line <= len(lines):
                diagnostic["source_line"] = lines[line - 1]
                diagnostic["setup_and_assertion_context"] = "\n".join(
                    f"{index + 1}: {lines[index]}" for index in range(max(0, line - 16), min(len(lines), line + 3)))
        diagnostic["correction"] = "Compare this test and implementation with the original configuration and supporting source evidence; fix the evidenced mismatch, not just the symptom."
    context = "\n".join(failed.values()) + str(diagnostics)
    relevant = [dict(path=path, content=content) for path, content in files.items()
        if path.startswith("src/main/java/") and re.search(r"\b" + re.escape(Path(path).stem) + r"\b", context)]
    while True:
        context += "\n" + "\n".join(item["content"] for item in relevant)
        additional = [dict(path=path, content=content) for path, content in files.items()
            if path.startswith("src/main/java/") and path not in {item["path"] for item in relevant}
            and re.search(r"\b" + re.escape(Path(path).stem) + r"\b", context)]
        if not additional:
            break
        relevant.extend(additional)
    correction = dict(diagnostics=diagnostics, failed_sources=[dict(path=path, content=content) for path, content in failed.items()],
        relevant_implementation_sources=relevant, original_test_output=text)
    return with_dependency_apis(correction, dependency_apis)
