"""Identify driver coordinates from actual configured classpath JARs."""

import hashlib
import re
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree
from tools.maven_dependency_tools.jar_metadata import archive_coordinates


def driver_candidates(driver_class, classpath):
    """Return source-backed coordinates or explicit gaps, never infer a filename version."""
    candidates = []
    for location in classpath.classes.get(driver_class, []):
        if not location.startswith('jar:'):
            continue
        path = Path(location[4:])
        try:
            with ZipFile(path) as jar:
                manifest = jar.read('META-INF/MANIFEST.MF').decode('utf-8', errors='replace') if 'META-INF/MANIFEST.MF' in jar.namelist() else ''
            coordinates = archive_coordinates(path)
            item = dict(jar=path.name, jar_hash=hashlib.sha256(path.read_bytes()).hexdigest(), driver_class=driver_class)
            if coordinates:
                values = dict(zip(('groupId', 'artifactId', 'version'), coordinates))
                item['dependency'] = dict(group_id=values['groupId'], artifact_id=values['artifactId'], version=values['version'],
                    scope='runtime', reason='Driver identified in configured workspace classpath JAR', required_classes=[driver_class])
            else:
                item['issue'] = 'Driver JAR Maven coordinates are missing or ambiguous'
            version = re.search(r'(?m)^Implementation-Version:\s*(.+)$', manifest)
            if version:
                item['manifest_version'] = version[1].strip()
            candidates.append(item)
        except (OSError, ValueError, BadZipFile, ElementTree.ParseError) as exc:
            candidates.append(dict(jar=path.name, driver_class=driver_class, issue='Unreadable driver JAR: ' + str(exc)))
    return candidates
