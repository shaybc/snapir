"""Compile current mapper/core sources for legacy Java integration harnesses."""

from pathlib import Path


def mapper_sources(root):
    return [*sorted((root/'java-analysis-core/src/main/java').rglob('*.java')),
            *sorted((root/'composer-mapper/src/main/java').rglob('*.java'))]


def mapper_dependencies(root):
    jackson = Path.home()/'.m2/repository/com/fasterxml/jackson/core/jackson-core/2.18.2/jackson-core-2.18.2.jar'
    if jackson.is_file():
        return str(jackson)
    jar = root/'composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar'
    if jar.is_file():
        return str(jar)
    raise RuntimeError('Build mapper dependencies first: mvn -f source/pom.xml package')
