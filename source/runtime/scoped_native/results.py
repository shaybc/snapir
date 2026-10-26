"""Bind native generation results to C5 context/unit proof and checked output bytes."""

from pathlib import Path
from copy import deepcopy

from tools.conversion_tools.scoped_reuse.artifacts import save_validated_output, reuse_validated_output


def fingerprint_payload(payload, category):
    """Exclude only derived dependency advice; actual pins remain build-validated.

    A project's accepted POM supplies known_dependencies on warm resume. It is
    not new source/contract evidence. The native ledger and existing cached build
    validator still verify the exact result, returned files and current POM.
    """
    result = deepcopy(payload)
    if category == 'analysis':
        return result
    result.pop('known_dependencies', None)
    if isinstance(result.get('unit'), dict) and result['unit'].get('unit_id'):
        result['unit'].pop('known_dependencies', None)
    return result


def cached_result(binding, conn, config, profile, category, identity, fingerprint, output):
    """Legacy compatibility is never sufficient for a qualified accepted result."""
    execution, key, unit = binding
    data = reuse_validated_output(conn, config, profile, execution['classpath'], key, unit,
        'result', category + ':' + identity + ':' + fingerprint,
        validator=lambda value: value == output)
    return data == output


def record_result(binding, conn, config, profile, category, identity, fingerprint, output):
    """Persist only after existing schema/compiler/test validators have accepted output."""
    execution, key, unit = binding
    files = []
    project = Path(config.output_root) / key
    # Bind this task's returned native sources. Later units may add files to the
    # same project; they must not make an earlier task's result falsely stale.
    files.extend(project / item['path'] for item in output.get('files', []))
    save_validated_output(conn, config, profile, execution['classpath'], key, unit,
        'result', category + ':' + identity + ':' + fingerprint, output, files,
        validator=lambda value: value == output)


def record_operation(conn, config, profile, key, record):
    """Bind reviewed native assembly metadata and files to its complete checkpoint."""
    from runtime.scoped_native.scope import require_task
    binding = require_task(conn, config, profile, 'service', key, {})
    execution, _, anchor = binding
    if not record['review']['approved'] or record['review']['issues'] or record['review']['unresolved_questions']:
        return
    save_validated_output(conn, config, profile, execution['classpath'], key, anchor,
        'native_artifact', 'native-operation:' + key, record,
        [Path(record['project']) / name for name in record['files']], validator=lambda value: value == record)


def verify_operation(conn, config, profile, key, record):
    """Require the qualified native artifact ledger before packaging a saved operation."""
    from tools.conversion_tools.scoped_reuse.state import checkpoints
    from tools.source_discovery_tools.classpath import discover_java_classpath
    checkpoint = next((item for item in checkpoints(conn, config.run_id).values() if item.operation_key == key), None)
    if checkpoint is None or not checkpoint.units:
        raise ValueError('Qualified native operation checkpoint is missing: ' + key)
    classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    data = reuse_validated_output(conn, config, profile, classpath, key, sorted(checkpoint.units)[0],
        'native_artifact', 'native-operation:' + key, validator=lambda value: value == record)
    if data != record:
        raise ValueError('Qualified native operation artifact proof is missing: ' + key)
