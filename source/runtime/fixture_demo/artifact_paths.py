"""Keep converter demo records outside deliverable operation projects."""
from pathlib import Path
from runtime.fixture_jdbc_tools.releases import file_hash


ARTIFACT_NAMES = (
    '.demo-scenario-generation', '.demo-scenario-verification',
    '.demo-owned-files.json', 'demo-preparation.json', 'operation-demo-scenarios.json',
)


def demo_workspace(project):
    """Return generated/.converter-demo/channel/operation without creating files."""
    project = Path(project).resolve()
    generated = project.parent.parent
    directory = (generated / '.converter-demo' / project.parent.name / project.name).resolve()
    if not directory.is_relative_to(generated) or directory.is_relative_to(project):
        raise ValueError('Converter demo workspace must stay outside the operation project')
    return directory


def demo_artifact(project, name):
    """Resolve one known converter record; runtime fixture paths remain project-relative."""
    if name not in ARTIFACT_NAMES:
        raise ValueError('Unknown converter demo artifact: ' + name)
    directory = demo_workspace(project)
    path = (directory / name).resolve()
    if not path.is_relative_to(directory):
        raise ValueError('Converter demo artifact escaped its workspace')
    return path


def migrate_demo_artifacts(project):
    """Move legacy records intact, rejecting conflicting copies and active preparation locks.

    All paths and conflicts are checked before moving anything. Identical partial
    copies can be completed after an interruption; history and attempt counts are
    never rewritten. Only empty legacy directories are removed after moving files.
    """
    project = Path(project).resolve()
    workspace = demo_workspace(project)
    files, directories = [], []
    for name in ARTIFACT_NAMES:
        source = project / name
        if source.is_symlink():
            raise ValueError('Legacy demo artifact cannot be a symbolic link')
        if not source.exists():
            continue
        destination = demo_artifact(project, name)
        for path in [source, *source.rglob('*')] if source.is_dir() else [source]:
            if path.is_symlink() or not path.resolve().is_relative_to(project):
                raise ValueError('Legacy demo artifact escaped the operation project')
            if path.name.endswith('.lock'):
                raise ValueError('Finish the active demo preparation before migrating its records')
            target = destination / path.relative_to(source) if source.is_dir() else destination
            if not target.resolve().is_relative_to(workspace):
                raise ValueError('Demo migration target escaped its workspace')
            if target.exists() and (target.is_dir() != path.is_dir() or
                    path.is_file() and file_hash(target) != file_hash(path)):
                raise ValueError('Conflicting converter demo artifact; both copies were preserved: ' + str(target))
            (directories if path.is_dir() else files).append((path, target))
    for _, target in directories:
        target.mkdir(parents=True, exist_ok=True)
    for source, target in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if file_hash(target) != file_hash(source):
                raise ValueError('Converter demo artifact changed during migration')
            source.unlink()
        else:
            source.rename(target)
    for source, _ in sorted(directories, key=lambda pair: len(pair[0].parts), reverse=True):
        source.rmdir()
    return workspace


def saved_generation_proposal(project, saved_path):
    """Rebase a legacy cache pointer without changing its retained journal bytes."""
    project = Path(project).resolve()
    path = Path(saved_path).resolve()
    legacy = project / '.demo-scenario-generation'
    current = demo_artifact(project, '.demo-scenario-generation')
    if path.is_relative_to(legacy):
        path = current / path.relative_to(legacy)
    if not path.resolve().is_relative_to(current):
        raise ValueError('Saved demo proposal escaped its generation journal')
    return path
