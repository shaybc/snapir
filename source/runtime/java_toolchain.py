"""Select a run's JDK without changing the parent process environment."""

import os
import re
import shutil
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar

import constants

_selected = ContextVar("migration_java_toolchain", default=None)


def jdk_version(home):
    """Read the installed JDK's declared major version and check its executables."""
    root = Path(home)
    suffix = ".exe" if os.name == "nt" else ""
    if not all((root / "bin" / (name + suffix)).is_file() for name in ("java", "javac")):
        raise ValueError(f"Java home must contain java and javac: {root}")
    match = re.search(r'JAVA_VERSION="(\d+)', (root / "release").read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"Cannot determine JDK version: {root}")
    return int(match.group(1))


def resolve_java_home(version, home=None):
    """Use an explicit matching JDK or discover a locally installed matching version."""
    if home:
        root = Path(home).expanduser().resolve()
        if jdk_version(root) != int(version):
            raise ValueError(f"Configured java_home must use Java {version}: {root}")
        return str(root)
    candidates = [os.environ.get("JAVA_HOME")]
    for name in ("javac", "java"):
        executable = shutil.which(name)
        if executable:
            candidates.append(str(Path(executable).resolve().parent.parent))
    roots = [Path.home() / ".jdks", Path("/usr/lib/jvm"), Path("/Library/Java/JavaVirtualMachines")]
    if os.name == "nt":
        base = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        roots.extend(base / name for name in ("Java", "Eclipse Adoptium", "Microsoft", "Amazon Corretto"))
    for root in roots:
        if root.is_dir():
            candidates.extend(str(path / "Contents/Home" if (path / "Contents/Home").is_dir() else path)
                              for path in sorted(root.iterdir()) if path.is_dir())
    for candidate in candidates:
        if candidate:
            try:
                if jdk_version(candidate) == int(version):
                    return str(Path(candidate).resolve())
            except (OSError, ValueError):
                continue
    raise ValueError(f"No installed JDK {version} found. Set java_home in the migration configuration.")


def java_version():
    """Return the active run target, falling back to the central default for standalone tools."""
    return str(_selected.get()[0] if _selected.get() else constants.JAVA_VERSION)


def java_environment(version=None, home=None):
    """Build a child process environment using the selected JDK."""
    selected = _selected.get()
    if version is None and home is None and selected is None:
        return None
    version = version or (selected[0] if selected else constants.JAVA_VERSION)
    home = resolve_java_home(version, home or (selected[1] if selected and str(version) == str(selected[0]) else None))
    environment = os.environ.copy()
    environment["JAVA_HOME"] = home
    environment["PATH"] = str(Path(home) / "bin") + os.pathsep + environment.get("PATH", "")
    return environment


@contextmanager
def java_scope(profile):
    """Bind all Java commands within a run to its verified, resolved JDK."""
    profile.java_home = resolve_java_home(profile.java_version, profile.java_home)
    import logging
    logging.getLogger(__name__).info("Selected Java %s JDK: %s", profile.java_version, profile.java_home)
    token = _selected.set((profile.java_version, profile.java_home))
    try:
        yield
    finally:
        _selected.reset(token)


def run_java(command, **kwargs):
    """Launch a Java, javac, or Maven command in the selected child environment."""
    import subprocess
    environment = kwargs.get("env") or java_environment()
    if environment is not None:
        kwargs.setdefault("env", environment)
        if command[0] in {"java", "javac"}:
            suffix = ".exe" if os.name == "nt" else ""
            command = [str(Path(environment["JAVA_HOME"]) / "bin" / (command[0] + suffix)), *command[1:]]
    return subprocess.run(command, **kwargs)
