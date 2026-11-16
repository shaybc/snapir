"""Inventory explicitly configured framework archives without executing their classes."""
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import re

from tools.composer_mapper_tools.scoped_intake_evidence import file_digest


def framework_libraries(paths):
    """Return exact class ownership and archive revisions, never decompiled source."""
    libraries = {}
    for value in paths:
        path = Path(value).resolve()
        if str(path) in libraries:
            continue
        try:
            before = file_digest(path)
            with ZipFile(path) as archive:
                classes = set()
                for name in archive.namelist():
                    name = re.sub(r'^META-INF/versions/\d+/', '', name)
                    if name.endswith('.class') and not name.startswith('META-INF/') and name.rsplit('/', 1)[-1] not in {'module-info.class', 'package-info.class'}:
                        classes.add(name[:-6].replace('/', '.'))
            if file_digest(path) != before:
                raise ValueError('Framework JAR changed while indexing: ' + str(path))
        except (OSError, BadZipFile) as error:
            raise ValueError('Framework JAR is missing, unreadable or invalid: ' + str(path)) from error
        libraries[str(path)] = dict(path=str(path), sha256=before, classes=sorted(classes))
    return list(libraries.values())
