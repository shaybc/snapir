"""Build missing converter Java prerequisites before opening the migration CLI."""

from pathlib import Path
import subprocess
from xml.etree import ElementTree
from zipfile import ZipFile, BadZipFile

import constants
from runtime.java_toolchain import java_environment
from tools.behavior_verification.java_tool import default_tool_path
from tools.maven_dependency_tools.command import maven_executable


ANALYZER_CAPABILITY = 'il/co/dcd/verification/ProjectTypeSolvers.class'
ANALYZER_PROGRESS_CAPABILITY = 'il/co/dcd/verification/NodeProcessingProgress.class'


def analyzer_ready(path):
    """Reject old or incomplete analyzer artifacts lacking analysis progress reporting."""
    try:
        with ZipFile(path) as archive:
            return all(name in archive.namelist() for name in
                       (ANALYZER_CAPABILITY, ANALYZER_PROGRESS_CAPABILITY))
    except (OSError, BadZipFile):
        return False


def ensure_java_tools(project):
    """Reuse existing JARs and build missing tools with the POM-required JDK.

    Maven uses the machine's existing settings and dependency cache. Build errors
    stop startup; this function never starts a migration or changes saved runs.
    """
    project = Path(project).resolve()
    tools = [
        ('Composer mapper', project / constants.COMPOSER_MAPPER_JAR,
         project / 'source/composer-mapper/pom.xml',
         ['-f', str(project / 'source/pom.xml'), '-pl', 'composer-mapper', '-am']),
        ('Boundary analyzer', project / default_tool_path().relative_to(Path(__file__).resolve().parents[2]),
         project / 'source/behavior-verification-java/pom.xml',
         ['-f', str(project / 'source/behavior-verification-java/pom.xml')]),
    ]
    missing = [tool for tool in tools if not tool[1].is_file() or
               tool[0] == 'Boundary analyzer' and not analyzer_ready(tool[1])]
    if not missing:
        print('Java prerequisites ready: Composer mapper and boundary analyzer.', flush=True)
        return
    versions = [int(node.text.strip()) for _, _, pom, _ in missing
                for node in ElementTree.parse(pom).iter()
                if node.tag.rsplit('}', 1)[-1] in {'release', 'maven.compiler.source'}
                and node.text and node.text.strip().isdigit()]
    if not versions:
        raise ValueError('Java tool POMs do not declare a supported compiler version')
    environment = java_environment(max(versions))
    maven = maven_executable()
    for name, artifact, _, arguments in missing:
        print('Building missing or outdated Java prerequisite: ' + name, flush=True)
        result = subprocess.run([maven, '-B', *arguments, 'package'], cwd=project,
                                env=environment, check=False)
        if result.returncode:
            raise ValueError(name + ' build failed. Check the Maven output above. On an offline machine, '
                             'the required dependencies/plugins must already be cached or supplied locally.')
        if not artifact.is_file():
            raise ValueError(name + ' build finished without producing the expected JAR: ' + str(artifact))
        if name == 'Boundary analyzer' and not analyzer_ready(artifact):
            raise ValueError('Built boundary analyzer lacks analysis progress reporting; check the tool sources and Maven output')
    print('Java prerequisites ready: Composer mapper and boundary analyzer.', flush=True)


if __name__ == '__main__':
    try:
        ensure_java_tools(Path(__file__).resolve().parents[2])
    except (OSError, ValueError, ElementTree.ParseError) as error:
        print('Java prerequisite check failed: ' + str(error), flush=True)
        print('Install/configure Maven and the required JDK, or supply the built tool JARs before retrying.', flush=True)
        raise SystemExit(1)
