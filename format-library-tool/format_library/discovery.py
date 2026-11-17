"""Run the isolated Java scanner; retain exact source and archive revisions."""
import tempfile
from pathlib import Path
from format_library.classpaths import inventory
from format_library.java_prerequisites import SCANNER_JAR, ensure_scanner
from format_library.files import file_hash, read_json, write_json
from format_library.processes import run_process

def scan(config, *, build=False):
    """Discover classes and dependencies without invoking the converter or original classes."""
    java, environment = ensure_scanner(config, force=build)
    timeout = config['java_scan_inactivity_timeout_seconds']
    log_path = Path(config['output_root']).resolve() / 'logs/discovery.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('Format library discovery: inheritance first, followed by required dependency closures.\n', encoding='utf-8')
    print('Checking inheritance and required dependencies; details: ' + str(log_path), flush=True)
    inputs = inventory(config)
    for root in config.get('foundation_source_roots', []):
        extra = inventory({**config, 'source_root': root})
        known = {item['file'] for item in inputs['sources']}
        inputs['sources'].extend(item for item in extra['sources'] if item['file'] not in known)
        project_ids = {item['id'] for item in inputs['projects']}
        inputs['projects'].extend(item for item in extra['projects'] if item['id'] not in project_ids)
    foundation_projects = {item['project'] for item in inputs['sources']
        if any(Path(item['file']).is_relative_to(Path(root)) for root in config.get('foundation_source_roots', []))}
    for project in inputs['projects']:
        project['visible_projects'] = list(dict.fromkeys([*project['visible_projects'], *sorted(foundation_projects)]))
    inputs.update(format_base_class=config['format_base_class'], decorator_base_classes=config['decorator_base_classes'],
                  framework_jars=config['framework_jars'],
                  foundation_classes=[name for members in config.get('foundation_groups', {}).values() for name in members])
    hashes = {item['file']: file_hash(item['file']) for item in inputs['sources']}
    libraries = {library for project in inputs['projects'] for library in project['libraries'] if Path(library).is_file()}
    hashes.update({path: file_hash(path) for path in libraries})
    with tempfile.TemporaryDirectory(prefix='format-library-scan-') as temporary:
        folder = Path(temporary)
        write_json(folder / 'input.json', inputs)
        run_process([java, '-jar', str(SCANNER_JAR), str(folder / 'input.json'), str(folder / 'output.json')],
                    environment, timeout, log_path=log_path)
        result = read_json(folder / 'output.json')
    for path, revision in hashes.items():
        if file_hash(path) != revision:
            raise ValueError('Input changed during discovery: ' + path)
    result.update(schema_version='format-library-discovery-v2', hashes=hashes, projects=inputs['projects'],
                  scanner_hash=file_hash(SCANNER_JAR), source_root=config['source_root'])
    result['foundation_groups'] = config.get('foundation_groups', {})
    result['foundation_source_roots'] = config.get('foundation_source_roots', [])
    result['dependency_policy'] = 'required-members-v1'
    result['detailed_log'] = str(log_path)
    from format_library.discovery_reporting import missing_dependencies, record_details
    result['unresolved_dependencies'] = missing_dependencies(result)
    record_details(result)
    write_json(Path(config['output_root']) / 'discovery.json', result)
    return result
