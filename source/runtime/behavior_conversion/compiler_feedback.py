"""Explain Java compiler failures using diagnostics, failed sources and verified APIs."""

import re
from pathlib import Path

CORRECTION_INSTRUCTION = """When compiler_correction is supplied, correct the latest failed_sources using
its diagnostics and relevant_dependency_apis. Check every replacement call's parameters and
return type against the verified API. Do not invent methods or change accepted interfaces.
For a missing supporting class or package, check the returned files, supplied accepted native
APIs and retained declared dependencies. When supporting source evidence defines required
behavior with no available native implementation, include that companion implementation in
the corrected bundle and wire its callers, metadata and tests to it. Merely changing the
import, restoring the IBM class or adding only an interface/mock is not a production fix.
Preserve evidenced business behavior and working code; implement behavior locally only when
the original evidence supports it. Compiler diagnostics identify invalid code, not a business
replacement. Keep the original compiler output as supporting evidence and return the complete
corrected bundle, including matching metadata and tests, in the required JSON schema."""


class CompilerCorrectionError(ValueError):
    """Retain compiler context before a candidate's temporary source directory disappears."""

    def __init__(self, message, correction):
        super().__init__(message)
        self.compiler_correction = correction


def compiler_correction(error, sources=(), dependency_apis=(), staged=None):
    """Extract generic Java diagnostics; read only affected files inside the candidate root."""
    headers = re.compile(r"(?:\[ERROR\]\s*)?([^\n]+?\.java):\[(\d+),(\d+)\]\s*([^\n]+)")
    text = str(error)
    matches = list(headers.finditer(text))
    diagnostics, seen = [], set()
    supplied = {item["path"]: item["content"] for item in sources}
    failed = {}
    for index, match in enumerate(matches):
        file = match[1].strip()
        marker = re.search(r"src/(?:main|test)/java/.*", file.replace("\\", "/"))
        relative = marker[0] if marker else file
        line, column, message = int(match[2]), int(match[3]), match[4].strip()
        key = (relative, line, column, message)
        if key in seen:
            continue
        seen.add(key)
        tail = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        details = {}
        for name in ("symbol", "location", "required", "found", "reason"):
            value = re.search(r"(?:^|\n)\s*(?:\[ERROR\]\s*)?" + name + r":\s*([^\n]+)", tail)
            if value:
                details[name] = value[1].strip()
        category = "compiler_error"
        guidance = "Correct the reported code using the supplied evidence and verified APIs."
        if "cannot find symbol" in message:
            category = "missing_symbol"
            guidance = "Use only symbols declared by the verified API; do not invent members or change accepted dependencies."
            if details.get("symbol", "").startswith("class "):
                guidance = ("Resolve " + details["symbol"] + " from returned native files, accepted native APIs or declared ordinary dependencies. "
                    "If supplied supporting source defines required behavior without an available native implementation, "
                    "include its native companion implementation and wire callers, metadata and tests to it; "
                    "do not invent a package, restore an IBM import or provide only an interface/mock.")
        elif "incompatible types" in message:
            category = "incompatible_types"
            guidance = "Match the required type; check the actual return type of the replacement expression."
        elif "does not exist" in message and "package" in message:
            category = "missing_package"
            guidance = ("Use a supplied dependency and its verified APIs, or declare a justified ordinary dependency using known coordinates. "
                "For required supporting behavior supplied as source evidence, include a native companion implementation "
                "when no accepted native API is available; wire callers, metadata and tests to the returned type. "
                "Do not invent a migrated package or restore an IBM import.")
        elif "cannot be applied" in message:
            category = "argument_mismatch"
            guidance = "Match the verified method's parameter count and types."
        source = supplied.get(relative)
        if source is None and staged is not None:
            target = (Path(staged) / relative).resolve()
            if target.is_relative_to(Path(staged).resolve()) and target.is_file():
                source = target.read_text(encoding="utf-8")
        diagnostic = dict(file=relative, line=line, column=column, category=category,
                          message=message, details=details, correction=guidance)
        conversion = re.search(r"incompatible types:\s*(.+?) cannot be converted to (.+)$", message)
        if conversion:
            diagnostic.update(actual_type=conversion[1].strip(), required_type=conversion[2].strip())
        if source is not None:
            failed[relative] = source
            lines = source.splitlines()
            if 0 < line <= len(lines):
                diagnostic["source_line"] = lines[line - 1]
        diagnostics.append(diagnostic)
    if not diagnostics:
        return None
    result = dict(diagnostics=diagnostics,
                  failed_sources=[dict(path=path, content=content) for path, content in failed.items()],
                  original_compiler_output=text)
    return with_dependency_apis(result, dependency_apis)


def with_dependency_apis(correction, dependency_apis):
    """Select supplied APIs referenced by failing source or diagnostic receiver types."""
    if correction is None:
        return None
    correction = dict(correction)
    sources = {item['path']: item['content'] for item in correction['failed_sources']}
    diagnostics = []
    for entry in correction['diagnostics']:
        diagnostic = dict(entry)
        if 'org.mockito' in sources.get(entry.get('file'), '') and 'no suitable method found for thenReturn(' in entry.get('message', ''):
            diagnostic['category'] = 'mock_generic_return_mismatch'
            diagnostic['correction'] = ("Check the inferred return type of the generic mocked call inside when(...), not just the response mock. "
                "Supply the correct explicit method type argument (mock.<ElementType>method(...)) or typed ArgumentMatchers "
                "on that original call; alternatively use Mockito.doReturn(value).when(mock) with the verified method API. "
                "Casting the thenReturn value alone does not fix a call inferred with Object. "
                "Keep the production API, concrete response type, assertions and behavior coverage unchanged.")
            diagnostic['details'] = dict(entry.get('details', {}), overload_diagnostics=[line.strip().removeprefix('[ERROR]').strip()
                for line in correction.get('original_compiler_output', '').splitlines()
                if 'thenReturn(' in line or 'argument mismatch;' in line])
        diagnostics.append(diagnostic)
    correction['diagnostics'] = diagnostics
    context = "\n".join(item["content"] for item in correction["failed_sources"] + correction.get("relevant_implementation_sources", [])) + str(correction["diagnostics"])
    relevant = []
    for dependency in dependency_apis:
        names = [api["type_name"] for api in dependency.get("planned_apis", [])]
        names.extend(path.removesuffix(".java").split("/")[-1]
                     for path in dependency.get("verified_api_surface", {}))
        if any(re.search(r"\b" + re.escape(name.split(".")[-1]) + r"\b", context) for name in names):
            relevant.append(dependency)
    correction["relevant_dependency_apis"] = relevant
    return correction


def request_dependency_apis(request):
    """Collect verified dependency surfaces from unit or operation-assembly requests."""
    apis = list(request.get("converted_dependency_apis", []))
    for identity, unit in request.get("accepted_units", {}).items():
        apis.append(dict(unit_id=unit.get("unit_id", identity),
                         planned_apis=unit.get("apis", unit.get("contract", {}).get("apis", [])),
                         verified_api_surface=unit.get("public_api", {})))
    return apis
