"""Separate readable operation IDs from safe generated Maven artifact coordinates."""

import re
from tools.component_inventory_tools.identity import stable_id


def native_artifact_id(name):
    """Preserve ordinary coordinates; encode special labels without renaming evidence."""
    return name if re.fullmatch(r'[A-Za-z0-9_.-]+', name) else 'scoped-' + stable_id(name)[:24]
