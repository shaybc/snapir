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
    log_path.write_text('Format library discovery: inheritance first, then required members.\n', encoding='utf-8')
    print('Checking inheritance and required dependencies; details: ' + str(log_path), flush=True)
    inputs = inventory(config)
    inputs.update(format_base_class=config['format_base_class'], decorator_base_classes=config['decorator_base_classes'],
                  framework_jars=config['framework_jars'], source_encoding=config['source_encoding'])
    hashes = {}
    for item in inputs['sources']:
        try:
            hashes[item['file']] = file_hash(item['file'])
        except OSError as error:
            with log_path.open('a', encoding='utf-8') as log:
                log.write('WARNING: Unreadable Java source: ' + item['file'] + ' | ' + str(error) + '\n')
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
    result.update(schema_version='format-library-discovery-v1', hashes=hashes, projects=inputs['projects'],
                  scanner_hash=file_hash(SCANNER_JAR), source_root=config['source_root'],
                  source_encoding=config['source_encoding'])
    result['dependency_policy'] = 'required-members-v1'
    result['detailed_log'] = str(log_path)
    from format_library.discovery_reporting import missing_dependencies, record_details
    result['unresolved_dependencies'] = missing_dependencies(result)
    record_details(result)
    write_json(Path(config['output_root']) / 'discovery.json', result)
    return result
