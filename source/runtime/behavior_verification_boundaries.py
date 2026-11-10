"""Publish converter-side boundary discovery without replacing any acceptance gate."""

import json
import logging

from runtime.workspace_paths import write_run_report
from tools.behavior_verification.boundaries import build_boundary_report
from tools.composer_mapper_tools.channel_note_parser import parse_channel_note
from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess


def write_boundary_report(conn, config, preparation, directory, *, collect_checklists=True, profile=None):
    """Keep incomplete analysis visible while the new verification pipeline is being built."""
    mappings = {}
    access = ScopedVaultAccess(conn, config.run_id)
    for key in preparation.get('operations', {}):
        channel, operation = key.split('/', 1)
        context = access.operation(channel, operation)
        mappings[key] = {name: fqcn for name, fqcn, _ in parse_channel_note(
            access.channel_evidence(context)['markdown'], context.channel)}
    classpath = None
    if profile is not None:
        from tools.source_discovery_tools.classpath_scope import discover_conversion_classpath
        classpath = discover_conversion_classpath(config.source_root, profile.classpath_jars,
            profile.eclipse_classpath_variables, profile=profile)
    report = build_boundary_report(preparation, mappings=mappings, collect_checklists=collect_checklists,
                                  classpath_index=classpath)
    write_run_report(directory, 'behavior_verification_boundaries.json', json.dumps(report, indent=2))
    logging.getLogger(__name__).info('Boundary discovery: %s/%s entries identified; behavioral verification has not run',
        report['counts']['identified'], report['counts']['total'])
    logging.getLogger(__name__).info('Reachability: %s analyzed, %s incomplete, %s uncertain and %s unbounded edges; no runtime tracing',
        report['reachability_counts']['analyzed'], report['reachability_counts']['incomplete'],
        report['reachability_counts']['uncertain_edges'], report['reachability_counts']['unbounded_edges'])
    logging.getLogger(__name__).info('Parser checklist: %s extracted, %s incomplete, %s items; no acceptance gate',
        report['checklist_counts']['extracted'], report['checklist_counts']['incomplete'], report['checklist_counts']['items'])
    return report
