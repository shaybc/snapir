from __future__ import annotations

import re
from dataclasses import dataclass, field

from tools.java_analysis_tools.java_slicer import extract_ibm_imports


@dataclass
class JavaClassSummary:
    """Structured Java class facts used as deterministic conversion evidence."""

    class_name: str
    package: str
    fqcn: str
    parent_class: str | None
    interfaces: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    setters: list[str] = field(default_factory=list)
    ibm_imports: list[str] = field(default_factory=list)
    return_codes: dict[str, list[str]] = field(default_factory=dict)
    behavior_types: list[str] = field(default_factory=list)
    context_fields_written: list[str] = field(default_factory=list)
    context_fields_read: list[str] = field(default_factory=list)
    source_char_count: int = 0


def summarise_java_class(
    source: str,
    parent_class: str | None,
    interfaces: list[str],
) -> JavaClassSummary:
    """Build a deterministic structural summary from Java source text."""
    package = _extract_package(source)
    class_name = _extract_class_name(source)
    methods = _extract_method_names(source)
    context_fields_written = _detect_context_fields(
        source,
        call_names=("setValueAt", "setValue"),
    )
    context_fields_read = _detect_context_fields(
        source,
        call_names=("getValueAt", "getValue"),
    )
    return JavaClassSummary(
        class_name=class_name,
        package=package,
        fqcn=f"{package}.{class_name}" if package and class_name else class_name,
        parent_class=parent_class,
        interfaces=interfaces,
        methods=methods,
        setters=[method for method in methods if method.startswith("set")],
        ibm_imports=extract_ibm_imports(source),
        return_codes=_extract_return_codes(source),
        behavior_types=_detect_behavior_types(source),
        context_fields_written=context_fields_written,
        context_fields_read=context_fields_read,
        source_char_count=len(source),
    )


def detect_context_access_patterns(source: str) -> list[str]:
    """Extract context field names referenced by getValue/setValue style calls."""
    return sorted(set(_detect_context_fields(
        source,
        call_names=("setValueAt", "getValueAt", "setValue", "getValue"),
    )))


def _extract_package(source: str) -> str:
    match = re.search(r"^\s*package\s+([^;]+);", source, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_class_name(source: str) -> str:
    match = re.search(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b", source)
    return match.group(1) if match else ""


def _extract_method_names(source: str) -> list[str]:
    names = []
    pattern = re.compile(
        r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*"
        r"(?:public|protected|private)\s+"
        r"(?:static\s+)?(?:final\s+)?[\w<>\[\], ?]+\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        re.MULTILINE,
    )
    for match in pattern.finditer(source):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return names


def _detect_context_fields(source: str, call_names: tuple[str, ...]) -> list[str]:
    calls = "|".join(re.escape(call_name) for call_name in call_names)
    pattern = re.compile(rf"\.(?:{calls})\s*\(\s*\"([^\"]+)\"")
    return sorted(set(match.group(1) for match in pattern.finditer(source)))


def _extract_return_codes(source: str) -> dict[str, list[str]]:
    codes: dict[str, list[str]] = {}
    for match in re.finditer(r"\breturn\s+([A-Za-z_][A-Za-z0-9_]*|-?\d+|\"[^\"]+\")\s*;", source):
        code = match.group(1).strip('"')
        codes.setdefault(code, [])
    return codes


def _detect_behavior_types(source: str) -> list[str]:
    behavior_types = set()
    lower_source = source.lower()
    if "sql" in lower_source or "preparedstatement" in lower_source or "resultset" in lower_source:
        behavior_types.add("database")
    if "http" in lower_source or "urlconnection" in lower_source:
        behavior_types.add("http")
    if "jms" in lower_source or "queue" in lower_source:
        behavior_types.add("messaging")
    if "context." in lower_source or "getvalue" in lower_source or "setvalue" in lower_source:
        behavior_types.add("context_access")
    return sorted(behavior_types)
