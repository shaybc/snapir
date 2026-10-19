"""Select direct test-failure evidence without recursively resending the operation."""

from copy import deepcopy
from pathlib import Path
import re

from runtime.java_public_type import _code


def trim_test_correction(payload):
    """Retain failing tests, direct implementation calls, routing and accepted APIs.

    Returns a copy; durable responses, reports and source history are not modified.
    Constructor-only collaborators retain their accepted APIs rather than entire bodies.
    """
    correction = payload.get("test_correction")
    if not correction:
        return payload
    result = deepcopy(payload)
    correction = result["test_correction"]
    tests = "\n".join(item["content"] for item in correction.get("failed_sources", []))
    code = _code(tests)
    receivers = set(re.findall(r"\b(\w+)\s*\.\s*\w+\s*\(", code))
    types = {kind for kind, name in re.findall(r"\b([\w.]+)(?:\s*<[^;=]+>)?\s+(\w+)\s*=", code) if name in receivers}
    types.update(re.findall(r"\bat\s+([\w.$]+)\.\w+\(", str(correction.get("diagnostics", []))))
    names = {name.split(".")[-1].split("$")[0] for name in types}
    retained = [item for item in correction.get("relevant_implementation_sources", [])
                if Path(item["path"]).stem in names]
    # Shared-library method bodies are absent from the temporary service sources.
    for unit in result.get("accepted_units", {}).values():
        if not unit.get("project"):
            continue
        root = Path(unit.get("project", "")).resolve()
        for path in unit.get("files", []):
            if not path.startswith("src/main/java/") or Path(path).stem not in names:
                continue
            source = (root / path).resolve()
            if source.is_relative_to(root) and source.is_file() and path not in {item["path"] for item in retained}:
                retained.append(dict(path=path, content=source.read_text(encoding="utf-8")))
    correction["relevant_implementation_sources"] = retained
    # Maven output and retained report context are already stored in the attempt history.
    correction.pop("original_test_output", None)
    result.pop("failed_test_context", None)
    result.pop("compiler_correction", None)
    result["correction_feedback"] = "Test execution failed; use test_correction diagnostics and latest sources."
    result["accepted_units"] = {key: {field: value for field, value in unit.items()
        if field in {"unit_id", "apis", "public_api", "input_type", "output_type", "wire_type"}}
        for key, unit in result.get("accepted_units", {}).items()}
    closure = result.get("closure", {})
    closure.pop("external_dependencies", None)
    closure.pop("java_classes", None)
    result["test_correction_evidence_policy"] = (
        "Full failing test and directly called implementation sources are supplied. Other collaborators retain "
        "accepted APIs. Compare mocked calls with real methods: preserve required argument mutations and "
        "side effects as well as return values. Original routing/configuration and approved interfaces remain "
        "authoritative. Correct only this scenario; do not alter accepted implementations or passing tests.")
    return result
