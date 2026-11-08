"""Collect user-owned inputs for full conversion using the existing wizard lifecycle."""
import json
from types import SimpleNamespace

from cli.default_configuration_settings import completed_settings
from cli.configuration_flow import _default_path, collect_section as existing_section
from models.service_environment import ServiceEnvironment
from models.service_address import ServiceAddress
from runtime.model_execution.readiness import model_readiness_issues


SECTION_NAMES = ('Default config: name and source', 'Composer analysis', 'Run and shared storage',
    'Channels and root operations', 'Java and Helm', 'Dependency environment', 'Approval policy',
    'Live AI connection', 'Service environment')


def _json(inputs, title, default, expected):
    """Validate structured user settings before committing a section."""
    value = json.loads(inputs.text(title, json.dumps(default)))
    if not isinstance(value, expected):
        raise ValueError(title + ': invalid JSON value type')
    return value


def collect_section(draft, inputs, configs, api):
    """Reuse canonical discovery and input collectors, keeping workflow policy fixed."""
    section, values = draft.section, draft.values()
    if section == 0:
        result = existing_section(draft, inputs, configs, api)
        result['source_workspace_id'] = inputs.text('Stable application/workspace ID', result['_name'])
        if not result['source_workspace_id'].strip():
            raise ValueError('source_workspace_id is required')
        return result
    if section == 1:
        choice = inputs.menu('Composer analysis', [('create', 'Create a new map'), ('existing', 'Use an existing indexed/scoped map')])
        if choice == 'create':
            return dict(mapper_jar=api.collect_path(configs, 'mapper_jar',
                _default_path(configs, api.constants.COMPOSER_MAPPER_JAR), prompt=inputs.text))
        path = inputs.text('Existing indexed/scoped map folder')
        from tools.workspace_intake_tools.vault_validator import check_existing_composer_map
        from tools.composer_mapper_tools.indexed_analysis import is_indexed_map, bounded_json
        root = (configs / path).resolve()
        check_existing_composer_map(str(root))
        if not is_indexed_map(root):
            raise ValueError('Select an indexed/scoped map or create a new map')
        metadata = bounded_json((root / 'vault-manifest.json').read_text(encoding='utf-8-sig'))
        if metadata['workspace_id'] != values['source_workspace_id']:
            raise ValueError('source_workspace_id differs from the existing map; correct the application ID or create a new map')
        return dict(existing_composer_map=path)
    if section == 2:
        result = existing_section(draft, inputs, configs, api)
        result['shared_store_root'] = inputs.text('Persistent shared store folder', '../shared')
        if not result['shared_store_root'].strip():
            raise ValueError('shared_store_root is required')
        return result
    if section == 3:
        # Reuse discovery and selection while removing the redundant Java-only question.
        class JavaInputs:
            def multiple(self, title, options, **kwargs):
                return ['java'] if title == 'Select target languages' else inputs.multiple(title, options, **kwargs)
            def __getattr__(self, name):
                return getattr(inputs, name)
        return existing_section(draft, JavaInputs(), configs, api)
    if section == 4:
        result = existing_section(draft, inputs, configs, api)
        result['microservice'] = dict(enabled=True, require_helm_validation=True,
            helm_executable=inputs.text('Helm executable', 'helm'))
        return result
    if section == 5:
        result = api.collect_external_dependencies(inputs.text)
        result['classpath_jars'] = _json(inputs, 'Additional classpath JARs (JSON list)', [], list)
        result['eclipse_classpath_variables'] = _json(inputs, 'Eclipse classpath variables (JSON object)', {}, dict)
        result['maven_settings_path'] = inputs.text('Maven settings file (empty uses Maven defaults)', '') or None
        result['maven_local_repository'] = inputs.text('Maven local repository (empty uses Maven defaults)', '') or None
        return result
    if section == 6:
        return api.collect_gate_configuration(inputs.text)
    if section == 7:
        result = dict(model_provider='litellm',
            model_name=inputs.text('LiteLLM model name', api.constants.AGENT_MODEL),
            model_base_url=inputs.text('Model API endpoint', 'https://generativelanguage.googleapis.com'),
            model_api_key_environment=inputs.text('API key environment variable name (not the key)', 'GEMINI_API_KEY'))
        issues = model_readiness_issues(SimpleNamespace(**result))
        if issues:
            raise ValueError(' '.join(issues))
        return result
    environment = inputs.text('Service environment name', 'test')
    if not environment.strip():
        raise ValueError('Service environment name is required')
    namespace = inputs.text('OpenShift namespace (empty if not configured yet)', '')
    cluster = inputs.text('Cluster domain', 'cluster.local')
    port = int(inputs.text('Internal Service port', '8080'))
    if not 1024 <= port <= 65535:
        raise ValueError('Service port must be between 1024 and 65535 for the generated application')
    external = inputs.text('External URL pattern (empty if not configured yet)', '')
    settings = ServiceEnvironment(namespace=namespace, cluster_domain=cluster, service_port=port, external_url_pattern=external)
    if external:
        try:
            ServiceAddress(external_base_url=external.format(service_name='sample', namespace=namespace,
                channel='CHANNEL', operation='Operation'))
        except (KeyError, ValueError) as error:
            raise ValueError('service_environments external URL pattern needs a valid HTTP URL and supported placeholders') from error
    overrides = _json(inputs, 'Exact operation address overrides (JSON object)', {}, dict)
    for identity, address in list(overrides.items()):
        if '/' not in identity or not all(identity.split('/', 1)) or not isinstance(address, dict):
            raise ValueError('Operation overrides must use channel/operation keys and address objects')
        supplied = dict(address)
        if 'service_port' in supplied:
            if 'port' in supplied and supplied['port'] != supplied['service_port']:
                raise ValueError('Operation overrides contain conflicting service ports')
            supplied['port'] = supplied.pop('service_port')
        # Partial naming/port overrides inherit URLs from the environment convention.
        validated = ServiceAddress.model_validate({'base_url_property':'service.address', **supplied}).model_dump(mode='json', exclude_none=True)
        if 'base_url_property' not in supplied:
            validated.pop('base_url_property')
        if 'port' in validated:
            validated['service_port'] = validated.pop('port')
        overrides[identity] = validated
    return dict(deployment_environment=environment, service_environments={environment: settings.model_dump(mode='json')},
                deployment_values=overrides, test_deployment=dict(service_base_url='', service_external_port=None, service_route_pattern='ms_${ms_name}'))


def error_section(error):
    """Return validation failures to their user-input section."""
    text = str(error)
    for index, fields in ((1, ('mapper_', 'existing_composer_map')), (2, ('shared_store_root', 'output_root')),
            (3, ('channels', 'include_operations')), (4, ('java_', 'helm')), (5, ('maven_', 'classpath', 'external_dependencies')),
            (6, ('gate_', 'plan_approval_policy')), (7, ('model_', 'credential', 'API key')),
            (8, ('service_environments', 'deployment_', 'namespace', 'Service port', 'Service environment', 'Operation overrides'))):
        if any(field in text for field in fields):
            return index
    return 0


def validate_settings(values, configs):
    """Recheck map identity after review edits, before writing any configuration."""
    if values.get('existing_composer_map'):
        from tools.composer_mapper_tools.indexed_analysis import bounded_json, is_indexed_map
        root = (configs / values['existing_composer_map']).resolve()
        if not is_indexed_map(root):
            raise ValueError('existing_composer_map must be indexed/scoped')
        metadata = bounded_json((root / 'vault-manifest.json').read_text(encoding='utf-8-sig'))
        if metadata['workspace_id'] != values['source_workspace_id']:
            raise ValueError('existing_composer_map workspace ID differs from source_workspace_id')
