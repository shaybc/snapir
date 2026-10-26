"""Classify explicit imports using discovered source and binary class indexes."""

import re
from pathlib import Path


def classify_java_imports(source_path: str, source_index, classpath_index) -> list[dict]:
    """Report dependency evidence without claiming compilation or behavioral equivalence.

    Wildcard imports require compiler analysis and are reported for review. IBM
    types remain replacement requirements even when a legacy library provides them.
    """
    from tools.java_analysis_tools.java_text import read_java_text
    source = read_java_text(source_path, strip_bom=True)
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    results = []
    for match in re.finditer(r"^\s*import\s+(static\s+)?([\w.*]+)\s*;", source, re.M):
        name = match.group(2)
        wildcard = name.endswith(".*")
        if wildcard and not match.group(1):
            results.append(dict(import_name=name, kind="needs_review", locations=[], reason="Wildcard requires compiler resolution"))
            continue
        if match.group(1):
            name = name.rsplit(".", 1)[0]
        locations = ["source:" + path for path in source_index.classes.get(name, [])]
        locations += classpath_index.classes.get(name, [])
        # Nested source types are declared inside their enclosing source file.
        parent = name
        while not locations and "." in parent:
            parent = parent.rsplit(".", 1)[0]
            locations = ["source:" + path for path in source_index.classes.get(parent, [])]
        framework = name.startswith(("com.ibm.", "javax.ejb.", "javax.rmi.", "org.omg."))
        kind = "replacement_required" if framework else "ambiguous" if len(locations) > 1 else (
            "source" if locations and locations[0].startswith("source:") else
            "platform" if locations and locations[0].startswith("jdk:") else
            "library" if locations else "missing")
        results.append(dict(import_name=match.group(2), kind=kind, locations=locations))
    return results
