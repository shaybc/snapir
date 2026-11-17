"""Run the isolated Java scanner; retain exact source and archive revisions."""
import shutil
import tempfile
from pathlib import Path
from format_library.classpaths import inventory
from format_library.configuration import TOOL_ROOT, java_environment
from format_library.files import file_hash, read_json, write_json
from format_library.processes import run_process

SCANNER_JAR = TOOL_ROOT / 'scanner/target/format-library-scanner-1.0.0-jar-with-dependencies.jar'


def scan(config, *, build=False):
    """Discover classes and dependencies without invoking the converter or original classes."""
    java, environment = java_environment(config)
    timeout = config['java_scan_inactivity_timeout_seconds']
    if build or not SCANNER_JAR.is_file():
        maven = shutil.which('mvn', path=environment['PATH']) or shutil.which('mvn.cmd', path=environment['PATH'])
        if not maven:
            raise ValueError('Maven is required to build the scanner infrastructure')
        command = [maven, '-B', '-f', str(TOOL_ROOT / 'scanner/pom.xml')]
        if config.get('maven_settings_path'):
            command += ['-s', config['maven_settings_path']]
        if config.get('maven_local_repository'):
            command += ['-Dmaven.repo.local=' + config['maven_local_repository']]
        run_process([*command, 'package'], environment, timeout, cwd=TOOL_ROOT)
    inputs = inventory(config)
    inputs.update(format_base_class=config['format_base_class'], decorator_base_classes=config['decorator_base_classes'],
                  framework_jars=config['framework_jars'])
    hashes = {item['file']: file_hash(item['file']) for item in inputs['sources']}
    libraries = {library for project in inputs['projects'] for library in project['libraries'] if Path(library).is_file()}
    hashes.update({path: file_hash(path) for path in libraries})
    with tempfile.TemporaryDirectory(prefix='format-library-scan-') as temporary:
        folder = Path(temporary)
        write_json(folder / 'input.json', inputs)
        run_process([java, '-jar', str(SCANNER_JAR), str(folder / 'input.json'), str(folder / 'output.json')],
                    environment, timeout)
        result = read_json(folder / 'output.json')
    for path, revision in hashes.items():
        if file_hash(path) != revision:
            raise ValueError('Input changed during discovery: ' + path)
    result.update(schema_version='format-library-discovery-v1', hashes=hashes, projects=inputs['projects'],
                  scanner_hash=file_hash(SCANNER_JAR), source_root=config['source_root'])
    write_json(Path(config['output_root']) / 'discovery.json', result)
    return result
