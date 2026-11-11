"""Assemble stage-specific conversion histories from saved evidence only."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from models.conversion_ai_report import ConversionAiReport
from runtime.model_execution.error_details import sanitize_diagnostic
from tools.run_diagnostics.ai_attempt_evidence import (snapshot, read_json, journal, blob_reference,
                                                       material_text, legacy_logs, saved_file_reference)
from tools.run_diagnostics.ai_response_findings import finding, error_location

STAGE = 'dependency_closure_and_component_conversion'


def is_conversion_phase(phase):
    """Select AI conversion checkpoints, leaving pre-conversion preparation diagnosis intact."""
    return str(phase or '').startswith(('conversion_components_', 'conversion_units_',
        'conversion_scoped_native_', 'conversion_component_', 'component_correction_',
        'conversion_pending', 'conversion_in_progress'))


def _target(targets, identity, request=None):
    request = request or {}
    identity = str(identity or 'unidentified')
    target = targets.setdefault(identity, dict(identity=identity, name=identity, type='conversion target',
        consumers=[], directions=[], result='not established', attempts=[], budget_checks=[]))
    components = request.get('components') or {}
    if isinstance(components, dict) and components:
        names, roles, kinds = [], set(), set()
        for component in components.values():
            if not isinstance(component, dict):
                continue
            names.append(component.get('label') or identity)
            roles.update(component.get('roles', []))
            kinds.add(component.get('kind'))
            target['consumers'] = sorted(set(target['consumers']) | set(component.get('operations', [])))
        target['name'] = ', '.join(names) or identity
        if 'format_composition' in kinds:
            target['type'] = 'configured format'
        elif 'decorator' in roles:
            target['type'] = 'decorator'
        elif {'format_leaf', 'format_wrapper'} & roles:
            target['type'] = 'basic format'
        elif 'configured_step' in kinds or any('step' in role for role in roles):
            target['type'] = 'OP step'
        else:
            target['type'] = 'shared component'
    elif request.get('kind') in {'request_unformat', 'response_format', 'configured_step'}:
        target['type'] = 'OP step' if request['kind'] == 'configured_step' else 'configured format'
        target['name'] = request.get('logical_id') or request.get('name') or target['name']
    configured = request.get('configured_format') or request.get('unit') or request
    if not isinstance(configured, dict):
        configured = request
    if target['name'] == identity and configured.get('logical_id'):
        target['name'] = configured['logical_id']
    direction = request.get('direction') or {'request_unformat': 'unformat', 'response_format': 'format'}.get(configured.get('kind'))
    if direction:
        target['directions'] = sorted(set(target['directions']) | {direction})
    for lifecycles in (request.get('format_lifecycles') or {}).values():
        for lifecycle in lifecycles:
            if lifecycle.get('direction') in {'format', 'unformat'}:
                target['directions'] = sorted(set(target['directions']) | {lifecycle['direction']})
    return target


def _request(text):
    try:
        value = json.loads(text or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def _identity(request, fallback):
    return request.get('group_id') or request.get('unit_id') or request.get('operation_identity') or fallback


def _conversion_request(category, request):
    """Keep planning, review and assembly records out of the conversion history."""
    if str(category or '').startswith(('planning', 'review', 'component_review', 'operation_assembly', 'service_')):
        return False
    if request.get('assembly_phase') or request.get('kind') in {'operation_assembly', 'service_generation'}:
        return False
    return bool(request.get('group_id') or request.get('unit_id') or request.get('kind') in
        {'request_unformat', 'response_format', 'configured_step', 'basic_component', 'format_implementation', 'format_composition'}
        or str(category or '').startswith(('component_generation', 'staged_', 'unit')))


def _database_attempts(directory, evidence, targets):
    snapshots = {(row['category'], row['identity'], row['fingerprint']): row for row in evidence['behavior_snapshots']}
    ordinary = evidence['behavior_attempts']
    for table, records in (('behavior_attempts', ordinary), ('staged_conversion_attempts', evidence['staged_conversion_attempts'])):
        for row in records:
            category = row.get('category') or 'staged_' + row['stage']
            if table == 'staged_conversion_attempts' and any(item['category'] == category and
                    item['identity'] == row['identity'] + ':' + row['revision'] for item in ordinary):
                continue  # Staged reservations corroborate ordinary records, not additional model calls.
            request = _request(row.get('request_json'))
            if not _conversion_request(category, request):
                continue
            target = _target(targets, _identity(request, row['identity']), request)
            saved = snapshots.get((category, row['identity'], row.get('fingerprint')))
            completed = bool(saved and saved['status'] == 'accepted' and row.get('error') is None and
                             row.get('response') is not None)
            outcome = finding(row.get('response'), row.get('error'), completed=completed)
            attempt = dict(id=hashlib.sha256(f"{table}:{row['evidence_rowid']}".encode()).hexdigest()[:24],
                category=category, identity=row['identity'], fingerprint=row.get('fingerprint', ''),
                number=row['attempt'], timestamp=row.get('created_at') or row.get('updated_at'),
                outcome=outcome,
                parser_location=error_location(row.get('error')) if outcome.startswith('invalid_json') else None, deliveries=[],
                materials={}, evidence=[dict(file='state/migration.db', table=table, rowid=row['evidence_rowid'])])
            if row.get('error'):
                attempt['error_summary'] = sanitize_diagnostic(row['error']).splitlines()[0][:240]
            for name, column in (('request', 'request_json'), ('response', 'response'), ('error', 'error')):
                if row.get(column) is not None:
                    attempt['materials'][name] = dict(storage='database', table=table,
                        column=column, rowid=row['evidence_rowid'], exact_application_text=name == 'response')
            target['attempts'].append(attempt)
            if completed and category == 'unit':
                target['result'] = 'saved unit accepted (receipt; freshness not rechecked)'


def _journal_attempts(directory, events, targets, limitations):
    traces = {}
    trace_targets = {}
    for event in events:
        identity = event.get('identity')
        if not identity:
            continue
        request_ref = blob_reference(event, 'request')
        try:
            request = _request(material_text(directory, request_ref)) if request_ref else {}
        except (OSError, ValueError):
            request = {}
            limitations.add('Some captured materials are missing or fail checksum verification.')
        if event.get('trace_id') not in trace_targets and not _conversion_request(event.get('category'), request):
            continue
        target = _target(targets, trace_targets.get(event.get('trace_id')) or _identity(request, identity), request)
        if event['event'] == 'budget_check':
            check = dict(stage=event.get('budget_stage'), decision=event.get('decision'),
                characters=event.get('characters'), character_limit=event.get('character_limit'),
                timestamp=event.get('timestamp'), materials={})
            for name in ('request', 'instructions'):
                reference = blob_reference(event, name)
                if reference:
                    check['materials'][name] = reference
            if check not in target['budget_checks']:
                target['budget_checks'].append(check)
            continue
        trace = event.get('trace_id')
        if not trace:
            continue
        trace_targets[trace] = target['identity']
        attempt = traces.get(trace)
        if attempt is None:
            matches = [item for item in target['attempts'] if item['category'] == event.get('category')
                       and item['identity'] == identity and item['fingerprint'] == event.get('fingerprint', '')
                       and item['number'] == event.get('attempt')]
            if len(matches) == 1:
                attempt = matches[0]
            else:
                attempt = dict(id=trace, category=event.get('category'), identity=identity,
                    fingerprint=event.get('fingerprint', ''), number=event.get('attempt'),
                    timestamp=event.get('timestamp'), outcome='in_progress_or_unknown',
                    materials={}, deliveries=[], evidence=[])
                target['attempts'].append(attempt)
            traces[trace] = attempt
        for name in ('request', 'instructions', 'response', 'error'):
            reference = blob_reference(event, name)
            if reference:
                attempt['materials'][name] = reference
        if event['event'] in {'generation_response', 'validation_failed', 'validation_passed'}:
            try:
                response = material_text(directory, attempt['materials'].get('response'))
            except (OSError, ValueError):
                response = None
            attempt['outcome'] = finding(response, event.get('error'), completed=event['event'] == 'validation_passed')
            attempt['parser_location'] = error_location(event.get('error')) if attempt['outcome'].startswith('invalid_json') else None
            if event.get('error'):
                attempt['error_summary'] = sanitize_diagnostic(event['error']).splitlines()[0][:240]
        delivery_id = event.get('delivery_id')
        if delivery_id:
            delivery = next((item for item in attempt['deliveries'] if item['id'] == delivery_id), None)
            if delivery is None:
                delivery = dict(id=delivery_id, number=event.get('delivery_attempt'), outcome='dispatch_attempted', http_status=None)
                attempt['deliveries'].append(delivery)
            if event['event'] == 'http_response':
                delivery['http_status'] = event.get('http_status') if isinstance(event.get('http_status'), int) else None
                delivery['gateway_request_id'] = event.get('gateway_request_id')
            if event['event'] == 'delivery_failed':
                delivery['outcome'] = finding(error=event.get('error'))
                if delivery['outcome'] in {'failure_without_response', 'in_progress_or_unknown'}:
                    delivery['outcome'] = 'delivery_failed'
                reference = blob_reference(event, 'error')
                if reference:
                    delivery['error_material'] = reference
                if isinstance(event.get('http_status'), int):
                    delivery['http_status'] = event['http_status']
            if event['event'] == 'response_received':
                delivery['outcome'] = 'response_received'


def build_report(directory):
    """Collect a current conversion view without executing prior-stage investigations."""
    directory = Path(directory).resolve()
    evidence = snapshot(directory)
    run = evidence['run']
    limitations = {'HTTP status is unknown unless explicitly captured; received text is not proof of HTTP 200 or accepted conversion.',
        'Historical database requests may include later validation feedback; uncaptured instructions are unavailable.'}
    targets = {}
    if evidence['unavailable_tables']:
        limitations.add('Optional saved evidence tables are absent: ' + ', '.join(evidence['unavailable_tables']) + '.')
    for row in evidence['conversion_component_plans']:
        plan = _request(row['plan_json'])
        for group in plan.get('groups', []):
            components = {key: plan.get('components', {}).get(key, {}) for key in group.get('members', [])}
            _target(targets, group['group_id'], dict(components=components))
    _database_attempts(directory, evidence, targets)
    events = journal(directory, limitations)
    _journal_attempts(directory, events, targets, limitations)
    for row in evidence['shared_component_consumers']:
        target = _target(targets, row['group_id'])
        try:
            target['consumers'] = sorted(set(target['consumers']) | set(json.loads(row['consumers_json'])))
        except ValueError:
            limitations.add('Some saved consumer associations are unreadable.')
    reports = sorted(directory.glob('**/reports/3_dependency_closure_and_component_conversion/component-generation.json'))
    for path in reports:
        for identity, result in (read_json(path, {}) or {}).get('groups', {}).items():
            target = _target(targets, identity)
            target.setdefault('result_evidence', []).append(dict(file=path.relative_to(directory).as_posix(),
                status=result.get('status'), reused=result.get('reused', False)))
            target['result'] = ('reused validated component' if result.get('reused') else 'component validated (build/tests)') if result.get('status') == 'component_validated' else str(result.get('status', 'unknown'))
            if result.get('reason'):
                target['blocker'] = finding(error=result['reason'])
                target['blocker_summary'] = sanitize_diagnostic(result['reason']).splitlines()[0][:240]
    for row in evidence['conversion_component_heads']:
        target = _target(targets, row['group_id'])
        target['component_head_status'] = row['status']
        if row['status'] == 'component_validated' and 'validated' not in target['result']:
            target['result'] = 'component_validated (saved component head)'
        elif (row['status'] != 'component_validated' and 'validated' in target['result']) or target['result'] == 'not established':
            target['result'] = str(row['status']) + ' (saved component head)'
    # Historical oversized captures are also useful before correlation capture was installed.
    for path in sorted(directory.glob('**/reports/oversized_model_requests/*/metadata.json')):
        if path.is_symlink() or not path.resolve().is_relative_to(directory):
            continue
        metadata = read_json(path, {}) or {}
        identity = metadata.get('request_id')
        if identity:
            folder = path.parent
            materials = {}
            for name, filename in (('request', 'request.json'), ('instructions', 'instructions.txt')):
                try:
                    materials[name] = saved_file_reference(directory, folder / filename)
                except (OSError, ValueError):
                    limitations.add('Some historical oversized materials are unavailable; no reconstruction performed.')
            try:
                request = _request(material_text(directory, materials.get('request')))
            except (OSError, ValueError):
                request = {}
            if not _conversion_request(None, request):
                continue
            target = _target(targets, _identity(request, identity), request)
            target.setdefault('oversized_captures', []).append(folder.relative_to(directory).as_posix())
            check = dict(stage=metadata.get('stage'), decision='too_large',
                characters=metadata.get('total', {}).get('characters'), character_limit=metadata.get('character_limit'))
            existing = next((item for item in target['budget_checks'] if all(item.get(key) == value for key, value in check.items())), None)
            if existing is None:
                check['materials'] = materials
                target['budget_checks'].append(check)
            else:
                existing.setdefault('materials', materials)
    labels = {'Basic native group: ' + item['name']: key for key, item in targets.items() if item['name'] != key}
    for event in legacy_logs(directory, labels, limitations):
        target = targets[event.pop('target')]
        if not any(item['deliveries'] for item in target['attempts']):
            target.setdefault('legacy_delivery_evidence', []).append(event)
    active = next((row['operation_key'] for row in evidence['operation_workflow_progress'] if row['status'] != 'completed'), None)
    if not events:
        limitations.add('This run predates correlated attempt capture; delivery retry counts and exact HTTP status may be unavailable.')
    return ConversionAiReport(run_id=directory.name, status=str(run['status']), checkpoint=str(run['current_phase']),
        stage=STAGE, observed_at=datetime.now(timezone.utc).isoformat(), active_operation=active,
        targets=list(targets.values()), limitations=sorted(limitations))


def format_report(report):
    """Render concise per-target histories; material bodies stay in inspectable exports."""
    lines = ['SAVED RUN DIAGNOSTIC (read-only)', 'Run: ' + report.run_id,
        'State: ' + report.status + ' / ' + report.checkpoint, 'Stage: Dependency closure and component conversion',
        'Observed: ' + report.observed_at]
    if report.active_operation:
        lines.append('Active operation: ' + report.active_operation)
    counts = Counter(item['result'] for item in report.targets)
    lines.append('Targets: ' + str(len(report.targets)) + '; results: ' + ', '.join(f'{key}={value}' for key, value in counts.items()))
    for target in report.targets:
        lines += ['', target['type'] + ': ' + sanitize_diagnostic(target['name']), '  ID: ' + sanitize_diagnostic(target['identity'])]
        if target['consumers']:
            lines.append('  Consumers: ' + ', '.join(sanitize_diagnostic(value) for value in target['consumers']))
        if target['directions']:
            lines.append('  Directions: ' + ', '.join(target['directions']))
        for check in target['budget_checks']:
            lines.append(f"  Budget check ({check.get('stage')}): {check.get('characters')} characters / {check.get('character_limit')}; {check.get('decision')}")
        if target['budget_checks'] and not target['attempts'] and all(item['decision'] == 'too_large' for item in target['budget_checks']):
            lines.append('  Delivery: NOT SENT at the recorded budget checks; no generation attempt recorded.')
        for attempt in target['attempts']:
            label = attempt['outcome'].replace('_', ' ').replace('json', 'JSON')
            lines.append(f"  Attempt {attempt['number']} ({attempt['category']}): {label}")
            if attempt.get('parser_location'):
                lines.append('    JSON location: ' + str(attempt['parser_location']))
            if attempt.get('error_summary'):
                lines.append('    Error: ' + attempt['error_summary'])
            for delivery in attempt['deliveries']:
                status = delivery.get('http_status')
                label = delivery['outcome'].replace('_', ' ')
                lines.append(f"    Delivery {delivery['number']}: {label}; HTTP {status if status is not None else 'not captured'}")
            available = ', '.join(sorted(attempt['materials'])) or 'none captured'
            lines.append('    Saved materials: ' + available)
        for event in target.get('legacy_delivery_evidence', []):
            lines.append(f"  Historical delivery evidence: {event['event']} at {event['file']}:{event['line']} (generation attempt not correlated)")
        if target.get('blocker'):
            lines.append('  Blocker: ' + target['blocker'])
            lines.append('  Reason: ' + target['blocker_summary'])
        lines.append('  Result: ' + target['result'])
    lines += ['', *('Limitation: ' + value for value in report.limitations),
              'No migration state changes, source parsing, AI calls, builds, or connector reads were performed.']
    return lines
