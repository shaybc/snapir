"""Resolve application identity and a registry location independent of run folders."""

from pathlib import Path

from runtime.project_paths import project_root
from tools.component_inventory_tools.identity import stable_id


def resolve_registry_settings(profile):
    """Return the existing workspace identity and shared database path without I/O.

    Input paths are effective configuration paths. Explicit registry paths are
    resolved by the profile loader; defaults do not depend on a run/output folder.
    """
    application_id = profile.source_workspace_id or Path(profile.source_root).resolve().as_uri()
    if not application_id.strip():
        raise ValueError("The service registry needs a non-empty source workspace identity")
    path = (Path(profile.service_registry_path).resolve() if profile.service_registry_path
            else project_root() / "work" / "service_registry" / stable_id(application_id) / "services.db")
    return application_id, path
