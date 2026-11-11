"""Correlate saved reports and read-only SQLite evidence without executing analysis."""

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

from tools.run_diagnostics.prepared_units import read_prepared_units


def read_json(path):
    """Read a small evidence file; missing and malformed files stay distinguishable."""
    with path.open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def database(path):
    """Open existing SQLite state with filesystem and SQL writes prohibited."""
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    conn.execute('PRAGMA query_only=ON')
    return conn


def issue_summary(issues):
    """Classify analyzer errors without forwarding source excerpts or arbitrary values."""
    text = ' '.join(str(issue) for issue in issues)
    if 'no evidenced implementation binding' in text:
        return 'Missing implementation binding before Java analysis'
    if 'conflicts with explicit implClass' in text:
        return 'Explicit class conflicts with saved implementation binding'
    if 'Build the converter analysis tool' in text:
        return 'Converter analysis JAR is missing; it must be built or supplied offline'
    if 'Boundary analyzer JAR lacks project classpath support' in text:
        return 'Analyzer JAR is outdated; rebuild it for project-classpath support'
    if text.startswith(('Boundary JAR ', 'Boundary source has no verified owning project',
                        'Boundary implementation has no unique owning project')):
        return text[:240]
    if 'boundary analysis timed out after' in text:
        return 'Java analyzer exceeded its total runtime limit; see last progress below'
    if 'could not finish' in text:
        return 'Java analyzer could not finish (launch failure or timeout)'
    if 'Invalid Java source' in text:
        return 'Analyzer rejected supplied Java syntax'
    if 'Unsolved' in text or 'Unresolved' in text:
        symbol = re.search(r'''(?:Unsolved symbol\s*:\s*|name\s*[:=]\s*['"]?)([A-Za-z_$][\w.$]*)''', text)
        return 'Analyzer could not resolve a Java type' + (': ' + symbol[1] if symbol else '')
    if 'Entry method must resolve uniquely' in text:
        return 'No unique method matches the required entry signature'
    if 'no supplied Java source' in text:
        return 'Entry method has no supplied Java source'
    if 'no executable body' in text:
        return 'Entry method has no executable body'
    if 'Format entry' in text:
        return 'Format implementing body or reference could not be resolved'
    if 'boundary method is outside' in text.lower():
        return 'Analyzer returned a method outside the supplied source revision'
    if not issues:
        return 'No boundary issue saved; inspect component-level evidence'
    return 'Other analyzer error; see saved issue details below'


def class_evidence(run_db, analysis_db, class_name):
    """Count exact source/intake matches; do not infer entry-method success from facts."""
    indexed = intake = facts = 'unavailable'
    if class_name and analysis_db.is_file():
        try:
            with closing(database(analysis_db)) as conn:
                paths = conn.execute('SELECT file FROM java_sources WHERE fqcn=?', (class_name,)).fetchall()
                indexed = len(paths)
                facts = sum(conn.execute('SELECT count(*) FROM java_facts WHERE file=?', row).fetchone()[0] for row in paths)
        except sqlite3.Error:
            indexed = facts = 'unavailable'
    if class_name:
        try:
            with closing(database(run_db)) as conn:
                intake = conn.execute("SELECT count(*) FROM scoped_source_definitions WHERE run_id=? AND kind='java_class' AND logical_id=?",
                                      (run_db.parent.parent.name, class_name)).fetchone()[0]
        except sqlite3.Error:
            pass
    return indexed, intake, facts


def captured_binding(analysis_db, definition):
    """Read the exact mapped occurrence's implClass, never unrelated configuration."""
    if not definition or not analysis_db.is_file():
        return None
    try:
        with closing(database(analysis_db)) as conn:
            rows = conn.execute('''SELECT a.value FROM notes note
                JOIN files f ON f.relative_path=note.source_relative_path
                JOIN xml_nodes n ON n.file=f.path AND n.selector=note.source_selector
                JOIN xml_attributes a ON a.node=n.id AND a.name='implClass'
                WHERE note.definition=?''', (definition,)).fetchall()
            values = {row[0] for row in rows}
            return next(iter(values)) if len(values) == 1 else None
    except sqlite3.Error:
        return None


