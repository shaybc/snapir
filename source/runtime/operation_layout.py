"""Locate deliverable operation projects separately from converter working records."""
from pathlib import Path
from xml.etree import ElementTree


def operation_repository(project):
    """Return the repository owning a native project; retain legacy flat-project support."""
    project = Path(project)
    return project.parent if project.name == 'standalone' else project


def standalone_project(output_root, channel, operation):
    """New operations use a sibling-project repository; unmigrated checkpoints stay readable."""
    repository = Path(output_root) / channel / operation
    if (repository / 'pom.xml').is_file() and not (repository / 'standalone/pom.xml').is_file():
        return repository
    return repository / 'standalone'


def artifact_name(project):
    """Keep Maven coordinates stable when a project folder is called standalone or application."""
    project = Path(project)
    if (project / 'pom.xml').is_file():
        value = ElementTree.parse(project / 'pom.xml').getroot().findtext('{*}artifactId')
        if value:
            return value
    return project.parent.name if project.name == 'standalone' else project.name


def service_root(directory, item):
    """Keep new services beside standalone; support previously generated flat checkpoints."""
    native = Path(item['project'])
    if native.name == 'standalone':
        return native.parent / 'microservice'
    return Path(directory) / 'services' / item['channel'] / item['operation_id']


def application_project(project):
    """Resolve the executable Maven module without changing legacy single-module projects."""
    project = Path(project)
    return project / 'application' if (project / 'application/pom.xml').is_file() else project


def service_artifacts(project):
    """Keep converter control records outside operation repositories for the new reactor layout."""
    project = Path(project)
    if project.name == 'microservice' and (project / 'application/pom.xml').is_file():
        repository = project.parent
        return repository.parent.parent / '.converter-operations' / repository.parent.name / repository.name / 'microservice'
    return project


def service_record(project, name):
    """Locate an audit/control file without creating directories on reads."""
    return service_artifacts(project) / name
