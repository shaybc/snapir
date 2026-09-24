from __future__ import annotations

from pathlib import Path


def scan_for_ibm_dependencies(
    generated_path: str,
    forbidden_patterns: list[str],
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
            for pattern in _matched_patterns(line, forbidden_patterns):
                findings.append(f"{path}:{line_number}:{pattern}")
    return findings


def scan_source(java_source: str, forbidden_patterns: list[str]) -> list[str]:
    """Scan one Java source string and return forbidden patterns found."""
    matches = []
    for line in java_source.splitlines():
        if not _should_scan_line(line):
            continue
        for pattern in _matched_patterns(line, forbidden_patterns):
            if pattern not in matches:
                matches.append(pattern)
    return matches


def is_clean(generated_path: str, forbidden_patterns: list[str]) -> bool:
    """Return True when no forbidden dependency references are found."""
    return not scan_for_ibm_dependencies(generated_path, forbidden_patterns)


def _should_scan_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("import ") or '"' in stripped


def _matched_patterns(line: str, forbidden_patterns: list[str]) -> list[str]:
    lower_line = line.lower()
    return [pattern for pattern in forbidden_patterns if pattern.lower() in lower_line]
