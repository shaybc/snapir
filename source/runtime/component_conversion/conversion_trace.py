"""Best-effort converter diagnostics; recording must never change conversion outcomes."""
import json
import logging
from pathlib import Path

from tools.state_store_tools._json import utc_now


def _directory(config):
    return Path(config.db_path).resolve().parent.parent if getattr(config, 'db_path', None) else Path(config.output_root).resolve().parent


def _read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def record_trace(config, directory, plan, boundaries, units, report):
    """Snapshot only already-resolved records, including every current terminal/deferred outcome."""
    try:
        from tools.conversion_tools.conversion_graph_records import graph_from_records
        root = Path(directory)
        records_root = _directory(config)
        graph = graph_from_records(config.run_id, plan, boundaries, units, report,
            validation=_read(records_root / 'state/conversion-trace-validation.json', {}),
            blockers=_read(records_root / 'state/conversion-trace-blockers.json', []))
        graph.recorded_at = utc_now()
        _write(root / 'state/conversion-graph.json', graph.model_dump(mode='json'))
    except Exception:
        logging.getLogger(__name__).warning('Conversion graph evidence could not be recorded; conversion continues unchanged', exc_info=True)


def record_blocker(config, plan, group_id, dependency_group, reason):
    """Record the prerequisite that the converter is actually rejecting, before its existing error."""
    try:
        path = _directory(config) / 'state/conversion-trace-blockers.json'
        values = _read(path, [])
        item = dict(plan_fingerprint=plan.fingerprint, group_id=group_id,
                    dependency_group=dependency_group, reason=reason)
        if item not in values:
            values.append(item)
        _write(path, values)
    except Exception:
        logging.getLogger(__name__).warning('Conversion blocker trace unavailable; original error is unchanged', exc_info=True)


def record_validation(config, plan, contracts, results):
    """Retain recorded native API ownership and comparison outcomes after normal publication succeeds."""
    try:
        path = _directory(config) / 'state/conversion-trace-validation.json'
        values = _read(path, {})
        for key, result in results.items():
            report = json.loads((Path(result.artifact_root) / result.validation_report).read_text(encoding='utf-8'))
            contract = contracts[key]
            apis = contract.apis if hasattr(contract, 'apis') else contract.get('apis', [])
            values[key] = dict(plan_fingerprint=plan.fingerprint, result_revision=result.validation_report_hash,
                native_apis=[api.type_name if hasattr(api, 'type_name') else api['type_name'] for api in apis],
                comparisons=report.get('standalone_comparisons') or report.get('format_comparison') or {},
                evidence=dict(record='component_validation', file=str(Path(result.artifact_root) / result.validation_report),
                              sha256=result.validation_report_hash))
        _write(path, values)
    except Exception:
        logging.getLogger(__name__).warning('Conversion validation trace unavailable; validated artifacts are unchanged', exc_info=True)


def record_reuse(config, conn, plan, group):
    """Read an already-validated reuse receipt without adding a new acceptance gate."""
    try:
        from tools.state_store_tools import component_records as records
        from models.native_component_result import NativeComponentResult
        head = records.head(conn, config.run_id, group.group_id)
        contracts = records.read_record(conn, config.run_id, group.group_id, 'contract', head['contract_revision'])['contracts']
        saved = records.read_record(conn, config.run_id, group.group_id, 'result', head['result_revision'])['results']
        record_validation(config, plan, contracts, {key: NativeComponentResult.model_validate(value) for key, value in saved.items()})
    except Exception:
        logging.getLogger(__name__).warning('Component reuse trace unavailable; reuse result is unchanged', exc_info=True)


def record_preparation_failure(config, profile, directory, error):
    """Preserve a run-level preparation failure without blaming an unexamined dependency."""
    try:
        from models.conversion_graph import ConversionGraph
        from tools.conversion_tools.scoped_reuse.fingerprints import digest
        graph = ConversionGraph(run_id=config.run_id, recorded_at=utc_now())
        failure = 'preparation-failure'
        graph.nodes[failure] = dict(id=failure, label='Converter preparation failed', kind='preparation',
            status='failed', decision='converter_error', reason=str(error), issues=[], entry_points=[],
            evidence=[dict(record='standalone_preparation_failure')])
        for name in profile.selected_components:
            key = 'requested-' + digest(name)
            graph.nodes[key] = dict(id=key, label=name, kind='requested_component', status='not_run',
                decision='selected', issues=['Preparation failed before a complete component plan was available'],
                entry_points=[], evidence=[dict(record='saved_profile', field='selected_components')])
            graph.roots.append(key)
            graph.edges.append(dict(id='blocked-' + digest(name), **{'from': key, 'to': failure},
                                    relation='blocked_by', evidence=dict(record='standalone_preparation_failure')))
        graph.snapshot_id = digest(graph.model_dump(mode='json', exclude={'snapshot_id', 'recorded_at'}))
        _write(Path(directory) / 'state/conversion-graph.json', graph.model_dump(mode='json'))
    except Exception:
        logging.getLogger(__name__).warning('Preparation failure trace unavailable; original error is unchanged', exc_info=True)
