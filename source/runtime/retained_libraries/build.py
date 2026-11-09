"""Adapt verified retained artifacts to the existing Maven verifier and project lifecycle."""

from pathlib import Path
from runtime.retained_libraries.artifacts import materialize, restore_portable, DIRECTORY, verify_library
from runtime.retained_libraries.catalog import current


def portable_approvals(project, profile):
    """Reapply current original IBM exceptions when revalidating a saved component."""
    from runtime.retained_libraries.artifacts import verify_portable
    directory = Path(project) / DIRECTORY
    if not directory.exists():
        return set()
    approved = set()
    for coordinate, record in verify_portable(directory)['libraries'].items():
        if not record.get('ibm'):
            continue
        classes = record.get('required_classes', [])
        from tools.conversion_tools.composer_runtime_contracts import composer_class
        if any(composer_class(name) for name in classes):
            raise ValueError('Saved dependency cannot retain Composer runtime')
        if record.get('original_coordinates') not in getattr(profile, 'allowed_ibm_artifacts', ()) and not (
                classes and all(name in getattr(profile, 'allowed_ibm_classes', ()) for name in classes)):
            raise ValueError('Saved IBM dependency no longer has its original approval')
        approved.add(coordinate)
    return approved


class RetainedVerifier:
    """Delegate normal Maven validation while supplying exact selected original artifacts."""

    def __init__(self, verifier, profile, project, libraries):
        self.verifier, self.profile, self.project, self.libraries = verifier, profile, Path(project), libraries

    def __getattr__(self, name):
        return getattr(self.verifier, name)

    def repository(self):
        from tools.maven_dependency_tools.import_ownership import repository_path
        from tools.conversion_tools.scoped_reuse.fingerprints import revision
        settings = getattr(self.profile, 'maven_settings_path', None)
        return repository_path(settings, revision(settings) if settings else None, getattr(self.profile, 'maven_local_repository', None))

    def __call__(self, dependency):
        if (self.project / DIRECTORY).exists():
            restore_portable(self.project / DIRECTORY, self.project / DIRECTORY, self.repository())
        value = self.libraries.get(dependency.coordinates)
        if value:
            library = verify_library(value, self.profile)
            if not set(dependency.required_classes) <= set(library.dependency.required_classes):
                raise ValueError('Selected retained dependency claims unverified required classes')
            materialize(value, self.profile, self.project, self.repository())
        return self.verifier(dependency)

    def compile_project(self, project, allowed_ibm_artifacts=(), *, goal='compile'):
        if (Path(project) / DIRECTORY).exists():
            restore_portable(Path(project) / DIRECTORY, Path(project) / DIRECTORY, self.repository())
        return self.verifier.compile_project(project, allowed_ibm_artifacts, goal=goal)


def attach_build_context(context, profile, project):
    """Retained candidates remain optional; only selected dependencies are materialized."""
    scope = current()
    libraries = scope[1] if scope else {}
    if libraries or (Path(project) / DIRECTORY).exists():
        context.verifier = RetainedVerifier(context.verifier, profile, project, libraries)
        context.allowed_ibm_artifacts = tuple(sorted(set(context.allowed_ibm_artifacts) | portable_approvals(project, profile) |
            {value['dependency']['group_id'] + ':' + value['dependency']['artifact_id'] + ':' + value['dependency']['version']
             for value in libraries.values() if value['ibm']}))
    return context
