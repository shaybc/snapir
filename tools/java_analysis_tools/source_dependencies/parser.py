"""Invoke the installed JDK parser once per source inventory, with temporary reports."""

import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree


def parse_source_references(paths):
    """Return syntax evidence; never execute workspace code or fetch dependencies."""
    paths = sorted(set(str(Path(path).resolve()) for path in paths))
    if not paths:
        return ElementTree.Element("analysis")
    with tempfile.TemporaryDirectory(prefix="snapir-java-references-") as temporary:
        root = Path(temporary)
        manifest = ElementTree.Element("sources")
        for path in paths:
            ElementTree.SubElement(manifest, "source", path=path)
        ElementTree.ElementTree(manifest).write(root / "sources.xml", encoding="utf-8", xml_declaration=True)
        scanner = Path(__file__).with_name("SourceReferenceScanner.java")
        try:
            result = subprocess.run(["java", str(scanner), str(root / "sources.xml"), str(root / "references.xml")],
                                    capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Java source dependency analysis requires an available JDK") from exc
        if result.returncode:
            raise ValueError("JDK source dependency parser failed: " + result.stderr[-2000:])
        return ElementTree.parse(root / "references.xml").getroot()
