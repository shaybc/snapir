"""Locate required APIs in the selected JDK's actual class inventory."""

from functools import lru_cache
import os
from pathlib import Path
import shutil

from models.java_classpath_index import JavaClasspathIndex
from tools.source_discovery_tools.classpath import _index_archive


@lru_cache(maxsize=8)
def _inventory(home, archives):
    """Reuse the intake archive indexer and cache each unchanged JDK inventory."""
    index = JavaClasspathIndex()
    for name, _, _ in archives:
        _index_archive(index, Path(name), platform=True)
    return index.classes


def platform_class_owners(class_names, environment=None):
    """Return only classes proven present in the configured runtime, never prefix guesses."""
    from runtime.java_toolchain import java_environment
    environment = environment or java_environment() or os.environ
    home = environment.get('JAVA_HOME')
    executable = shutil.which('javac', path=environment.get('PATH'))
    root = Path(home) if home else Path(executable).resolve().parent.parent if executable else None
    if root is None:
        return {}
    archives = sorted((root / 'jmods').glob('*.jmod')) if (root / 'jmods').is_dir() else [root / 'jre/lib/rt.jar']
    signature = tuple((str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns)
                      for path in archives if path.is_file())
    inventory = _inventory(str(root.resolve()), signature)
    return {name: inventory[name.replace('$', '.')] for name in class_names if name.replace('$', '.') in inventory}