def diagnose(directory):
    """Produce a compact screenshot-friendly report with evidence-based conclusions."""
    directory = Path(directory).resolve()
    run_db = directory / 'state/migration.db'
    lines = ['SAVED RUN DIAGNOSTIC (read-only)', 'Run: ' + directory.name]
    saved_vault = None
    try:
        with closing(database(run_db)) as conn:
            row = conn.execute('SELECT status,current_phase FROM runs WHERE run_id=?', (directory.name,)).fetchone()
            if row is None:
                return lines + ['Run record not found in this database.']
            lines.append('State: ' + str(row[0]) + ' / ' + str(row[1]))
            columns = {column[1] for column in conn.execute('PRAGMA table_info(runs)')}
            if 'run_config_json' in columns:
                config = conn.execute('SELECT run_config_json FROM runs WHERE run_id=?', (directory.name,)).fetchone()[0]
                try:
                    saved_vault = json.loads(config).get('vault_root')
                except (ValueError, TypeError, AttributeError):
                    pass
    except sqlite3.Error:
        return lines + ['Run database missing, unreadable, locked, or incompatible.']
    from tools.run_diagnostics.conversion_ai import is_conversion_phase, build_report, format_report
    if is_conversion_phase(row[1]):
        try:
            return format_report(build_report(directory))
        except (OSError, ValueError, sqlite3.Error):
            return lines + ['Conversion AI evidence is unavailable or incompatible; no earlier-stage investigation performed.']
    if not str(row[1] or '').startswith(('conversion_', 'closure', 'dependency_closure')):
        from runtime.workflow_stages import workflow_stage_label
        known = str(row[1] or '').startswith(('planning', 'gate_', 'intake', 'scoped_', 'component_', 'assembly_', 'operation_', 'service_', 'finalization'))
        return lines + ['Stage: ' + (workflow_stage_label(row[1]) if known else 'Unknown checkpoint'),
                        'Conversion AI diagnosis is not applicable at this checkpoint; no previous-stage investigation performed.']
    stage = directory / 'reports/3_dependency_closure_and_component_conversion'
    try:
        boundaries = read_json(stage / 'behavior_verification_boundaries.json').get('boundaries', {})
    except (OSError, ValueError):
        return lines + ['Boundary report missing or unreadable; no boundary diagnosis possible.']
    failed = {key: value for key, value in boundaries.items() if value.get('analysis_status') != 'identified' or value.get('issues')}
    lines.append(f'Boundaries: {len(boundaries) - len(failed)}/{len(boundaries)} identified')
    try:
        units = read_prepared_units(stage / 'scoped_workflow_preparation.json', failed)
    except (OSError, ValueError, RecursionError):
        units = {}
        lines.append('Preparation report missing, incomplete, or incompatible.')
    if saved_vault:
        analysis = Path(saved_vault) / 'analysis/analysis.sqlite'
    else:
        try:
            profile = read_json(directory / 'state/profile.json')
            analysis = Path(profile.get('existing_composer_map') or directory / 'vault') / 'analysis/analysis.sqlite'
        except (OSError, ValueError, TypeError, AttributeError):
            analysis = directory / 'vault/analysis/analysis.sqlite'
    group_failures = []
    try:
        groups = read_json(stage / 'component-generation.json').get('groups', {})
        group_failures = [item for item in groups.values() if item.get('status') == 'incomplete']
        lines.append(f'Component groups incomplete: {len(group_failures)}/{len(groups)}')
    except (OSError, ValueError):
        lines.append('Component report missing or unreadable.')
    log_matches = 0
    for log in (directory / 'logs').rglob('*.log'):
        try:
            with log.open(encoding='utf-8', errors='replace') as stream:
                log_matches += sum('no parser-backed entry points' in line or 'Complete format requires identified original boundary' in line for line in stream)
        except OSError:
            continue
    lines.append(f'Related warnings in saved logs: {log_matches} (may include earlier attempts)')
    for number, (identity, boundary) in enumerate(list(failed.items())[:6], 1):
        unit = units.get(identity, {})
        configuration = unit.get('effective_configuration') or {}
        attrs = configuration.get('attributes') or {}
        resolved = configuration.get('resolved_implementation')
        implementation = boundary.get('implementation_class')
        mapped = captured_binding(analysis, unit.get('source_definition_id'))
        name = unit.get('logical_id') or attrs.get('id') or boundary.get('kind', 'unknown unit')
        lines += ['', f'{number}. {name} ({boundary.get("kind", "unknown")})',
                  '   Boundary class: ' + str(implementation or 'NULL'),
                  '   Prepared: explicit=' + str(attrs.get('implClass') or 'NULL') + '; resolved=' + str(resolved or 'NULL')]
        indexed, intake, facts = class_evidence(run_db, analysis, implementation or resolved or attrs.get('implClass'))
        lines.append(f'   Evidence: indexed={indexed}; intake={intake}; indexing records={facts}')
        if mapped and not (resolved or attrs.get('implClass')):
            conclusion = 'Map captured implClass but prepared binding is missing: ' + mapped
        elif resolved and not implementation:
            conclusion = 'Saved binding exists but boundary did not retain it; check deployed version/report freshness'
        else:
            conclusion = issue_summary(boundary.get('issues', []))
        lines.append('   Finding: ' + conclusion)
        for issue in boundary.get('issues', []):
            lines.append('   Saved issue:')
            lines.extend('      ' + line for line in str(issue).splitlines())
    if len(failed) > 6:
        lines.append(f'Additional failed boundaries: {len(failed) - 6}')
    if not failed:
        lines.append('No failed boundary recorded; component errors: ' + '; '.join(sorted({issue_summary([item.get('reason', '')]) for item in group_failures})))
    lines += ['', 'Indexing records are not behavioral checks. Missing evidence is not proof of a missing disk file.',
              'No migration changes, source parsing, AI calls, or connector reads were performed.']
    return lines
