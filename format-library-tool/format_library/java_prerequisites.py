"""Build only the tool's scanner when source/build evidence or its artifact has changed."""
import shutil
from zipfile import ZipFile, BadZipFile
from format_library.configuration import TOOL_ROOT, java_environment
from format_library.files import digest, file_hash, read_json, write_json
from format_library.processes import run_process

SCANNER_ROOT = TOOL_ROOT / 'scanner'
SCANNER_JAR = SCANNER_ROOT / 'target/format-library-scanner-1.0.0-jar-with-dependencies.jar'
BUILD_STATE = SCANNER_ROOT / 'target/build-state.json'
MAIN_CLASS = 'com/snapir/format/tool/ComponentScanner.class'


def _inputs():
    """Fingerprint build files, not timestamps, so a fresh checkout does not rebuild needlessly."""
    files = [SCANNER_ROOT / 'pom.xml', *sorted((SCANNER_ROOT / 'src').rglob('*'))]
    return digest({path.relative_to(SCANNER_ROOT).as_posix(): file_hash(path)
                   for path in files if path.is_file()})


def _ready(revision):
    try:
        state = read_json(BUILD_STATE)
        with ZipFile(SCANNER_JAR) as archive:
            return MAIN_CLASS in archive.namelist() and state.get('inputs') == revision and state.get('jar') == file_hash(SCANNER_JAR)
    except (OSError, ValueError, BadZipFile):
        return False


def ensure_scanner(config, *, force=False):
    """Validate JDK and scanner; Maven resolves/builds only this isolated tool project."""
    java, environment = java_environment(config)
    revision = _inputs()
    if not force and _ready(revision):
        print('Java scanner ready; no build needed.', flush=True)
        return java, environment
    maven = shutil.which('mvn', path=environment['PATH']) or shutil.which('mvn.cmd', path=environment['PATH'])
    if not maven:
        raise ValueError('Maven is required to build the scanner infrastructure')
    command = [maven, '-B', '-f', str(SCANNER_ROOT / 'pom.xml')]
    if config.get('maven_settings_path'):
        command += ['-s', config['maven_settings_path']]
    if config.get('maven_local_repository'):
        command += ['-Dmaven.repo.local=' + config['maven_local_repository']]
    print('Building tool Java scanner and its dependencies...', flush=True)
    run_process([*command, 'package'], environment, config['java_scan_inactivity_timeout_seconds'], cwd=TOOL_ROOT)
    if revision != _inputs():
        raise ValueError('Scanner inputs changed during build; retry after the files stop changing')
    try:
        with ZipFile(SCANNER_JAR) as archive:
            if MAIN_CLASS not in archive.namelist():
                raise ValueError('Scanner JAR does not contain its entry class')
        write_json(BUILD_STATE, dict(inputs=revision, jar=file_hash(SCANNER_JAR)))
    except (OSError, BadZipFile) as error:
        raise ValueError('Java scanner build did not produce a valid JAR') from error
    print('Java scanner ready.', flush=True)
    return java, environment
