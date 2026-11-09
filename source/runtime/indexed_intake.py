"""Run map-first intake using selected persisted facts instead of another workspace parse."""

import logging
from pathlib import Path
import tempfile

import constants
from runtime.workspace_paths import run_mapper_log_path, run_report_path
from runtime.inventory_reports import write_json_report
from runtime.intake_progress import component_inventory_progress
from runtime.java_toolchain import java_environment, run_java
from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis
from tools.composer_mapper_tools.mapped_scope import mapped_scope
from tools.component_inventory_tools.mapped_inventory import MappedInventory, ClassProjects
from tools.state_store_tools.inventory_records import InventoryRecords
from tools.state_store_tools.runs import update_run_status


def run_indexed_intake(profile, config, conn, directory, settings, vault):
    """Publish a pinned selected snapshot only after the reusable map is complete and verified."""
    with component_inventory_progress(0,log_directory=directory/'logs') as progress:
        return _run_indexed_intake(profile,config,conn,directory,settings,vault,progress)


def _run_indexed_intake(profile, config, conn, directory, settings, vault, progress):
    """Keep validation, mapping and selected loading inside one logged progress lifetime."""
    logger = logging.getLogger(__name__)
    progress.stage('Preparing reusable Composer analysis')
    if not profile.existing_composer_map:
        from tools.workspace_intake_tools.mapper_generation import mapper_command
        settings = dict(settings, COMPOSER_MAPPER_ANALYSIS_FORMAT='indexed-v1',
                        COMPOSER_MAPPER_ANALYSIS_REUSE=profile.mapper_analysis_reuse,
                        COMPOSER_MAPPER_ANALYSIS_SETTINGS=profile.mapper_analysis.model_dump())
        command = mapper_command(settings, markdown=True, filter_channel=False)
        update_run_status(conn,config.run_id,'in_progress','mapper')
        logger.info('Building reusable indexed Composer map before Java inventory; log: %s',run_mapper_log_path(directory))
        from runtime.indexed_mapper_progress import IndexedMapperProgress
        result = run_java(command,text=True,capture_output=False,check=False,
            inactivity_timeout_seconds=profile.java_scan_inactivity_timeout_seconds,
            activity_path=Path(vault)/'analysis/analysis.sqlite-wal',output_log=run_mapper_log_path(directory),
            env=java_environment(constants.MAPPER_JAVA_VERSION),on_output=IndexedMapperProgress(progress))
        if result.returncode:
            raise RuntimeError('Indexed Composer mapper failed; see logs/mapper.log')
        progress.advance(detail='Global indexed map published')
    from tools.state_store_tools.map_snapshot import validation_receipt
    progress.stage('Validating reusable Composer map')
    with IndexedAnalysis(vault,progress=logger.info,receipt=validation_receipt(profile.output_root,vault),
                         trusted_publication=not bool(profile.existing_composer_map)) as analysis:
        if analysis['workspace_id'] != profile.source_workspace_id:
            raise ValueError('Indexed map workspace ID does not match source_workspace_id')
        progress.stage('Verifying source fingerprints without parsing')
        analysis.verify_sources(profile.source_root,logger.info)
        progress.stage('Selecting operations and stored Java dependency closure')
        mapped = MappedInventory(analysis,profile.source_root,config)
        if mapped.index.issues:
            raise ValueError('Mapped Java source discovery reported issues: ' + '; '.join(mapped.index.issues[:10]))
        with mapped_scope(mapped),tempfile.TemporaryDirectory(prefix='snapir-mapped-inventory-') as scratch:
            storage = InventoryRecords(Path(scratch)/'records.sqlite',selection=config)
            storage.mapped_analysis = mapped
            try:
                from tools.component_inventory_tools import build_component_inventory
                from tools.state_store_tools.component_inventory import persist_component_inventory, iter_implementation_usage, iter_configured_component_usage
                from tools.component_inventory_tools.conversion_scope import persist_conversion_scope
                from runtime.selected_inventory_reports import selected_inventory
                count=analysis.conn.execute('SELECT count(*) FROM selected_java').fetchone()[0]
                logger.info('Using persisted map facts: %s selected Java implementations; zero workspace syntax scans.',count)
                progress.stage('Loading selected Java inventory',count)
                storage.progress=progress
                write_json_report(run_report_path(directory,'java_source_index.json'),dict(
                    workspace_root=str(mapped.workspace),class_projects=ClassProjects(mapped,selected_only=True),
                    classes=mapped.index.classes,source_roots=mapped.index.source_roots,
                    project_references=mapped.index.project_references,issues=mapped.index.issues,
                    analysis_scope='Selected Java closure; global declarations remain in the indexed Composer map'))
                from tools.source_discovery_tools.classpath import discover_java_classpath
                progress.stage('Resolving selected project classpath')
                classpath=discover_java_classpath(profile.source_root,profile.classpath_jars,profile.eclipse_classpath_variables,
                    visible_source_roots=[str(mapped.workspace/Path(row[0]).relative_to(analysis.source_root))
                        for row in analysis.conn.execute('SELECT DISTINCT s.root FROM java_sources s JOIN selected_java j ON j.file=s.file')],
                    progress=progress.current)
                write_json_report(run_report_path(directory,'java_classpath_index.json'),classpath)
                inventory=build_component_inventory(profile.source_root,profile.source_workspace_id,mapped.index,storage)
                persist_component_inventory(conn,config.run_id,inventory,analysis['analysis_hash'])
                scope=persist_conversion_scope(conn,config)
                write_json_report(run_report_path(directory,'conversion_scope.json'),scope)
                selected,graph=selected_inventory(conn,config.run_id,inventory)
                write_json_report(run_report_path(directory,'component_inventory.json'),selected)
                write_json_report(run_report_path(directory,'java_source_dependencies.json'),graph())
                write_json_report(run_report_path(directory,'component_usage.json'),iter_implementation_usage(conn,config.run_id,selected_only=True))
                write_json_report(run_report_path(directory,'configured_component_usage.json'),iter_configured_component_usage(conn,config.run_id,selected_only=True))
                from tools.composer_mapper_tools.indexed_vault_importer import import_indexed_vault
                from tools.composer_mapper_tools.vault_importer import VaultImportSummary
                progress.stage('Importing selected mapper evidence')
                summary=import_indexed_vault(conn,analysis,mapped,config,VaultImportSummary(),progress=logger.info)
                from agents.legacy_composer_analysis.agent import record_import_summary
                record_import_summary(conn,config,summary)
                progress.advance(detail='Pinned selected indexed intake committed')
            finally:
                storage.close()
    update_run_status(conn,config.run_id,'paused','scoped_inventory_ready')
    logger.info('Indexed selected inventory ready; existing qualified conversion gates remain active.')
    return directory
