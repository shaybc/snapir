"""Create planned Maven libraries and attach them to their consuming services."""

from pathlib import Path
from xml.etree import ElementTree

from constants import COMMON_LIB_ARTIFACT_ID, COMMON_LIB_GROUP_ID
from models.maven_dependency import MavenDependency
from tools.maven_dependency_tools.pom_manager import merge_dependencies, project_lock
from tools.state_store_tools.shared_library_plans import get_shared_library_plan


def create_library_contexts(conn, config, profile, contexts, factory):
    """Return library contexts, preserving the existing common-lib baseline."""
    plan = get_shared_library_plan(conn, config.run_id)
    libraries = {"common-lib": factory(profile, Path(config.output_root) / "common-lib", COMMON_LIB_ARTIFACT_ID)}
    versions = {"common-lib": "1.0.0"}
    if plan:
        for library in plan.libraries:
            root = Path(config.output_root) / "common-lib" if library.library_id == "common-lib" else Path(config.output_root) / "libraries" / library.library_id
            context = libraries.get(library.library_id) or factory(profile, root, library.library_id)
            with project_lock(Path(context.pom_path)):
                tree = ElementTree.parse(context.pom_path)
                node = tree.getroot().find("{*}version")
                if node is None:
                    raise ValueError("Managed library POM has no project version")
                if node.text != library.version:
                    node.text = library.version
                    tree.write(context.pom_path, encoding="utf-8", xml_declaration=True)
            libraries[library.library_id] = context
            versions[library.library_id] = library.version
    for (operation, channel), context in contexts.items():
        required = {"common-lib"}
        if plan:
            required.update(library.library_id for library in plan.libraries if channel + "/" + operation in library.consumers)
        for identity in sorted(required):
            merge_dependencies(context.pom_path, [MavenDependency(group_id=COMMON_LIB_GROUP_ID,
                artifact_id=COMMON_LIB_ARTIFACT_ID if identity == "common-lib" else identity,
                version=versions[identity], reason="Generated shared library in the reviewed migration plan")],
                lambda proposal: None, task_id="generated-library-baseline")
    if plan:
        if plan.diagnostics:
            raise ValueError("Library dependency plan contains unresolved diagnostics")
        for name, required in plan.library_dependencies.items():
            for dependency in required:
                merge_dependencies(libraries[name].pom_path, [MavenDependency(group_id=COMMON_LIB_GROUP_ID,
                    artifact_id=COMMON_LIB_ARTIFACT_ID if dependency == "common-lib" else dependency,
                    version=versions[dependency], reason="Generated utility library required by source dependency graph")],
                    lambda proposal: None, task_id="generated-library-dependency")
    return libraries
