"""Publish an evidence-based conversion checklist alongside the existing live status."""
import json
import uuid
from pathlib import Path


def conversion_steps(status,component_report=None):
    """Use verified progress only; a blocked earlier step never marks later work successful."""
    steps=[];running=status.get('process_running',False);phase=status.get('phase') or ''
    def add(mark,label):steps.append('['+mark+'] '+label)
    prepared=bool(status.get('total_units'))
    preparation_blocked=any(item.get('stage')=='preparation' for item in status.get('blockers',[])) or (
        not prepared and (status.get('status') in {'failed','blocked'} or status.get('error')))
    add('X' if preparation_blocked else 'V' if prepared else 'O' if running else ' ',
        'Resolve selected operation, source evidence, XML configuration and format references')
    component_report=component_report or {};groups=component_report.get('groups',{})
    total=component_report.get('total_groups')
    add('V' if groups or total else 'O' if prepared and running else ' ',
        'Build the dependency plan for basic formats, decorators, steps and configured structures')
    fatal=bool(component_report.get('fatal_error'))
    complete=bool(groups) and not fatal and (len(groups)==total if total is not None else not running) and all(
        item.get('status') in {'component_validated','configuration_bound','external_policy'} for item in groups.values())
    blocked=fatal or any(item.get('status') in {'incomplete','deferred'} for item in groups.values()) or (
        not running and status.get('error') and phase.startswith(('conversion_component','component_')))
    add('V' if complete else 'O' if running and (groups or total) else 'X' if blocked else ' ',
        ('Generate/reuse components and pass source, API, settings, dependency, compilation and JUnit checks (facts disabled for experiment)' if status.get('experimental_only') else
         'Generate/reuse components and pass source, API, settings, dependency, compilation, checklist and JUnit checks')
        +' ('+str(status.get('component_validated',0))+' validated)')
    chains=component_report.get('format_chain_status')
    add('V' if chains=='validated' else 'O' if chains=='running' and running else 'X' if chains in {'blocked','running'} else ' ',
        'Generate configured format/unformat chain classes and run behavior tests for order, values and decorator scope')
    units=status.get('total_units',0);accepted=status.get('accepted_units',0)
    unit_blocked=status.get('failed_units',0) or status.get('incomplete_units',0) or status.get('unverified_units')
    add('V' if not running and units and accepted==units and not status.get('unverified_units') else 'X' if unit_blocked else
        'O' if running and (accepted or phase.startswith('unit_')) else ' ',
        'Accept all complete units with current transitive component receipts ('+str(accepted)+'/'+str(units)+')')
    operations=status.get('total_operations',0);accepted_operations=status.get('accepted_operations',0)
    add('V' if not running and operations and accepted_operations==operations and not status.get('unverified_operations') else
        'X' if status.get('unverified_operations') else 'O' if running and (accepted_operations or phase.startswith(('operation_','conversion_operation'))) else ' ',
        'Assemble operations and pass operation review, build, JUnit and artifact checks ('+str(accepted_operations)+'/'+str(operations)+')')
    add('V' if (status.get('experimental_complete') if status.get('experimental_only') else status.get('acceptance_complete')) else ' ',
        'Complete experimental validation; normal acceptance and equivalence are not assessed' if status.get('experimental_only') else
        'Confirm conversion-ready acceptance; behavioral equivalence is not assessed')
    return steps


def publish_conversion_checklist(base,status,component_report=None):
    """Atomically refresh a human-readable file every time the live report is published."""
    base=Path(base)
    if component_report is None:
        from runtime.workspace_paths import run_report_path
        path=run_report_path(base/status['run_id'],'component-generation.json')
        component_report=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    lines=['# Conversion progress','',
        'Updated: '+status.get('recorded_at','unknown'),
        'Run: '+status['run_id']+'; status: '+str(status.get('status') or 'unknown')+'; phase: '+str(status.get('phase') or 'unknown'),
        'Legend: [V] passed; [X] failed/blocked; [ ] not reached; [O] working.','',
        *conversion_steps(status,component_report),'']
    if not status.get('process_running'):
        lines.extend(['Conversion is stopped. Stored historical component results do not establish acceptance under a newer chain policy.',''])
    target=base/'conversion-checklist.md';temporary=base/(target.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text('\n'.join(lines),encoding='utf-8');temporary.replace(target)
    return target
