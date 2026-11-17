"""Summarize discovered components and missing dependencies without per-class console noise."""
from pathlib import Path


def missing_dependencies(discovery):
    """Deduplicate unresolved symbols across ancestry warnings and relevant dependency closures."""
    missing = {symbol for item in discovery['classes'].values()
               for symbol in item.get('unresolved_dependencies', [])}
    for project in discovery.get('projects', []):
        missing.update(project.get('issues', []))
    return sorted(missing)


def record_details(discovery):
    """Append per-class diagnostics and their owners to the persistent scanner log."""
    path = Path(discovery['detailed_log'])
    with path.open('a', encoding='utf-8') as log:
        for issue in discovery.get('issues', []):
            log.write('DISCOVERY ISSUE: ' + issue + '\n')
        for project in discovery.get('projects', []):
            for issue in project.get('issues', []):
                log.write('PROJECT ' + project['id'] + ': ' + issue + '\n')
        for name, item in sorted(discovery['classes'].items()):
            if item.get('ancestry_status') == 'unresolved':
                log.write('WARNING: ancestry could not be classified: ' + name + '\n')
            if item.get('dependency_status') == 'analyzed':
                log.write('REQUIRED CODE: ' + name + ' | source: ' + str(item.get('file')) + '\n')
            for issue in item.get('issues', []):
                log.write(name + ': ' + issue + '\n')


def print_summary(plan):
    """Show identified formats/decorators, consolidated missing dependencies and the log path."""
    print('\nIdentified formats and decorators:')
    identified = [(name, item['kind']) for name, item in sorted(plan['classes'].items())
                  if item['kind'] in {'format', 'decorator'} and not item['abstract'] and not item['framework']]
    for name, kind in identified:
        print('  ' + kind + ': ' + name)
    if not identified:
        print('  none')
    print('\nMissing or unresolved classes and dependencies:')
    missing = set(plan.get('unresolved_dependencies', []))
    for name, item in plan['classes'].items():
        if 'file' in item and item['file'] is None:
            missing.add('Source required: ' + name)
    for symbol in sorted(missing):
        print('  ' + symbol)
    if not missing:
        print('  none')
    print('\nDetailed discovery log: ' + plan['detailed_log'])


def record_plan(plan):
    """Preserve foundation proposals, dependency order and blockers in the detailed log."""
    with Path(plan['detailed_log']).open('a', encoding='utf-8') as log:
        for item in plan.get('foundation_candidates', []):
            log.write('FOUNDATION BASE: ' + item['original_class'] + ' | source: ' +
                ('available' if item['source_available'] else 'required') + ' | selected: ' +
                (item['selected_group'] or 'not selected') + '\n')
        for item in plan['groups']:
            log.write(str(item['order']) + '. ' + item['stage'].upper() + ': ' + item['name'] +
                ' | ' + ', '.join(item['members']) + ' [' + item['id'] + ']\n')
            log.write('  Prerequisites: ' + (', '.join(item['dependencies']) or 'none') + '\n')
            for blocker in item['blockers']:
                log.write('  BLOCKED: ' + blocker + '\n')
