"""Read exact coordinates from archive-owned metadata or a neighboring original POM."""

import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree


def archive_coordinates(path):
    """Multiple embedded POM identities are ambiguous, not a filename-based guess."""
    candidates = set()
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith('META-INF/maven/') and name.endswith('/pom.properties'):
                if archive.getinfo(name).file_size > 1024 * 1024:
                    raise ValueError('Archive Maven metadata exceeds 1 MiB')
                values = dict(re.findall(r'(?m)^\s*(groupId|artifactId|version)\s*[=:]\s*(\S+)\s*$', archive.read(name).decode('utf-8', errors='replace')))
                if len(values) == 3:
                    candidates.add((values['groupId'], values['artifactId'], values['version']))
    sidecar = Path(path).with_suffix('.pom')
    if not candidates and sidecar.is_file():
        if sidecar.stat().st_size > 1024 * 1024:
            raise ValueError('Archive POM exceeds 1 MiB')
        root = ElementTree.parse(sidecar).getroot()
        values = [root.findtext('{*}' + key) or (root.findtext('{*}parent/{*}' + key) if key != 'artifactId' else None)
                  for key in ('groupId', 'artifactId', 'version')]
        if all(value and '${' not in value for value in values):
            candidates.add(tuple(values))
    return next(iter(candidates)) if len(candidates) == 1 else None
