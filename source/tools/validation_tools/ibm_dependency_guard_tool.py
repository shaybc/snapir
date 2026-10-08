from __future__ import annotations

from pathlib import Path
import re


def scan_for_ibm_dependencies(
    generated_path: str,
    forbidden_patterns: list[str],
    *,
    allowed_classes=(),
) -> list[str]:
    """Scan Java files under a path for forbidden IBM dependency references."""
    findings = []
    root = Path(generated_path)
    paths = [root] if root.is_file() else sorted(root.rglob("*.java"))
    for path in paths:
        if path.suffix != ".java":
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not _should_scan_line(line):
                continue
            for pattern in _matched_patterns(line, forbidden_patterns, allowed_classes):
                findings.append(f"{path}:{line_number}:{pattern}")
    return findings


def scan_source(java_source: str, forbidden_patterns: list[str], *, allowed_classes=()) -> list[str]:
    """Scan one Java source string and return forbidden patterns found."""
    matches = []
    for line in java_source.splitlines():
        if not _should_scan_line(line):
            continue
        for pattern in _matched_patterns(line, forbidden_patterns, allowed_classes):
            if pattern not in matches:
                matches.append(pattern)
    return matches


def is_clean(generated_path: str, forbidden_patterns: list[str]) -> bool:
    """Return True when no forbidden dependency references are found."""
    return not scan_for_ibm_dependencies(generated_path, forbidden_patterns)


def _should_scan_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("import ") or '"' in stripped


def _matched_patterns(line: str, forbidden_patterns: list[str], allowed_classes=()) -> list[str]:
    lower_line = line.lower()
    imported = re.fullmatch(r"\s*import\s+([\w.]+)\s*;\s*", line)
    if imported and imported.group(1) in allowed_classes:
        if not imported.group(1).startswith(("com.ibm.websphere.", "com.ibm.wsbcc.", "com.ibm.dse.", "javax.ejb.", "javax.rmi.", "org.omg.")):
            return [pattern for pattern in forbidden_patterns
                    if pattern.lower() != "com.ibm" and pattern.lower() in lower_line]
    return [pattern for pattern in forbidden_patterns if pattern.lower() in lower_line]
