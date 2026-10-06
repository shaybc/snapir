"""Index configured JARs and Eclipse library entries without downloading artifacts."""

import os
import shutil
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from models.java_classpath_index import JavaClasspathIndex


def discover_java_classpath(workspace_root: str, jars: list[str] | None = None,
                            variables: dict[str, str] | None = None) -> JavaClasspathIndex:
    """Read explicit libraries and metadata; report unresolved containers and variables.

    This index describes workspace availability, not Maven coordinates, transitive
    dependency resolution, or compiler classpath ordering.
    """
    workspace = Path(workspace_root).resolve()
    index = JavaClasspathIndex()
    libraries = {Path(path).resolve() for path in jars or []}
    for metadata in sorted(workspace.rglob(".classpath")):
        try:
            entries = ElementTree.parse(metadata).getroot().findall("classpathentry")
        except (ElementTree.ParseError, OSError) as exc:
            index.issues.append(f"Invalid classpath {metadata}: {exc}")
            continue
        for entry in entries:
            kind, value = entry.get("kind"), entry.get("path", "")
            if any(node.get("name") == "test" and node.get("value") == "true"
                   for node in entry.findall("attributes/attribute")):
                continue
            if kind == "lib":
                path = Path(value)
                if path.is_absolute() and not path.exists():
                    path = workspace / value.lstrip("/")
                elif not path.is_absolute():
                    path = metadata.parent / path
                libraries.add(path.resolve())
            elif kind == "var":
                name, _, remainder = value.partition("/")
                base = (variables or {}).get(name)
                if base is None:
                    index.issues.append(f"Unresolved Eclipse variable: {name}")
                else:
                    libraries.add((Path(base) / remainder).resolve())
            elif kind == "con" and "JRE_CONTAINER" not in value:
                index.issues.append(f"Unresolved Eclipse classpath container: {value}")
    for library in sorted(libraries):
        _index_archive(index, library, platform=False)
    java_home = os.environ.get("JAVA_HOME")
    executable = shutil.which("javac")
    jdk = Path(java_home) if java_home else Path(executable).resolve().parent.parent if executable else None
    if jdk and (jdk / "jmods").is_dir():
        for module in sorted((jdk / "jmods").glob("*.jmod")):
            _index_archive(index, module, platform=True)
    elif jdk and (jdk / "jre/lib/rt.jar").is_file():
        _index_archive(index, jdk / "jre/lib/rt.jar", platform=True)
    else:
        index.issues.append("JDK class inventory unavailable; configure JAVA_HOME")
    return index


def _index_archive(index, archive, platform):
    if not archive.is_file():
        index.issues.append(f"Missing classpath library: {archive}")
        return
    try:
        with ZipFile(archive) as contents:
            for entry in contents.namelist():
                if not entry.endswith(".class") or entry.startswith("META-INF/"):
                    continue
                if platform:
                    entry = entry.removeprefix("classes/")
                if entry.endswith(("module-info.class", "package-info.class")):
                    continue
                name = entry[:-6].replace("/", ".").replace("$", ".")
                location = ("jdk:" if platform else "jar:") + str(archive)
                locations = index.classes.setdefault(name, [])
                if location not in locations:
                    locations.append(location)
        if not platform:
            index.libraries.append(str(archive))
    except (BadZipFile, OSError) as exc:
        index.issues.append(f"Invalid classpath archive {archive}: {exc}")
