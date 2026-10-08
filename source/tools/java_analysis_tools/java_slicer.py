from __future__ import annotations

import re


def extract_method(source: str, method_name: str) -> str | None:
    """Extract a named Java method using signature matching and balanced braces."""
    for match in re.finditer(rf"\b{re.escape(method_name)}\s*\(", source):
        if match.start() > 0 and source[match.start() - 1] == ".":
            continue
        signature_start = _find_signature_start(source, match.start())
        body_start = _find_method_body_start(source, match.end())
        if body_start is None:
            continue
        body_end = _find_matching_brace(source, body_start)
        if body_end is None:
            continue
        return source[signature_start:body_end + 1].strip()
    return None


def extract_execute_method(source: str) -> str | None:
    """Extract the execute method from a Java source string."""
    return extract_method(source, "execute")


def extract_imports(source: str) -> list[str]:
    """Return imported Java types as fully qualified class names."""
    imports: list[str] = []
    for match in re.finditer(r"^\s*import\s+(?:static\s+)?([^;]+);", source, re.MULTILINE):
        imports.append(match.group(1).strip())
    return imports


def extract_ibm_imports(source: str) -> list[str]:
    """Return imported IBM and WebSphere Java types."""
    return [
        imported
        for imported in extract_imports(source)
        if imported == "com.ibm" or imported.startswith("com.ibm.")
    ]


def _find_signature_start(source: str, method_name_start: int) -> int:
    line_start = source.rfind("\n", 0, method_name_start) + 1
    while line_start > 0:
        previous_line_start = source.rfind("\n", 0, line_start - 1) + 1
        previous_line = source[previous_line_start:line_start].strip()
        if not previous_line.startswith("@"):
            break
        line_start = previous_line_start
    return line_start


def _find_method_body_start(source: str, search_start: int) -> int | None:
    paren_depth = 1
    index = search_start
    while index < len(source):
        char = source[index]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
            if paren_depth == 0:
                break
        index += 1
    if paren_depth != 0:
        return None
    while index < len(source):
        if source[index] == "{":
            return index
        if source[index] == ";":
            return None
        index += 1
    return None


def _find_matching_brace(source: str, open_brace_index: int) -> int | None:
    depth = 0
    index = open_brace_index
    while index < len(source):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None
