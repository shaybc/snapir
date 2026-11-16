"""Start and resume isolated component runs through the canonical component converter."""
import json
from pathlib import Path

import constants
from runtime.workspace_paths import resolve_run_directory, run_database_path, run_profile_path, write_run_report
from runtime.component_conversion.standalone_preparation import prepare_components
from runtime.component_conversion.runner import convert_basic_components
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import update_run_status, get_run
from tools.workspace_intake_tools.run_factory import create_run_config, persist_run_config
from tools.conversion_tools.component_identity import checked_plan


def start_components(profile, run_id, configuration_path=None):
    """Create normal run state, skipping Composer mapping and all operation/channel stages."""
    directory = resolve_run_directory(profile.output_root, run_id)
    directory.mkdir(parents=True, exist_ok=False)
    for name in ('state', 'reports', 'logs', 'generated'):
        (directory / name).mkdir()
    settings = {name: getattr(constants, name) for name in dir(constants) if name.isupper()}
    settings.update(RUN_MODE='full_inventory', COMPOSER_ROOT=profile.source_root, VAULT_ROOT=str(directory / 'vault'),
        OUTPUT_ROOT=str(directory / 'generated'), DB_PATH=str(run_database_path(directory)), TARGET_CHANNELS=[],
        INCLUDE_OPERATIONS=[], EXCLUDE_OPERATIONS=[], TARGET_LANGUAGES=profile.target_languages,
        ENABLE_GIT=profile.enable_git, AGENT_MODEL=profile.model_name, LITELLM_BASE_URL=profile.model_base_url,
        MAX_AGENT_TASK_RETRIES=profile.max_agent_task_retries)
    config = create_run_config(settings, run_id)
    conn = get_connection(str(run_database_path(directory)))
    try:
        create_all_tables(conn)
        persist_run_config(conn, config, directory)
        run_profile_path(directory).write_text(profile.model_dump_json(indent=2), encoding='utf-8')
        from runtime.run_identity import write_run_identity
        write_run_identity(directory, profile, configuration_path)
        return _convert(conn, config, profile, directory)
    finally:
        conn.close()


def resume_components(profile, directory):
    """Recompute current source/entry/JAR evidence; canonical reuse checks decide what can be reused."""
    from models.common_models import RunConfig
    conn = get_connection(str(run_database_path(directory)))
    try:
        run = get_run(conn, directory.name)
        if run is None:
            raise ValueError('Standalone component run does not exist')
        config = RunConfig.model_validate(run['run_config_json'])
        from runtime.run_identity import record_resume_started
        record_resume_started(directory)
        return _convert(conn, config, profile, directory)
    finally:
        conn.close()


def _convert(conn, config, profile, directory):
    """Preserve existing generation, staging, builds, retries and component receipts."""
    from runtime.java_toolchain import java_scope
    from runtime.model_execution.diagnostics import run_model_diagnostics
    with java_scope(profile), run_model_diagnostics(directory):
        update_run_status(conn, config.run_id, 'in_progress', 'conversion_components_preparing')
        try:
            preparation, classpath = prepare_components(profile)
            (directory / 'state/standalone-preparation.json').write_text(json.dumps(preparation, indent=2), encoding='utf-8')
            write_run_report(directory, 'behavior_verification_boundaries.json', json.dumps(preparation['boundaries'], indent=2))
            convert_basic_components(conn, config, profile, directory, preparation, classpath, include_steps=True)
            result = component_results(conn, config, preparation)
            (directory / 'reports/standalone-components.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            update_run_status(conn, config.run_id, 'completed' if result['status'] == 'completed' else 'blocked',
                              'conversion_components_completed' if result['status'] == 'completed' else 'conversion_components_incomplete')
            print('Standalone components: ' + result['status'] + '. Results: ' + str(directory / 'reports/standalone-components.json'))
        except Exception:
            update_run_status(conn, config.run_id, 'blocked', 'conversion_components_incomplete')
            raise
    return directory


def component_results(conn, config, preparation):
    """Report build success separately from original/native directional comparison evidence."""
    from tools.state_store_tools import component_records as records
    plan = checked_plan(preparation['component_plan'])
    result = dict(status='completed', conversion_scope='components', operations_converted=0, components={})
    from runtime.workspace_paths import run_report_path
    generation = run_report_path(Path(config.output_root).parent, 'component-generation.json')
    groups = json.loads(generation.read_text(encoding='utf-8')).get('groups', {}) if generation.is_file() else {}
    for group in plan.groups:
        head = records.head(conn, config.run_id, group.group_id)
        saved = records.read_record(conn, config.run_id, group.group_id, 'result', head['result_revision']) if head and head.get('result_revision') else None
        for key in group.members:
            item = dict(conversion='blocked', comparisons={}, entry_points={identity:
                dict(analysis_status=preparation['boundaries']['boundaries'][identity]['analysis_status'],
                     method=preparation['boundaries']['boundaries'][identity].get('legacy_method') or preparation['boundaries']['boundaries'][identity].get('framework_method'),
                     issues=preparation['boundaries']['boundaries'][identity]['issues']) for identity in plan.components[key].unit_ids})
            if groups.get(group.group_id, {}).get('reason'):
                item['reason'] = groups[group.group_id]['reason']
            if saved and groups.get(group.group_id, {}).get('status') == 'component_validated':
                artifact = saved['results'][key]
                report = json.loads((Path(artifact['artifact_root']) / artifact['validation_report']).read_text(encoding='utf-8'))
                item.update(conversion='build_and_tests_passed', comparisons=report.get('standalone_comparisons', {}))
            required = set(plan.components[key].unit_ids)
            item['status'] = 'completed' if (item['conversion'] == 'build_and_tests_passed' and set(item['comparisons']) == required and
                all(value['status'] == 'matched' for value in item['comparisons'].values())) else 'blocked'
            if item['status'] != 'completed':
                result['status'] = 'blocked'
            result['components'][plan.components[key].label] = item
    return result
