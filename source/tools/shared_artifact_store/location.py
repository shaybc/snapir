"""Resolve the durable shared store without depending on a conversion run."""
from pathlib import Path
import constants

from runtime.project_paths import project_root


def store_root(profile):
    """Resolve a configured store; direct profiles use the project as their base."""
    return (project_root() / getattr(profile, 'shared_store_root', constants.SHARED_STORE_ROOT)).resolve()


def application_id(profile):
    """Keep applications isolated; an explicit workspace identity survives relocation."""
    return getattr(profile, 'source_workspace_id', None) or Path(getattr(profile, 'source_root', project_root())).resolve().as_uri()
