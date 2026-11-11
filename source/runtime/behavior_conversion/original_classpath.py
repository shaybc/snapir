"""Use the original unit's project build path in isolated comparison processes."""
from pathlib import Path


def original_classpath(profile, unit):
    """Require evidenced ordering rather than execute an alphabetically sorted runtime."""
    root = getattr(profile, 'source_root', None)
    if not root or not Path(root).is_dir():
        return list(dict.fromkeys([*profile.classpath_jars, *profile.framework_jars]))
    from tools.source_discovery_tools import discover_java_sources
    from tools.source_discovery_tools.classpath_scope import discover_conversion_classpath
    from tools.behavior_verification.boundary_contracts import boundary_contract
    source = discover_java_sources(root)
    implementation = boundary_contract(unit).implementation_class
    owners = {source.class_projects[path] for path in source.classes.get(implementation, [])}
    project = next(iter(owners)) if len(owners) == 1 else (
        getattr(profile, 'scoped_java_projects', {}).get(unit.get('channel', '')) or getattr(profile, 'scoped_java_project', None))
    index = discover_conversion_classpath(root, profile.classpath_jars, profile.eclipse_classpath_variables, profile=profile)
    if not index.project_classpaths:
        return list(dict.fromkeys([*profile.classpath_jars, *profile.framework_jars]))
    if not project or project not in index.project_classpaths:
        raise ValueError('Original comparison needs an unambiguous source project')
    if index.issues:
        raise ValueError('Original project classpath is incomplete: ' + '; '.join(index.issues))
    from tools.source_discovery_tools.binary_resolution import ordered_library_paths
    return list(dict.fromkeys([*ordered_library_paths(index, project), *profile.framework_jars]))
