"""Prevent generated production wiring from changing discovered database targets."""

import re
from runtime.java_public_type import _code
from tools.validation_tools.java_comments import mask_java_comments


def validate_connection_wiring(files, proposals, connections):
    """Require selected driver dependencies and reject unsupported vendor driver choices."""
    drivers = {record['driver_class'] for record in connections if record.get('driver_class')}
    schemes = {':'.join(value['scheme']) for record in connections
        for key, value in record.get('connector_configuration', {}).items()
        if isinstance(value, dict) and isinstance(value.get('scheme'), list)
        and value['scheme'] and value['scheme'][0] == 'jdbc'}
    if not drivers:
        return
    known = {(item.group_id, item.artifact_id): item for item in proposals}
    for connection in connections:
        expected = connection.get('driver_dependency')
        if not expected:
            continue
        actual = known.get((expected['group_id'], expected['artifact_id']))
        if not actual or actual.version != expected['version'] or actual.scope not in {'compile', 'runtime'} or (
                expected['scope'] == 'compile' and actual.scope != 'compile'):
            raise ValueError('Production driver must match connector ' + connection['connector_id'] + ': ' +
                expected['group_id'] + ':' + expected['artifact_id'] + ':' + expected['version'] +
                ' in compile/runtime scope. Do not switch the source database vendor.')
    for path, content in files.items():
        if not path.startswith(('src/main/java/', 'src/main/resources/')):
            continue
        source = mask_java_comments(content) if path.endswith('.java') else content
        # Class literals/defaults express an actual choice; pure deployment placeholders
        # remain dynamic values and must not be replaced with an invented vendor.
        declared = re.findall(r'(?:driver-class-name\s*=\s*\$\{[^}:]+:|driverClassName\s*\(\s*")([\w.$]+)', source)
        for driver in declared:
            if driver not in drivers:
                raise ValueError(path + ': driver ' + driver + ' contradicts discovered connector drivers ' + ', '.join(sorted(drivers)))
        for scheme in re.findall(r'\bjdbc:[\w-]+(?=:)', source):
            if schemes and scheme not in schemes:
                raise ValueError(path + ': JDBC URL scheme ' + scheme + ' contradicts discovered connector schemes ' + ', '.join(sorted(schemes)))
